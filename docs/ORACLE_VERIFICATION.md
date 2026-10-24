# Oracle cloud verification — 24 October 2026

Live banking demo: https://vigil-161-118-164-31.sslip.io/login

This is a single-host Docker Compose adaptation on an existing Oracle Always
Free A1 ARM VM (1 OCPU / 6 GB RAM), rather than a deployed GKE cluster. The
original GKE files remain available. The Gemini key's project was inspected
through Google APIs and reported `billingEnabled=false`. No paid upgrade was
selected. Model capacity and free-tier quotas can still limit availability.

Automated release: [all CI jobs and Oracle deployment passed](https://github.com/dgexplores/vigil/actions/runs/40063802734), application revision `912989c08167984e5767b3acb6beda8cda56300f`.

## Observed release checks

- Public DNS resolved to the VM, Caddy obtained a Let's Encrypt certificate,
  and HTTPS `/login` returned 200 with certificate verification enabled.
- Actual browser login with upstream fictional `testuser` / `bankofanthos`
  opened `/home`, with a rendered balance and transaction history.
- Eight bank services, two databases (included in those eight), Toolbox, Caddy,
  three AI services and the monitor run in separate containers. Agent/database
  APIs have no public host port. All defined health checks passed.
- `verify.py --agents` checked running service health, bank login/home routing,
  and actual PostgreSQL trigger rejection with rolled-back probe data.
- Live Gemini investigation retrieved a fictional account profile and its recent
  ledger history through Toolbox and returned a validated risk assessment.
- Synthetic transaction 62 triggered monitor → orchestrator → investigation →
  actuator → ledger lock. A later outgoing insert from that sender was rejected
  by the actual PostgreSQL check-violation guard.
- During the next synthetic alert, the monitor was stopped before saving its
  acknowledgement. Its durable outbox retained transaction 64 as pending. On
  restart it retried, confirmed the idempotent lock, and persisted delivery.
- The second completed orchestration described 150000 cents as **$1,500.00**,
  following an explicit correction to both agents' unit instructions.
- The monitor then reported two delivered alerts and zero pending alerts.
- Restarting both databases and the monitor preserved 62 transactions, two locks, and both delivered outbox records. The first login after restart passed after enabling SQLAlchemy connection pre-ping in the Oracle build.
- The automated rollout recreated the services from the selected GitHub revision and passed bank, agent, ledger and public HTTPS checks. The original ADYA application directories were then removed after rechecking their local backup checksum; the unused Ollama service was stopped and disabled.

These are controlled integration checks, not evidence of measured fraud
accuracy. The destination and transaction patterns were deliberately synthetic;
model language claiming fraud or an unauthorized transfer is an assessment,
not proof. An account lock blocks future local outgoing ledger inserts; it does
not reverse an earlier transfer or disable the banking login.

## Model and build choices

Gemini 3.8 Flash returned a temporary 503 high-demand error. The verified demo
uses Gemini 3.5 Flash-Lite, which the key can access and which currently has a
free tier. The model is configurable through the private agent environment.

Native Java source builds exposed an upstream transaction-history executable
JAR class-name typo. The Oracle Dockerfile corrects that name during packaging.
Explicit hyphenated hostnames satisfy the upstream metric-label parser while
cloud metrics/tracing exports remain disabled. The pinned submodule is retained.

The ordinary CI suite tests the Python services, packaged monitor, actual
PostgreSQL schema/lock contract and dependency audits. The separate ARM suite
builds all banking/agent images and starts the real bank stack before checking
login routing and enforcement. Neither hosted suite invokes live Gemini.

Oracle continuous delivery reruns both suites before deployment, uses pinned
SSH host verification and a dedicated key, and preserves state/volumes outside
revision directories. The workflow result, rather than this file's existence,
establishes whether an automated rollout completed.

## Limits

This demo has one host and no high availability or production load evaluation.
The host can be reclaimed under Oracle's Free Tier policy. Agent APIs are
internal; there is no separate public AI chat or investigation dashboard.
At-least-once processing can repeat a remote action after a crash. The account
lock is idempotent; there is no distributed exactly-once claim. Use only fictional
data and check deployment/model quotas before extending the workload.
