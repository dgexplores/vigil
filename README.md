# Vigil | AI-assisted Transaction Investigation

Maintainer namespace: **dgexplores**. Local implementation and regression checks pass; live cloud deployment is pending. See the [reconstruction ledger](docs/RECONSTRUCTION.md) and [CI/CD instructions](docs/CI_CD.md).

Python services that connect transaction monitoring, PostgreSQL queries, and Gemini-assisted investigation in a banking demonstration environment.

This portfolio adaptation focuses on Python backend development, operational automation, REST APIs, SQL, and cloud deployment concepts. It builds on [Vigil by ayanliger and its contributors](https://github.com/ayanliger/gke-turns10-hackathon-vigil). Original source attribution and license notices are retained. See [contributions](PORTFOLIO.md) for the scope of this adaptation.

## Problem and approach

Operations teams need context when reviewing suspicious transactions. Vigil demonstrates a workflow that flags high-value transactions, gathers account history, requests an LLM risk assessment, and can invoke an account update through a separate actuator service.

The initial flag is a configurable amount rule. This is an AI-assisted automation prototype, not a trained fraud classifier or a validated production banking control.

## Request flow

```text
PostgreSQL → database toolbox → Python transaction monitor
                                    ↓ A2A message
                             Orchestrator / Gemini
                                    ↓
                             Investigation agent
                                    ↓
                          Risk assessment and decision
                                    ↓
                         Actuator → database toolbox
```

## Implementation

| Component | Responsibility | Source |
|---|---|---|
| Transaction monitor | Poll transactions, apply amount threshold, dispatch alerts | [agent.py](vigil-system/transaction_monitor_agent/agent.py) |
| Orchestrator | Coordinate investigation and enforcement requests | [agent.py](vigil-system/orchestrator_agent/agent.py) |
| Investigation agent | Retrieve context and generate risk assessment | [agent.py](vigil-system/investigation_agent/agent.py) |
| Actuator | Handle enforcement requests | [agent.py](vigil-system/actuator_agent/agent.py) |
| Database toolbox | Expose parameterized PostgreSQL operations | [tools.yaml](vigil-system/genal_toolbox/tools.yaml) |

Stack: Python, asyncio, FastAPI, HTTPX, Google ADK, Gemini, A2A SDK, PostgreSQL, Docker, and Google Kubernetes Engine. The toolbox wraps an external Go binary; it is not evidence of original Go development in this adaptation.

## Setup and deployment

Deployment requires a Google Cloud project, billing, a GKE cluster, Docker, kubectl, and a compatible Bank of Anthos deployment. Cloud commands can create billable resources.

1. Initialize the banking submodule if needed: `git submodule update --init --recursive`.
2. Deploy the compatible Bank of Anthos application using its own instructions.
3. Create the Gemini configuration from `vigil-system/gemini-api-key-secret.yaml.example`; keep the populated secret out of version control.
4. Build the five images using the component Dockerfiles, using the contexts recorded in `.github/workflows/ci.yml` (the investigation agent and toolbox use their component directories).
5. Replace the original project image references in the deployment YAML with your own Artifact Registry image references.
6. Review the PostgreSQL schema and both toolbox configuration files before applying manifests. They include sample database credentials and schema assumptions.
7. Apply the secret, toolbox ConfigMap, and ledger migration; wait for its Job to complete before starting agents. Apply the monitor PVC and component manifests. Both database configurations must match your demonstration databases.

For example, build the orchestrator from the repository root:

```bash
docker build -f vigil-system/orchestrator_agent/Dockerfile -t vigil-orchestrator:local .
```

This builds one component only; it does not deploy or validate the complete system.

| Setting | Default | Purpose |
|---|---|---|
| `FRAUD_THRESHOLD` | `1000.0` | Transaction amount flag threshold in cents |
| `POLL_INTERVAL` | `5` | Polling interval in seconds |
| `RISK_SCORE_THRESHOLD` | `7` | Investigation escalation threshold |
| `GEMINI_API_KEY` | Required | Model access for LLM agents |
| `MONITOR_STATE_PATH` | `data/monitor.sqlite3` | Durable outbox and cursor path; `/data/monitor.sqlite3` in Kubernetes |
| `MONITOR_START_TIMESTAMP` | Unix epoch in UTC | Initial poll lower bound for a new state database |

## Verification and limitations

This adaptation includes implementation changes and offline regression tests for durable alert delivery and service policy enforcement. See the reconstruction ledger for evidence and limitations. Cloud deployment, live model evaluation, and throughput benchmarks remain unverified.

Before presenting an end-to-end demo, verify transaction retrieval, investigation responses, below-threshold behavior, actuator behavior, and banking enforcement separately. Use synthetic accounts and record the actual results.

The monitor now uses a durable SQLite outbox and polling cursor. Apply the additive ledger migration before starting agents to enforce account locks on future local outgoing transactions. Run one monitor replica with the supplied PVC. Delivery is at-least-once; older late-arriving transactions and large polling batches need further work. Fraud precision, recall, and false-positive rates have not been established here.

## Portfolio material

- [Reproduce local tests](docs/LOCAL_VERIFICATION.md)
- [Contribution record and role alignment](PORTFOLIO.md)
- [Interview preparation and improvement plan](docs/INTERVIEW_GUIDE.md)

## Attribution and license

Original project: [ayanliger/gke-turns10-hackathon-vigil](https://github.com/ayanliger/gke-turns10-hackathon-vigil), developed for the GKE Turns 10 Hackathon. Hackathon recognition belongs to the original project and participants.

The repository includes an [MIT license](LICENSE); individual files also retain their existing notices. The Bank of Anthos submodule has its own provenance and licensing.

Dependency review: dependency upgrades and the single mitigated upstream tracing advisory are documented in [DEPENDENCY_REVIEW.md](docs/DEPENDENCY_REVIEW.md). Passing functional tests is not a production security assessment.

Quick verification: with Python 3.11 and Make installed, run `make install` then `make test`. The PostgreSQL contract is explicitly skipped unless `TEST_POSTGRES_DSN` points to a disposable test database. See [deployment readiness](docs/DEPLOYMENT_READINESS.md) for routes and account prerequisites.
