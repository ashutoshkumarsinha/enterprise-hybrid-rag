COMPOSE := docker compose -f compose/docker-compose.yml --env-file .env
IMAGE_TAG ?= dev
REGISTRY ?=
PUSH     ?= false
PACKER_ARGS := -var "image_tag=$(IMAGE_TAG)" -var "registry=$(REGISTRY)" -var "push=$(PUSH)"

.PHONY: network up down health logs build lint format integration benchmark benchmark-nightly smoke-e2e prune-sessions packer-init packer-validate packer-build

network:
	docker network inspect hybrid-rag-net >/dev/null 2>&1 || docker network create hybrid-rag-net

build:
	$(COMPOSE) build

up: network build
	$(COMPOSE) up -d query

down:
	$(COMPOSE) down

health:
	@chmod +x scripts/*.sh 2>/dev/null || true
	@./scripts/healthcheck.sh

logs:
	$(COMPOSE) logs -f --tail=100

lint:
	@$(MAKE) -C .. lint

format:
	@$(MAKE) -C .. format

benchmark: ## Run golden-set benchmark (stub mode default)
	@python benchmarks/benchmark_rag.py --limit 4 --golden-set benchmarks/golden_set.json.example

benchmark-nightly: ## Nightly benchmark + Ragas + baseline compare
	@python benchmarks/benchmark_rag.py --limit 10 --ragas --warn-total-p95-ms 45000 --warn-faithfulness 0.80
	@if [ -f benchmarks/baselines.json ]; then \
		python benchmarks/compare_benchmark_run.py benchmarks/last_run.json benchmarks/baselines.json; \
	else \
		echo "SKIP compare: benchmarks/baselines.json not present"; \
	fi

smoke-e2e: ## E2E smoke (in-process stub or QUERY_BASE_URL)
	@python benchmarks/smoke_test.py --e2e --in-process --warn-total-ms 45000

prune-sessions: ## Soft-delete sessions older than SESSION_MAX_AGE_DAYS (E-44)
	@python -m app.session_prune

integration: ## Live-stack integration tests (see .env.live.example + scripts/run-integration.sh)
	@chmod +x scripts/run-integration.sh 2>/dev/null || true
	@./scripts/run-integration.sh -q

packer-init:
	packer init packer/

packer-validate: packer-init
	packer validate $(PACKER_ARGS) packer/

packer-build: packer-init
	packer build $(PACKER_ARGS) packer/
