# System python interpreter. Used only to create virtual environment
PY=python3
VENV=venv
BIN=$(VENV)/bin
ACTIVATE=source $(BIN)/activate

ifeq ($(OS), Windows_NT)
	BIN=$(VENV)/Scripts
	PY=python
	ACTIVATE=$(BIN)/activate
endif


all: format lint test

.PHONY: lint
lint:
	flake8 . --count --select=E9,F63,F7,F82 --show-source --statistics
	flake8 . --count --exit-zero --max-complexity=13 --max-line-length=127 --statistics

format-check:
	black --check .

.PHONY: format
format:
	black .

.PHONY: test
test:
	$(PY) -m pytest tests/ -vv

.PHONY: test-cov
test-cov:
	$(PY) -m pytest --cov-report term-missing --cov=todus tests/ -vv

.PHONY: typecheck
typecheck:
	mypy -p todus

.PHONY: clean
clean: clean-build clean-pyc clean-test

clean-build:
	rm -rf build dist *.egg-info

clean-pyc:
	find . -type f -name "*.pyc" -exec rm -f {} \;
	find . -type f -name "*.pyo" -exec rm -f {} \;
	find . -type d -name "__pycache__" -exec rm -rf {} \;

clean-test:
	rm -rf .tox/ htmlcov/
	rm -f .coverage
