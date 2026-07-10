COMPOSE := docker compose -f compose/docker-compose.yml --env-file .env
PROFILE ?= default
IMAGE_TAG ?= dev
REGISTRY ?=
PUSH     ?= false
PACKER_ARGS := -var "image_tag=$(IMAGE_TAG)" -var "registry=$(REGISTRY)" -var "push=$(PUSH)"

.PHONY: network up down health logs build lint format migrate migrate-status packer-init packer-validate packer-build

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

packer-init:
	packer init packer/

packer-validate: packer-init
	packer validate $(PACKER_ARGS) packer/

packer-build: packer-init
	packer build $(PACKER_ARGS) packer/
