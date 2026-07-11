COMPOSE := docker compose -f compose/docker-compose.yml --env-file .env
IMAGE_TAG ?= dev
REGISTRY ?=
PUSH     ?= false
PACKER_ARGS := -var "image_tag=$(IMAGE_TAG)" -var "registry=$(REGISTRY)" -var "push=$(PUSH)"
PROFILE ?=

.PHONY: up down health logs network synthetic-trace import-signoz packer-init packer-validate packer-build

network:
	docker network inspect hybrid-rag-net >/dev/null 2>&1 || docker network create hybrid-rag-net

up: network
ifeq ($(PROFILE),metrics)
	$(COMPOSE) --profile metrics up -d langfuse-postgres langfuse jaeger otel-collector prometheus
else ifeq ($(PROFILE),signoz)
	COLLECTOR_CONFIG=../collector/otel-collector-config.signoz.yaml SIGNOZ_OTLP_ENDPOINT=signoz-otel-collector:4317 \
	$(COMPOSE) --profile signoz up -d langfuse-postgres langfuse jaeger otel-collector signoz-otel-collector
else ifeq ($(PROFILE),prod)
	TRACE_SAMPLING_PERCENTAGE=$(TRACE_SAMPLING_PERCENTAGE) COLLECTOR_CONFIG=../collector/otel-collector-config.prod.yaml \
	$(COMPOSE) up -d langfuse-postgres langfuse jaeger otel-collector
else
	$(COMPOSE) up -d langfuse-postgres langfuse jaeger otel-collector
endif

down:
	$(COMPOSE) --profile metrics --profile signoz down

health:
	@chmod +x scripts/*.sh 2>/dev/null || true
	@./scripts/healthcheck.sh

synthetic-trace:
	@chmod +x scripts/*.sh 2>/dev/null || true
	@./scripts/synthetic-trace.sh

import-signoz:
	@python3 scripts/import_signoz.py all

logs:
	$(COMPOSE) logs -f --tail=100 otel-collector jaeger

packer-init:
	packer init packer/

packer-validate: packer-init
	packer validate $(PACKER_ARGS) packer/

packer-build: packer-init
	packer build $(PACKER_ARGS) packer/
