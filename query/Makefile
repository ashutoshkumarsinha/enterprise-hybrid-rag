COMPOSE := docker compose -f compose/docker-compose.yml --env-file .env
IMAGE_TAG ?= dev
REGISTRY ?=
PUSH     ?= false
PACKER_ARGS := -var "image_tag=$(IMAGE_TAG)" -var "registry=$(REGISTRY)" -var "push=$(PUSH)"

.PHONY: network up down health logs build lint format integration packer-init packer-validate packer-build

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

integration: ## Live-stack integration tests (see .env.live.example + scripts/run-integration.sh)
	@chmod +x scripts/run-integration.sh 2>/dev/null || true
	@./scripts/run-integration.sh -q

packer-init:
	packer init packer/

packer-validate: packer-init
	packer validate $(PACKER_ARGS) packer/

packer-build: packer-init
	packer build $(PACKER_ARGS) packer/
