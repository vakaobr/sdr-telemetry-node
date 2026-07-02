.PHONY: setup test lint codegen drift-check clean

VENV := .venv
PY := $(VENV)/bin/python
PIP := $(VENV)/bin/pip

setup: ## venv + both services (editable) + web deps
	python3 -m venv $(VENV)
	$(PIP) install -q -e "services/gateway[dev]" -e "services/radio2[dev]"
	cd web && npm install

test: ## all test suites
	cd services/gateway && ../../$(VENV)/bin/pytest -q
	cd services/radio2 && ../../$(VENV)/bin/pytest -q
	cd web && npm test

lint:
	$(VENV)/bin/ruff check services
	$(VENV)/bin/ruff format --check services
	cd web && npm run lint && npm run typecheck

codegen: ## regenerate models/types from shared/schemas
	PATH="$(abspath $(VENV))/bin:$$PATH" bash scripts/codegen.sh

drift-check: codegen
	git diff --exit-code -- '**/generated_*.py' 'web/src/types/generated/'

clean:
	rm -rf $(VENV) web/node_modules web/dist
