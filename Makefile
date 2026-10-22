PYTHON ?= python3.11
VENV := .venv/bin
.PHONY: install test
install:
	$(PYTHON) -m venv .venv
	$(VENV)/python -m pip install -r vigil-system/orchestrator_agent/requirements.txt -r vigil-system/transaction_monitor_agent/requirements.txt 'psycopg[binary]==3.2.6'
test:
	$(VENV)/python -m unittest discover -s tests -v
