COMPOSE := docker compose -f compose/docker-compose.yml --env-file .env
PROFILE ?= default
IMAGE_TAG ?= dev
REGISTRY ?=
PUSH     ?= false
PACKER_ARGS := -var "image_tag=$(IMAGE_TAG)" -var "registry=$(REGISTRY)" -var "push=$(PUSH)"

.PHONY: network up down health init-db init-minio init-catalog-indexes backup logs render-caddy mtls-dev-certs cert-manager-install cert-manager-issuer cert-manager-health cert-manager-sync-ca packer-init packer-validate packer-build

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

init-catalog-indexes:
	@chmod +x scripts/apply-catalog-indexes.sh
	@./scripts/apply-catalog-indexes.sh

backup:
	@chmod +x scripts/backup.sh
	@./scripts/backup.sh

render-caddy:
	python3 scripts/render_caddyfile.py --config config/infra.toml --write caddy/Caddyfile

mtls-dev-certs: ## Generate dev CA + server/client certs (E-34)
	@chmod +x scripts/gen_mtls_certs.sh
	@./scripts/gen_mtls_certs.sh

cert-manager-install: ## Install cert-manager controllers (Kubernetes)
	@chmod +x k8s/cert-manager/*.sh
	@./k8s/cert-manager/install.sh

cert-manager-issuer: ## Bootstrap hybrid-rag root CA ClusterIssuers
	@chmod +x k8s/cert-manager/*.sh
	kubectl apply -f k8s/cert-manager/cluster-issuer-selfsigned.yaml
	kubectl apply -f k8s/cert-manager/ca-certificate.yaml
	kubectl wait --for=condition=Ready certificate/hybrid-rag-root-ca -n cert-manager --timeout=180s
	kubectl apply -f k8s/cert-manager/cluster-issuer-ca.yaml

cert-manager-health: ## Health check cert-manager controllers + CRDs
	@chmod +x k8s/cert-manager/*.sh
	@./k8s/cert-manager/healthcheck.sh

cert-manager-sync-ca: ## Copy root CA secret to app namespace (APP_NS=hybrid-rag)
	@chmod +x k8s/cert-manager/*.sh
	@./k8s/cert-manager/sync-root-ca.sh $(APP_NS)

logs:
	$(COMPOSE) logs -f --tail=100

packer-init:
	packer init packer/

packer-validate: packer-init
	packer validate $(PACKER_ARGS) packer/

packer-build: packer-init
	packer build $(PACKER_ARGS) packer/
