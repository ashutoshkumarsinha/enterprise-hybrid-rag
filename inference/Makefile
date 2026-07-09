COMPOSE := docker compose -f compose/docker-compose.yml --env-file .env
PROFILE ?= gpu_24gb
IMAGE_TAG ?= dev
REGISTRY ?=
PUSH     ?= false
PACKER_ARGS := -var "image_tag=$(IMAGE_TAG)" -var "registry=$(REGISTRY)" -var "push=$(PUSH)"

.PHONY: network up down health smoke-test logs packer-init packer-validate packer-build

network:
	docker network inspect hybrid-rag-net >/dev/null 2>&1 || docker network create hybrid-rag-net

up: network
	$(COMPOSE) --profile $(PROFILE) up -d

down:
	$(COMPOSE) --profile $(PROFILE) down

health:
	@./scripts/healthcheck.sh

smoke-test:
	@./scripts/smoke-test-llm.sh

logs:
	$(COMPOSE) --profile $(PROFILE) logs -f --tail=100

packer-init:
	packer init packer/

packer-validate: packer-init
	packer validate $(PACKER_ARGS) packer/

packer-build: packer-init
	packer build $(PACKER_ARGS) packer/
