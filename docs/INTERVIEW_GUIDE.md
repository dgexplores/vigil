# Vigil: Interview Guide

Trace one transaction from PostgreSQL through Toolbox, monitor, A2A, ADK investigation, risk policy, actuator, and database enforcement.

Explain these new engineering choices:

1. An atomic cursor and outbox prevent fetched alerts being lost when dispatch fails.
2. Inclusive timestamps plus transaction IDs handle repeated boundary rows.
3. A stable message ID helps correlation but does not establish exactly-once delivery.
4. Policy validation must constrain model tool calls before account locking.
5. An affected database row verifies the lock, while a database trigger enforces future outgoing transfers.
6. Unit/ASGI tests, PostgreSQL contract tests, container builds, hosted CI runs, and cloud deployment each prove different things.

Review [the reconstruction ledger](RECONSTRUCTION.md) for limits and [the CI/CD guide](CI_CD.md) for deployment gates. Describe this as an extension of the attributed original project, and distinguish your understanding of inherited components from the added implementation.
