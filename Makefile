PYTHON ?= python3
VENV   ?= .venv
BIN    := $(VENV)/bin

.PHONY: install format lint test run demo tune clean

$(BIN)/python:
	$(PYTHON) -m venv $(VENV)

install: $(BIN)/python
	$(BIN)/pip install --upgrade pip
	$(BIN)/pip install -e ".[dev]"

format:
	$(BIN)/black aurora_cdp tests
	$(BIN)/isort aurora_cdp tests

lint:
	-$(BIN)/ruff check aurora_cdp tests
	-$(BIN)/mypy aurora_cdp

test:
	$(BIN)/pytest -q

run:
	$(BIN)/uvicorn aurora_cdp.api.main:app --host 127.0.0.1 --port 8000 --reload

demo:
	$(BIN)/aurora demo

tune:
	$(BIN)/aurora tune --quick

clean:
	rm -rf .aurora outputs .pytest_cache .ruff_cache .mypy_cache
	find . -name __pycache__ -type d -prune -exec rm -rf {} +
