# Enterprise Hybrid RAG — root Makefile
# Orchestrates all sub-projects. Spec: ENTERPRISE_HYBRID_RAG_SPEC.md §12.5, §23.6
#
# Quick start:
#   make help
#   make env          # copy .env.example → .env where missing
#   make bootstrap    # full dev stack (infra → inference → obs → ingest → query)
#   make health       # health checks all planes
#   make lint         # Ruff + Black (requires: pip install ruff black)

SHELL := /bin/bash
.DEFAULT_GOAL := help

# Sub-project directories
INFRA_DIR          := infra
INFERENCE_DIR      := inference
OBSERVABILITY_DIR  := observability
INGEST_DIR         := ingest
QUERY_DIR          := query

# Bootstrap options (override on CLI)
INFERENCE_PROFILE  ?= gpu_24gb
INFRA_EDGE         ?= false
INGEST_PROFILE     ?= default
OBS_PROFILE        ?=

# Packer (image supply chain)
IMAGE_TAG          ?= dev
REGISTRY           ?=
PUSH               ?= false
PACKER_DIR         := packer
PACKER_ARGS        := -var "image_tag=$(IMAGE_TAG)" -var "registry=$(REGISTRY)" -var "push=$(PUSH)"

# Python paths for lint/format (root pyproject.toml)
PYTHON_APP_DIRS    := query/app ingest/app inference/reranker

# ---------------------------------------------------------------------------
# Help
# ---------------------------------------------------------------------------

.PHONY: help
help: ## Show this help
	@echo "Enterprise Hybrid RAG — root targets"
	@echo ""
	@grep -E '^[a-zA-Z0-9_.-]+:.*## ' $(MAKEFILE_LIST) | sort | \
		awk 'BEGIN {FS = ":.*## "}; {printf "  \033[36m%-24s\033[0m %s\n", $$1, $$2}'
	@echo ""
	@echo "Variables: INFERENCE_PROFILE=$(INFERENCE_PROFILE)  IMAGE_TAG=$(IMAGE_TAG)  INFRA_EDGE=$(INFRA_EDGE)  OBS_PROFILE=$(OBS_PROFILE)"
	@echo "Examples:"
	@echo "  make env && make bootstrap"
	@echo "  make bootstrap INFERENCE_PROFILE=lima_12gb INFRA_EDGE=true"
	@echo "  make lint && make health"

# ---------------------------------------------------------------------------
# Network
# ---------------------------------------------------------------------------

.PHONY: network
network: ## Create shared Docker network hybrid-rag-net
	@$(MAKE) -C $(INFRA_DIR) network

# ---------------------------------------------------------------------------
# Environment files
# ---------------------------------------------------------------------------

.PHONY: env
env: ## Copy .env.example → .env in each sub-project (skip if .env exists)
	@for dir in $(INFRA_DIR) $(INFERENCE_DIR) $(OBSERVABILITY_DIR) $(INGEST_DIR) $(QUERY_DIR); do \
		if [ -f "$$dir/.env.example" ] && [ ! -f "$$dir/.env" ]; then \
			cp "$$dir/.env.example" "$$dir/.env"; \
			echo "Created $$dir/.env"; \
		elif [ -f "$$dir/.env" ]; then \
			echo "Exists $$dir/.env (unchanged)"; \
		else \
			echo "Skip $$dir (no .env.example)"; \
		fi; \
	done

# ---------------------------------------------------------------------------
# Per-plane delegation
# ---------------------------------------------------------------------------

.PHONY: infra-up infra-down infra-health infra-init-db infra-logs
infra-up: network ## Start infra stores + Keycloak
	@$(MAKE) -C $(INFRA_DIR) up

infra-down: ## Stop infra stack
	@$(MAKE) -C $(INFRA_DIR) down

infra-health: ## Health check infra
	@$(MAKE) -C $(INFRA_DIR) health

infra-init-db: ## Init Qdrant collection + MinIO buckets
	@$(MAKE) -C $(INFRA_DIR) init-db

infra-logs: ## Tail infra logs
	@$(MAKE) -C $(INFRA_DIR) logs

.PHONY: inference-up inference-down inference-health inference-logs
inference-up: network ## Start inference (PROFILE=$(INFERENCE_PROFILE))
	@$(MAKE) -C $(INFERENCE_DIR) up PROFILE=$(INFERENCE_PROFILE)

inference-down: ## Stop inference
	@$(MAKE) -C $(INFERENCE_DIR) down PROFILE=$(INFERENCE_PROFILE)

