VENV?=.venv
PY=${VENV}/bin/python
PIP=${VENV}/bin/pip

.PHONY: help venv install deps run test lint format docker-build docker-up docker-down alembic-upgrade migrate clean

help:
	@echo "Makefile targets:"
	@echo "  help             - Show this help"
	@echo "  venv             - Create a virtualenv at $(VENV)"
	@echo "  install          - Create venv and install requirements"
	@echo "  deps             - Alias for install"
	@echo "  run              - Run the app with uvicorn (reload)"
	@echo "  test             - Run pytest"
	@echo "  lint             - Run linters (from dev requirements)"
	@echo "  docker-build     - Build the Docker image"
	@echo "  docker-up        - Start services with docker-compose"
	@echo "  docker-down      - Stop services started by docker-compose"
	@echo "  alembic-upgrade  - Run alembic upgrade head"
	@echo "  migrate          - Create autogen migration and apply"
	@echo "  clean            - Remove venv and common caches"

venv:
	python3 -m venv $(VENV)
	$(PIP) install --upgrade pip

install: venv
	$(PIP) install -r requirements.txt
	@if [ -f requirements-dev.txt ]; then $(PIP) install -r requirements-dev.txt; fi

deps: install

run: venv
	$(PY) -m uvicorn src.main:app --host 0.0.0.0 --port 8000 --reload

test: venv
	$(PY) -m pytest -q

lint: venv
	$(PY) -m flake8 || echo "flake8 not installed; add to requirements-dev.txt"

format: venv
	$(PY) -m black src tests || echo "black not installed; add to requirements-dev.txt"

docker-build:
	docker build -t veriphy-be:latest .

docker-up:
	docker-compose up -d --build

docker-down:
	docker-compose down

alembic-upgrade: venv
	$(PY) -m alembic upgrade head

migrate: venv
	$(PY) -m alembic revision --autogenerate -m "autogen"
	$(PY) -m alembic upgrade head

clean:
	rm -rf $(VENV) .pytest_cache build dist *.egg-info __pycache__
