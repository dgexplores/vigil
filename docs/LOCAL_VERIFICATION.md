# Reproduce local verification

These checks run on synthetic data and do not call Google Cloud or Gemini.
Run the Python commands from this repository root using Python 3.11.

```bash
python3.11 -m venv .venv
.venv/bin/python -m pip install \
  -r vigil-system/transaction_monitor_agent/requirements.txt \
  -r vigil-system/orchestrator_agent/requirements.txt \
  -r vigil-system/investigation_agent/requirements.txt \
  -r vigil-system/actuator_agent/requirements.txt
.venv/bin/python -m unittest discover -s tests -v
```

Without PostgreSQL configuration, the database contract test is explicitly
skipped. To run it as well, start a disposable PostgreSQL 17 instance. The
following local-only password is demonstration data, not a cloud credential:

```bash
.venv/bin/python -m pip install 'psycopg[binary]==3.2.6'
docker run --name vigil-test-db --rm -d \
  -p 127.0.0.1:55432:5432 \
  -e POSTGRES_PASSWORD=local-test-only postgres:17-alpine
docker exec vigil-test-db pg_isready -U postgres
TEST_POSTGRES_DSN=postgresql://postgres:local-test-only@127.0.0.1:55432/postgres \
  .venv/bin/python -m unittest discover -s tests -v
docker rm -f vigil-test-db
```

Wait until `pg_isready` reports ready before running the test. The contract
creates its own randomly named schema and removes it afterward. It verifies
the actual Bank of Anthos ledger schema, repeatable migration, timestamp
conversion, rejected locked-sender insert, and unaffected other senders.
Do not aim the test at a real banking database.

Local results recorded on 22 October 2026: 24 tests passed with PostgreSQL
17 enabled. Four agent images and pinned Go Toolbox built successfully.
Four Go Toolbox HTTP tools and a running actuator-to-toolbox-to-PostgreSQL
lock operation also passed using synthetic data. Built model service
constructors initialized without live model calls.

The Docker builds were Linux ARM64 local builds. GitHub-hosted AMD64 jobs,
GKE rollout, and Gemini inference have not been observed in this work session.
