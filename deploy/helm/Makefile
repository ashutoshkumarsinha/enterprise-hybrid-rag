.PHONY: template lint

CHART := hybrid-rag
CHART_PATH := hybrid-rag

template:
	helm template $(CHART) ./$(CHART_PATH) -f ./$(CHART_PATH)/values-prod.yaml

lint:
	helm lint ./$(CHART_PATH) -f ./$(CHART_PATH)/values-prod.yaml
