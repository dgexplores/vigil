# Vigil service architecture and verification

This reconstruction uses the available Python source, not binary decompilation. The REA skill routes complete source repositories to ordinary repository analysis. The existing Google ADK/Gemini, A2A, GenAI Toolbox, PostgreSQL, and GKE design remains in place.

## Observed interfaces

| Service | Endpoint | Request / behavior |
| --- | --- | --- |
| Orchestrator | `POST /`, `POST /a2a/send-message` | A2A JSON-RPC `message/send`, text `Process transaction alert: <transaction JSON>` |
| Investigation | `POST /`, `POST /a2a/send-message` | A2A text `investigate_transaction: <transaction JSON>` |
| Investigation | `POST /investigate` | Transaction object, including `from_account_id`; returns case file or error |
| Actuator | `POST /`, `POST /a2a/send-message` | A2A text `execute_action: <command JSON>` |
| Actuator | `POST /execute` | `{ "action": "lock_account", "account_id": "..." }`; returns application success/error |
| All three | `GET /health` | Reports service initialization; 503 before initialization |

Successful A2A transport envelopes can contain application errors. Callers must inspect the embedded response: an orchestrator result must have `status: completed`, an actuator result must have `status: success`. Neither HTTP 200 nor a JSON-RPC result alone establishes a successful action.

## Working flow

1. The monitor sends a suspicious transaction to the orchestrator.
2. The orchestrator's Gemini agent invokes the investigation delegation tool through A2A.
3. Investigation reads the account profile and transaction history through GenAI Toolbox, invokes Gemini, validates the returned finite risk score (0–10) and non-empty justification, and returns the complete case file.
4. The orchestrator's actuator delegation wrapper enforces the threshold and account identity independently of the model's instructions. It uses the investigation result for the current request, never a model-supplied replacement case file.
5. The actuator invokes the `lock_account` Toolbox tool with `account_id`, and only reports success after receiving a row confirming that account. The bank ledger migration provides the actual account-lock enforcement.
6. If the model omits a required high-risk action, the orchestrator performs the existing fallback delegation. Failed or absent required action produces application `status: error` for retry by the monitor.

## Source-backed repairs

- Replaced the process-global latest case file with request-isolated context. Concurrent customers cannot inherit another request's case file.
- Added deterministic risk, account-match, duplicate-success and concurrent in-flight checks around the model's actuator tool.
- Distinguished nested actuator application errors from transport success. Incomplete high-risk processing is no longer acknowledged as completed.
- Made investigation context failures explicit instead of treating unavailable database tools as empty history.
- Validated model score/justification and rejected non-object command JSON.
- Accepted prefixed A2A JSON with or without whitespace after the colon.
- Made initialization failures exit unsuccessfully and readiness fail before service initialization.

## Verification and boundaries

`tests/test_agent_services.py` uses the actual FastAPI, A2A SDK and ADK imports with HTTP requests through ASGI. It substitutes model-runner and Toolbox results; it does not call Gemini or cloud services.

Covered behaviors: concurrent request isolation; invalid, below-threshold and mismatched-account action rejection; duplicate successful actuation rejection; confirmed versus empty lock updates; valid and malformed model assessments; context failure; high/low-risk orchestration through real JSON-RPC serialization; and failed high-risk actuation status.

Run from the repository root after installing `requirements-ci.txt`:

```bash
python -m unittest discover -s tests
```

The offline tests establish these contracts, not successful GKE deployment, model quality, or end-to-end live fraud prevention. Cross-process action auditing and distributed exactly-once delivery remain outside the request-local orchestration guard; account locking itself is designed to be idempotent at the database layer.
