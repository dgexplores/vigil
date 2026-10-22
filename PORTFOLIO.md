# Vigil: Engineering Contributions

Maintainer namespace: dgexplores. Based on the attributed upstream Vigil application.

## Added in this build

- SQLite outbox and atomic polling checkpoint, retry after restart, duplicate suppression, and stable alert IDs.
- Inclusive UTC-aware PostgreSQL polling contract.
- Additive ledger table/trigger that rejects transfers from locked local accounts.
- Request-isolated investigation state, deterministic risk/account checks, and database-confirmed actuation.
- Tested SDK version pins, regression tests, container packaging, and gated GKE CI/CD.

See [reconstruction and test boundaries](docs/RECONSTRUCTION.md), [service evidence](docs/SERVICE_EVIDENCE.md), and [pipeline instructions](docs/CI_CD.md).

## Resume wording after reviewing and understanding this build

> Extended a Python AI-agent transaction investigation application with persistent alert delivery, duplicate suppression, SQL-based transfer enforcement, and automated regression tests.

The upstream application and its hackathon recognition remain credited to their original authors. No live deployment, model-quality metric, or full original authorship is claimed.
