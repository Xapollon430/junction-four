.PHONY: start check reset antithesis-build antithesis-up antithesis-down

PYTHON ?= python3
COMPOSE = docker compose -f deployment/config/docker-compose.yaml

start:
	$(PYTHON) -m junction.launcher

check:
	$(PYTHON) -m compileall -q junction deployment

reset:
	$(PYTHON) -m junction.reset

antithesis-build:
	$(COMPOSE) build

antithesis-up:
	$(COMPOSE) up

antithesis-down:
	$(COMPOSE) down -v