inference-health: ## Health check inference
	@$(MAKE) -C $(INFERENCE_DIR) health

inference-logs: ## Tail inference logs
	@$(MAKE) -C $(INFERENCE_DIR) logs PROFILE=$(INFERENCE_PROFILE)

.PHONY: observability-up observability-down observability-health observability-logs synthetic-trace
observability-up: network ## Start Langfuse + OTel + Jaeger (OBS_PROFILE=signoz|metrics for optional backends)
	@$(MAKE) -C $(OBSERVABILITY_DIR) up PROFILE=$(OBS_PROFILE)

observability-down: ## Stop observability
	@$(MAKE) -C $(OBSERVABILITY_DIR) down

observability-health: ## Health check observability
	@$(MAKE) -C $(OBSERVABILITY_DIR) health

observability-logs: ## Tail observability logs
	@$(MAKE) -C $(OBSERVABILITY_DIR) logs

synthetic-trace: ## Run synthetic trace script (observability)
	@$(MAKE) -C $(OBSERVABILITY_DIR) synthetic-trace

.PHONY: ingest-up ingest-down ingest-health ingest-logs
ingest-up: network ## Start ingest orchestrator + workers
	@$(MAKE) -C $(INGEST_DIR) up PROFILE=$(INGEST_PROFILE)

ingest-down: ## Stop ingest
	@$(MAKE) -C $(INGEST_DIR) down

ingest-health: ## Health check ingest
	@$(MAKE) -C $(INGEST_DIR) health

ingest-logs: ## Tail ingest logs
	@$(MAKE) -C $(INGEST_DIR) logs

.PHONY: query-up query-down query-health query-logs query-test
query-up: network ## Start hybrid-rag-query MCP gateway
	@$(MAKE) -C $(QUERY_DIR) up

query-down: ## Stop query
	@$(MAKE) -C $(QUERY_DIR) down

query-health: ## Health check query (/healthz)
	@$(MAKE) -C $(QUERY_DIR) health

query-logs: ## Tail query logs
	@$(MAKE) -C $(QUERY_DIR) logs

# ---------------------------------------------------------------------------
# Full stack (canonical bootstrap §12.5)
# ---------------------------------------------------------------------------

.PHONY: bootstrap up down health logs
.PHONY: migrate-catalog
migrate-catalog: ## Apply catalog DDL via ingest migration runner
	@$(MAKE) -C $(INGEST_DIR) migrate || echo "WARN: migrate skipped (set CATALOG_DSN in ingest/.env)"

query-test: ## Run query pytest suites
	@cd $(QUERY_DIR) && python -m pytest tests/contract tests/unit -q --tb=short 2>/dev/null || \
		cd $(QUERY_DIR) && python -m pytest tests/contract -q --tb=short

bootstrap: env ## Bootstrap full dev stack (infra → inference → obs → ingest → query)
	@echo "==> 1/6 infra (stores + Keycloak)"
	@$(MAKE) infra-up
	@$(MAKE) infra-init-db
	@$(MAKE) migrate-catalog || echo "WARN: migrate-catalog skipped (set CATALOG_DSN in ingest/.env)"
	@$(MAKE) infra-health
	@echo "==> 2/6 inference (PROFILE=$(INFERENCE_PROFILE))"
	@$(MAKE) inference-up
	@$(MAKE) inference-health
	@echo "==> 3/6 observability"
	@$(MAKE) observability-up
	@$(MAKE) observability-health
	@echo "==> 4/6 ingest"
	@$(MAKE) ingest-up
	@$(MAKE) ingest-health
	@echo "==> 5/6 query"
	@$(MAKE) query-up
	@$(MAKE) query-health
ifeq ($(INFRA_EDGE),true)
	@echo "==> 6/6 infra edge (Caddy)"
	@$(MAKE) -C $(INFRA_DIR) up PROFILE=edge
else
	@echo "==> 6/6 skip edge (set INFRA_EDGE=true for Caddy)"
endif
	@echo ""
	@echo "Bootstrap complete. Optional: make synthetic-trace"

up: bootstrap ## Alias for bootstrap

down: ## Stop all sub-projects (reverse order)
	-$(MAKE) query-down
	-$(MAKE) ingest-down
	-$(MAKE) observability-down
	-$(MAKE) inference-down
	-$(MAKE) infra-down

health: ## Run health checks on all sub-projects
	@echo "==> infra"; $(MAKE) infra-health || exit 1
	@echo "==> inference"; $(MAKE) inference-health || exit 1
	@echo "==> observability"; $(MAKE) observability-health || exit 1
	@echo "==> ingest"; $(MAKE) ingest-health || exit 1
	@echo "==> query"; $(MAKE) query-health || exit 1
	@echo "All health checks passed."

