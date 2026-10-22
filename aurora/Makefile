# Aurora identity engine (Spark/Delta) targets.
# Invoke as `make -f aurora/Makefile <target>` from the repo root, or add
# `-include aurora/Makefile` to the root Makefile to expose these targets there.
PYTHON ?= python3
VENV   ?= .venv
BIN    := $(VENV)/bin
SIZE   ?= 100000
CONFIG ?= configs/tenants/demo.yaml
RAW    ?= data/raw/run1
PREV   ?=

.PHONY: setup-spark generate-data run-pipeline run-pipeline-drift eval api-spark test-spark \
        docker-spark-up docker-spark-down clean-spark cdc-tail

$(BIN)/python:
	$(PYTHON) -m venv $(VENV)

setup-spark: $(BIN)/python
	$(BIN)/pip install --upgrade pip
	$(BIN)/pip install -e ".[spark,dev]"

generate-data: ## 100k synthetic customers (override SIZE=...) -> data/raw/run1 (+ drifted run2)
	$(BIN)/python -m aurora.synth.generator --size $(SIZE) --out data/raw/run1 --drift-out data/raw/run2

run-pipeline: ## one identity pass over RAW -> data/lake + data/cdc + data/runs/<job_id>
	$(BIN)/python -m aurora.pipeline.runner --config $(CONFIG) --raw $(RAW)

run-pipeline-drift: ## second pass over the drifted data to exercise stable IDs / CDC
	$(BIN)/python -m aurora.pipeline.runner --config $(CONFIG) --raw data/raw/run2

eval: ## metrics vs planted truth (+ churn if PREV=<parquet of prev assignments>)
	$(BIN)/python -m aurora.pipeline.eval --config $(CONFIG) $(if $(PREV),--prev $(PREV),)

api-spark: ## profile API + explorer UI on :8000
	$(BIN)/uvicorn aurora.api.main:app --host 0.0.0.0 --port 8000

test-spark:
	$(BIN)/pytest -q tests/test_synth_small.py tests/test_blocking.py tests/test_scoring.py tests/test_components.py tests/test_stable_id.py

cdc-tail:
	$(BIN)/python scripts/cdc_consumer.py --follow

docker-spark-up:
	docker compose -f aurora/docker/docker-compose.yml up --build -d

docker-spark-down:
	docker compose -f aurora/docker/docker-compose.yml down

clean-spark:
	rm -rf .tmp data/lake data/cdc data/runs data/eval/*.json spark-warehouse derby.log metastore_db
	find aurora tests -name __pycache__ -type d -prune -exec rm -rf {} +
