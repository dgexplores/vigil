PYTHON ?= python3.11
VENV := .venv/bin
MONITOR := .monitor-venv/bin
.PHONY: install test
install:
	$(PYTHON) -m venv .venv
	$(VENV)/python -m pip install -r vigil-system/orchestrator_agent/requirements.txt 'psycopg[binary]==3.2.6'
	$(PYTHON) -m venv .monitor-venv
	$(MONITOR)/python -m pip install -r vigil-system/transaction_monitor_agent/requirements.txt
test:
	$(VENV)/python -m unittest discover -s tests -v
	$(MONITOR)/python -m unittest discover -s tests -p test_monitor_delivery.py -v