logs: ## Show how to tail logs per plane (use infra-logs, query-logs, …)
	@echo "Tail logs per sub-project:"
	@echo "  make infra-logs | inference-logs | observability-logs | ingest-logs | query-logs"

# ---------------------------------------------------------------------------
# Code quality (§23, docs/CODING_STANDARDS.md)
# ---------------------------------------------------------------------------

.PHONY: lint format test test-unit test-contract test-pr test-nightly benchmark-pr benchmark-ingest-pr
lint: ## Ruff + Black check on application Python
	@command -v ruff >/dev/null 2>&1 || { echo "Install: pip install ruff black"; exit 1; }
	@command -v black >/dev/null 2>&1 || { echo "Install: pip install ruff black"; exit 1; }
	ruff check $(PYTHON_APP_DIRS)
	black --check $(PYTHON_APP_DIRS)

format: ## Auto-format Python with Black
	@command -v black >/dev/null 2>&1 || { echo "Install: pip install black"; exit 1; }
	black $(PYTHON_APP_DIRS)

test: test-unit test-contract ## Run all pytest suites that exist

test-pr: ## PR gate — unit + contract (query + ingest)
	@chmod +x scripts/ci-pr.sh 2>/dev/null || true
	@./scripts/ci-pr.sh

benchmark-pr: ## Stub golden-set benchmark with warn thresholds (PR tier)
	@cd $(QUERY_DIR) && PY=$$( [ -x .venv/bin/python ] && echo .venv/bin/python || echo python3 ); \
	$$PY benchmarks/benchmark_rag.py \
		--limit 4 \
		--golden-set benchmarks/golden_set.json.example \
		--output benchmarks/last_run_ci.json \
		--warn-total-p95-ms 45000

benchmark-ingest-pr: ## Mock ingest throughput warn tier (PR)
	@cd $(INGEST_DIR) && PY=$$( [ -x .venv/bin/python ] && echo .venv/bin/python || echo python3 ); \
	$$PY benchmarks/benchmark_ingest.py --mock --chunks 500 --warn-chunks-per-min 1000

test-nightly: ## Nightly gate — PR suite + integration + benchmark + compare
	@chmod +x scripts/ci-nightly.sh scripts/ci-pr.sh 2>/dev/null || true
	@./scripts/ci-nightly.sh

test-unit: ## pytest tests/unit in query and ingest (if present)
	@status=0; \
	for dir in $(QUERY_DIR) $(INGEST_DIR); do \
		if [ -d "$$dir/tests/unit" ]; then \
			echo "==> pytest $$dir/tests/unit"; \
			(cd "$$dir" && python -m pytest tests/unit -q --tb=short) || status=1; \
		else \
			echo "Skip $$dir/tests/unit (not yet scaffolded)"; \
		fi; \
	done; \
	exit $$status

test-contract: ## pytest tests/contract in query and ingest (if present)
	@status=0; \
	for dir in $(QUERY_DIR) $(INGEST_DIR); do \
		if [ -d "$$dir/tests/contract" ]; then \
			echo "==> pytest $$dir/tests/contract"; \
			(cd "$$dir" && python -m pytest tests/contract -q --tb=short) || status=1; \
		else \
			echo "Skip $$dir/tests/contract (not yet scaffolded)"; \
		fi; \
	done; \
	exit $$status

test-integration: ## Live-stack integration (query + ingest; requires .env.live profile)
	@cd $(QUERY_DIR) && chmod +x scripts/run-integration.sh && ./scripts/run-integration.sh -q
	@cd $(INGEST_DIR) && chmod +x scripts/run-integration.sh && ./scripts/run-integration.sh -q

# ---------------------------------------------------------------------------
# Packer image supply chain (§12.7)
# ---------------------------------------------------------------------------

.PHONY: packer-init packer-validate packer-build packer-build-all
packer-init: ## Initialize root Packer plugins
	packer init $(PACKER_DIR)

packer-validate: packer-init ## Validate root Packer config
	packer validate $(PACKER_ARGS) $(PACKER_DIR)/

packer-build: packer-init ## Build root Packer image set
	packer build $(PACKER_ARGS) $(PACKER_DIR)/

packer-build-all: ## Build images for every sub-project
	IMAGE_TAG=$(IMAGE_TAG) REGISTRY=$(REGISTRY) PUSH=$(PUSH) ./packer/build-all.sh
