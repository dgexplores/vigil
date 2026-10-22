# Source reconstruction and verification ledger

Maintainer namespace: `dgexplores`. This is a technical work record, not a deployed-product or original-authorship claim.

## Baseline identity

- Vigil baseline: `d363d942bac59a31fa196422c020d5ca4e58f72f` from `ayanliger/gke-turns10-hackathon-vigil`.
- Original banking submodule pointed to an unavailable personal repository. Replacement: Google's Bank of Anthos at `db35fea9fd090150e2398106aadb475576f80d94`.
- No binary decompilation was needed: the supplied reverse-engineer-anything skill routes complete source repositories to normal source tools.

## Architecture retained

PostgreSQL ledger → Go GenAI Toolbox REST API → Python monitor → A2A orchestrator → Gemini/ADK investigation → A2A actuator → database lock operation. Docker images and Kubernetes manifests target GKE. Offline tests stub the model and downstream requests; they do not replace the cloud architecture.

## Observations and repairs

| ID | Source observation | Change / evidence |
|---|---|---|
| V1 | Unpinned a2a-sdk installed 1.2.3, which lacks `a2a.client.legacy` | Pin tested 0.3.10; actual SDK imports and HTTP schema tests |
| V2 | Monitor cursor was in memory and advanced despite alert failures | SQLite cursor/outbox committed together; restart/retry tests |
| V3 | `timestamp > cursor` loses new boundary rows | Inclusive timestamp query plus transaction ID deduplication |
| V4 | Bank ledger stores timestamp without timezone | Explicit SQL UTC conversion and aware cursor normalization |
| V5 | Account lock SQL named nonexistent user_info/ext_user_id fields | Ledger lock table and database trigger migration |
| V6 | Actuator reported success without checking a database row | Matching returned account row required |
| V7 | Orchestrator investigation context was global mutable state | Request context and original-transaction enforcement |
| V8 | Model could invoke actuator below threshold | Deterministic finite-score/account policy checked before delegation |

## New processing contract

The outbox stores every observed transaction ID, keeping high-value items pending until an application-level completed acknowledgement. Failed polls do not block retries of saved items. Delivered IDs suppress ordinary duplicate polls. Retried alerts use a stable message ID.

This is at-least-once delivery, not exactly-once execution: a crash after a remote action but before local acknowledgement can repeat the action. Lock upserts are idempotent; no general downstream deduplication is claimed. Run one monitor with the mounted persistent volume. Late-arriving rows older than the cursor, unbounded history retention, and large historical polling need further design.

Amounts in Bank of Anthos are integer cents. `FRAUD_THRESHOLD=1000` means 1000 cents, not $1000; configure 100000 for a $1000 threshold. The added ledger guard applies to local routing number `883745000`; change the migration deliberately if using another routing number. Account locking prevents future local outgoing ledger inserts; it does not reverse transactions or disable login.

## Verification boundaries

25 regression tests passed locally with real PostgreSQL 17 enabled, including monitor delivery, A2A endpoint contracts, policy enforcement, and database trigger behavior. The Go Toolbox 0.16.0 container also passed four real HTTP tool calls against synthetic PostgreSQL data using `scripts/check_local_toolbox.py`. A running actuator container called that real Toolbox and confirmed a PostgreSQL lock upsert. Orchestrator and investigation constructors initialized inside their built containers using a synthetic key without making model calls. Unit and ASGI model tests use fake model responses. PostgreSQL contract checks require `TEST_POSTGRES_DSN`; they create and remove a uniquely named test schema. No Google Cloud billing project or Gemini key has been configured in this work session. GKE deployment and live model quality remain unverified.

The recruiter-facing README now explains the workflow and verified contributions. A public live-application URL remains pending until an actual deployment is verified. No billable cloud resources may be created under the current ₹0 spending constraint.
