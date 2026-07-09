COMPOSE := docker compose -f compose/docker-compose.yml --env-file .env
PROFILE ?= default
IMAGE_TAG ?= dev
REGISTRY ?=
PUSH     ?= false
PACKER_ARGS := -var "image_tag=$(IMAGE_TAG)" -var "registry=$(REGISTRY)" -var "push=$(PUSH)"

.PHONY: network up down health init-db init-minio backup logs render-caddy packer-init packer-validate packer-build

network:
	docker network inspect hybrid-rag-net >/dev/null 2>&1 || docker network create hybrid-rag-net

up: network
ifeq ($(PROFILE),edge)
	$(COMPOSE) --profile edge up -d qdrant neo4j redis minio postgres keycloak caddy
else
	$(COMPOSE) up -d qdrant neo4j redis minio postgres keycloak
endif

down:
	$(COMPOSE) --profile edge down

health:
	@chmod +x scripts/*.sh 2>/dev/null || true
	@./scripts/healthcheck.sh

init-db:
	@chmod +x scripts/init-db.sh scripts/init-minio.sh
	@./scripts/init-db.sh

init-minio:
	@chmod +x scripts/init-minio.sh
	@./scripts/init-minio.sh

backup:
	@chmod +x scripts/backup.sh
	@./scripts/backup.sh

render-caddy:
	python3 scripts/render_caddyfile.py --config config/infra.toml --write caddy/Caddyfile

logs:
	$(COMPOSE) logs -f --tail=100

packer-init:
	packer init packer/

packer-validate: packer-init
	packer validate $(PACKER_ARGS) packer/

packer-build: packer-init
	packer build $(PACKER_ARGS) packer/
