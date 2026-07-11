COMPOSE := docker compose -f compose/docker-compose.yml --env-file .env
PROFILE ?= default
IMAGE_TAG ?= dev
REGISTRY ?=
PUSH     ?= false
PACKER_ARGS := -var "image_tag=$(IMAGE_TAG)" -var "registry=$(REGISTRY)" -var "push=$(PUSH)"

.PHONY: network up down health logs build lint format migrate migrate-status prune-versions packer-init packer-validate packer-build benchmark benchmark-mock

network:
	docker network inspect hybrid-rag-net >/dev/null 2>&1 || docker network create hybrid-rag-net

build:
	$(COMPOSE) build

up: network build
ifeq ($(PROFILE),beat)
	$(COMPOSE) --profile beat up -d
else
	$(COMPOSE) up -d orchestrator worker
endif

down:
	$(COMPOSE) --profile beat down

health:
	@chmod +x scripts/*.sh 2>/dev/null || true
	@./scripts/healthcheck.sh

logs:
	$(COMPOSE) logs -f --tail=100

lint:
	@$(MAKE) -C .. lint

format:
	@$(MAKE) -C .. format

migrate: ## Apply pending catalog migrations (requires CATALOG_DSN)
	@python -m app.migrate

migrate-status: ## Show applied/pending migrations
	@python -m app.migrate --status

prune-versions: ## Prune old document versions beyond VERSION_RETENTION_COUNT (E-22)
	@PY=$$( [ -x .venv/bin/python ] && echo .venv/bin/python || echo python3 ); \
	$$PY -m app.version_prune

purge-tenant: ## Purge tenant data (E-21) — requires TENANT=... and CONFIRM=1
	@test -n "$(TENANT)" || (echo "Usage: make purge-tenant TENANT=acme CONFIRM=1" && exit 1)
	@PY=$$( [ -x .venv/bin/python ] && echo .venv/bin/python || echo python3 ); \
	if [ "$(CONFIRM)" = "1" ]; then \
	  $$PY -m app.tenant_purge "$(TENANT)" --confirm; \
	else \
	  $$PY -m app.tenant_purge "$(TENANT)" --dry-run; \
	fi

test: ## Run ingest unit + contract tests
	@python -m pytest tests/unit tests/contract -q

test-integration: ## Live-stack integration (requires .env.live profile)
	@chmod +x scripts/run-integration.sh && ./scripts/run-integration.sh -q

benchmark-mock: ## Mock ingest throughput (PR warn tier)
	@PY=$$( [ -x .venv/bin/python ] && echo .venv/bin/python || echo python3 ); \
	$$PY benchmarks/benchmark_ingest.py --mock --chunks 500 --warn-chunks-per-min 1000

benchmark: ## Live ingest throughput (requires non-stub embed path)
	@PY=$$( [ -x .venv/bin/python ] && echo .venv/bin/python || echo python3 ); \
	$$PY benchmarks/benchmark_ingest.py --live-stack --chunks 8 --fail-chunks-per-min 2.0

packer-init:
	packer init packer/

packer-validate: packer-init
	packer validate $(PACKER_ARGS) packer/

packer-build: packer-init
	packer build $(PACKER_ARGS) packer/
