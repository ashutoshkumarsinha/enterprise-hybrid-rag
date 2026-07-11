COMPOSE_BASE := docker compose -f compose/docker-compose.yml --env-file .env
ifeq ($(PROFILE),jaeger-persist)
COMPOSE := $(COMPOSE_BASE) -f compose/docker-compose.jaeger-persist.yml --profile jaeger-persist
else
COMPOSE := $(COMPOSE_BASE)
endif
IMAGE_TAG ?= dev
REGISTRY ?=
PUSH     ?= false
PACKER_ARGS := -var "image_tag=$(IMAGE_TAG)" -var "registry=$(REGISTRY)" -var "push=$(PUSH)"
PROFILE ?=

.PHONY: up down health logs network synthetic-trace import-signoz validate-prometheus validate-collector langfuse-init bootstrap-langfuse-keys packer-init packer-validate packer-build

network:
	docker network inspect hybrid-rag-net >/dev/null 2>&1 || docker network create hybrid-rag-net

up: network langfuse-init
ifeq ($(PROFILE),metrics)
	$(COMPOSE) --profile metrics up -d langfuse-postgres langfuse jaeger otel-collector prometheus
else ifeq ($(PROFILE),signoz)
	COLLECTOR_CONFIG=../collector/otel-collector-config.signoz.yaml SIGNOZ_OTLP_ENDPOINT=signoz-otel-collector:4317 \
	$(COMPOSE) --profile signoz up -d langfuse-postgres langfuse jaeger otel-collector signoz-otel-collector
else ifeq ($(PROFILE),prod)
	TRACE_SAMPLING_PERCENTAGE=$(TRACE_SAMPLING_PERCENTAGE) COLLECTOR_CONFIG=../collector/otel-collector-config.prod.yaml \
	$(COMPOSE) up -d langfuse-postgres langfuse jaeger otel-collector
else ifeq ($(PROFILE),jaeger-persist)
	$(COMPOSE) up -d langfuse-postgres langfuse jaeger otel-collector
else
	$(COMPOSE) up -d langfuse-postgres langfuse jaeger otel-collector
endif

down:
	$(COMPOSE_BASE) --profile metrics --profile signoz --profile jaeger-persist down

health:
	@chmod +x scripts/*.sh 2>/dev/null || true
	@./scripts/healthcheck.sh

langfuse-init: ## Ensure .env has LANGFUSE_INIT_* headless bootstrap vars
	@chmod +x scripts/ensure_langfuse_init.sh
	@./scripts/ensure_langfuse_init.sh

bootstrap-langfuse-keys: langfuse-init ## Copy API keys into query/.env
	@chmod +x ../scripts/bootstrap_langfuse_keys.sh
	@../scripts/bootstrap_langfuse_keys.sh

synthetic-trace:
	@chmod +x scripts/*.sh 2>/dev/null || true
	@./scripts/synthetic-trace.sh

import-signoz:
	@python3 scripts/import_signoz.py all

validate-prometheus:
	@docker run --rm -v "$(CURDIR)/collector/prometheus.yml:/etc/prometheus/prometheus.yml:ro" \
		-v "$(CURDIR)/alerts/prometheus-rules.yaml:/etc/prometheus/alerts/prometheus-rules.yaml:ro" \
		prom/prometheus:v2.54.1 promtool check config /etc/prometheus/prometheus.yml

validate-collector: ## OBS-P2 contract — truncation processor on all collector profiles
	@cd ../ingest && PY=$$( [ -x .venv/bin/python ] && echo .venv/bin/python || echo python3 ); \
	$$PY -m pytest tests/contract/test_infra_otel_collector_truncation.py tests/contract/test_infra_otel_collector_prod.py -q

logs:
	$(COMPOSE) logs -f --tail=100 otel-collector jaeger

packer-init:
	packer init packer/

packer-validate: packer-init
	packer validate $(PACKER_ARGS) packer/

packer-build: packer-init
	packer build $(PACKER_ARGS) packer/
