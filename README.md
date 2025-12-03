# Vigil AI Fraud Shield

[![Status](https://img.shields.io/badge/Status-Completed-success?style=flat-square)](https://github.com/ayanliger/gke-turns10-hackathon-vigil)
[![Hackathon](https://img.shields.io/badge/GKE%20Turns%2010-Honorable%20Mention-blue?style=flat-square&logo=google-cloud)](https://github.com/ayanliger/gke-turns10-hackathon-vigil)
[![Demo](https://img.shields.io/badge/Demo-YouTube-red?style=flat-square&logo=youtube)](https://www.youtube.com/watch?v=S7xQgOoeFOw)
[![License](https://img.shields.io/badge/License-MIT-yellow?style=flat-square)](LICENSE)

[![Google Cloud](https://img.shields.io/badge/Google%20Cloud-GKE-4285F4?style=flat-square&logo=google-cloud&logoColor=white)](https://cloud.google.com/kubernetes-engine)
[![Gemini](https://img.shields.io/badge/Gemini-2.5%20Flash-8E75B2?style=flat-square&logo=google&logoColor=white)](https://ai.google.dev/)
[![Python](https://img.shields.io/badge/Python-3.11-3776AB?style=flat-square&logo=python&logoColor=white)](https://python.org)
[![Go](https://img.shields.io/badge/Go-1.23-00ADD8?style=flat-square&logo=go&logoColor=white)](https://go.dev)

**Vigil** is a proactive, hierarchical multi-agent system that enhances the security of microservice-based financial applications. It uses agentic AI to detect and mitigate financial fraud in real-time.

> 🏆 **Honorable Mention** — GKE 10th Birthday Hackathon (LATAM Region)

📺 [**Watch the Demo**](https://www.youtube.com/watch?v=S7xQgOoeFOw) · 📦 [**View Repository**](https://github.com/ayanliger/gke-turns10-hackathon-vigil)

## Architecture Overview

Vigil is a decoupled multi-agent system where a central **Orchestrator Agent** coordinates specialized agents for monitoring, investigation, and enforcement. The system integrates with the [Bank of Anthos](https://github.com/GoogleCloudPlatform/bank-of-anthos) sample banking application.

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              VIGIL SYSTEM                                   │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│   ┌──────────────────┐         A2A          ┌──────────────────────┐        │
│   │  Transaction     │ ───────────────────► │    Orchestrator      │        │
│   │  Monitor Agent   │                      │    Agent             │        │
│   │                  │                      │                      │        │
│   │  (Python/asyncio)│                      │  (ADK LlmAgent +     │        │
│   └────────┬─────────┘                      │   Gemini 2.5 Flash)  │        │
│            │                                └───────────┬──────────┘        │
│            │ REST                                 A2A   │   A2A             │
│            │                           ┌────────────────┴────────┐          │
│            ▼                           ▼                         ▼          │
│   ┌──────────────────┐       ┌──────────────────┐     ┌─────────────────┐   │
│   │  GenAI Toolbox   │       │  Investigation   │     │  Actuator       │   │
│   │  Service         │◄──────│  Agent           │     │  Agent          │   │
│   │                  │ REST  │                  │     │                 │   │
│   │  (Go binary)     │◄──────│  (ADK LlmAgent)  │     │  (FastAPI)      │   │
│   │                  │       └──────────────────┘     └────────┬────────┘   │
│   │                  │                                         │ REST       │
│   │                  │◄────────────────────────────────────────┘            │
│   └────────┬─────────┘                                                      │
│            │                                                                │
│            │ PostgreSQL                                                     │
│            ▼                                                                │
│   ┌──────────────────────────────────────┐                                  │
│   │  Bank of Anthos Databases            │                                  │
│   │  (accounts-db, ledger-db)            │                                  │
│   └──────────────────────────────────────┘                                  │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

## Components

| Component | Technology Stack | Description |
|-----------|------------------|-------------|
| **Transaction Monitor** | Python, asyncio, A2A SDK | Continuously polls the ledger database for new transactions. Flags high-value transactions and sends alerts to the Orchestrator via A2A protocol. |
| **Orchestrator Agent** | Google ADK (LlmAgent), Gemini 2.5 Flash, FastAPI, A2A | Central coordinator. Uses an LLM to analyze alerts, delegate investigations, compute risk scores, and decide on enforcement actions. |
| **Investigation Agent** | Google ADK (LlmAgent), Gemini 2.5 Flash, FastAPI, A2A | Gathers context about flagged transactions (user profile, transaction history) and produces a risk assessment with justification. |
| **Actuator Agent** | FastAPI, A2A SDK | Executes enforcement actions (e.g., account locking) by invoking tools on the GenAI Toolbox. |
| **GenAI Toolbox** | Go binary, REST API, PostgreSQL | Provides secure, pre-defined database operations as REST endpoints. Agents invoke tools like `get_user_details`, `lock_account`, etc. |

## Key Features

- **Hierarchical Multi-Agent System**: Specialized agents with clear separation of concerns, coordinated by a central orchestrator.
- **LLM-Powered Decision Making**: The Orchestrator and Investigation agents use Gemini to reason about fraud risk.
- **Risk-Gated Enforcement**: Actions are only taken when investigation risk scores exceed a configurable threshold.
- **A2A Protocol**: Inter-agent communication follows the Agent-to-Agent protocol for structured message passing.
- **Non-Invasive Integration**: Vigil monitors and protects Bank of Anthos without modifying its core application code.

## Detection Flow

1. **Monitor**: Transaction Monitor detects a high-value transaction (default threshold: $1,000)
2. **Alert**: Sends A2A message to Orchestrator with transaction details
3. **Investigate**: Orchestrator delegates to Investigation Agent, which queries user profile and history
4. **Assess**: Investigation Agent uses Gemini to produce a risk score (0-10) with justification
5. **Decide**: Orchestrator evaluates risk score against threshold (default: 7)
6. **Act**: If threshold exceeded, Orchestrator commands Actuator to lock the account

## Deployment

### Prerequisites

- Google Cloud project with billing enabled
- GKE cluster
- `kubectl` configured for your cluster
- Docker installed locally
- Bank of Anthos deployed to the cluster

### Quick Start

```bash
# 1. Configure Gemini API key
cp vigil-system/gemini-api-key-secret.yaml.example vigil-system/gemini-api-key-secret.yaml
# Edit the file with your actual API key

# 2. Set up environment
export PROJECT_ID=$(gcloud config get-value project)
export REGION="us-central1"
export REPO="vigil-repo"
export IMAGE_PREFIX="${REGION}-docker.pkg.dev/${PROJECT_ID}/${REPO}"

# 3. Create Artifact Registry repository
gcloud artifacts repositories create vigil-repo \
    --repository-format=docker \
    --location=$REGION

# 4. Configure Docker authentication
gcloud auth configure-docker ${REGION}-docker.pkg.dev

# 5. Build and push images
docker build -t "${IMAGE_PREFIX}/genal-toolbox:latest" -f vigil-system/genal_toolbox/Dockerfile .
docker build -t "${IMAGE_PREFIX}/transaction-monitor-agent:latest" -f vigil-system/transaction_monitor_agent/Dockerfile .
docker build -t "${IMAGE_PREFIX}/orchestrator-agent:latest" -f vigil-system/orchestrator_agent/Dockerfile .
docker build -t "${IMAGE_PREFIX}/investigation-agent:latest" -f vigil-system/investigation_agent/Dockerfile .
docker build -t "${IMAGE_PREFIX}/actuator-agent:latest" -f vigil-system/actuator_agent/Dockerfile .

docker push "${IMAGE_PREFIX}/genal-toolbox:latest"
docker push "${IMAGE_PREFIX}/transaction-monitor-agent:latest"
docker push "${IMAGE_PREFIX}/orchestrator-agent:latest"
docker push "${IMAGE_PREFIX}/investigation-agent:latest"
docker push "${IMAGE_PREFIX}/actuator-agent:latest"

# 6. Deploy to GKE
kubectl apply -f vigil-system/gemini-api-key-secret.yaml
kubectl apply -f vigil-system/genal_toolbox/toolbox-configmap.yaml
kubectl apply -f vigil-system/genal_toolbox/
kubectl apply -f vigil-system/transaction_monitor_agent/
kubectl apply -f vigil-system/orchestrator_agent/
kubectl apply -f vigil-system/investigation_agent/
kubectl apply -f vigil-system/actuator_agent/

# 7. Verify
kubectl get pods
```

### Configuration

| Environment Variable | Component | Default | Description |
|---------------------|-----------|---------|-------------|
| `FRAUD_THRESHOLD` | Transaction Monitor | 1000.0 | Minimum transaction amount to flag |
| `POLL_INTERVAL` | Transaction Monitor | 5 | Seconds between ledger polls |
| `RISK_SCORE_THRESHOLD` | Orchestrator | 7 | Minimum risk score to trigger enforcement |
| `GEMINI_API_KEY` | Orchestrator, Investigation | — | Required for LLM agents |

## Observing the System

```bash
# Watch all Vigil pods
kubectl get pods -w

# Stream logs from specific agents
kubectl logs -f deployment/transaction-monitor-agent
kubectl logs -f deployment/orchestrator-agent
kubectl logs -f deployment/investigation-agent
kubectl logs -f deployment/actuator-agent
```

## Future Improvements

- [ ] **True MCP Integration**: Replace REST calls to GenAI Toolbox with proper MCP protocol
- [ ] **Streaming Investigation**: Use streaming responses for real-time investigation updates
- [ ] **Enhanced Fraud Rules**: Implement velocity checks, geographic anomaly detection, behavioral patterns
- [ ] **Observability**: Add OpenTelemetry tracing across agent communications
- [ ] **Human-in-the-Loop**: Add approval workflow for high-stakes enforcement actions
- [ ] **Feedback Loop**: Allow marking false positives to improve risk scoring over time
- [ ] **Multi-Cluster Support**: Deploy agents across regions for resilience

## Technology Stack

- **Runtime**: Python 3.11, Go
- **AI/ML**: Google ADK, Gemini 2.5 Flash
- **Communication**: A2A Protocol (a2a-sdk), REST APIs
- **Infrastructure**: Google Kubernetes Engine (GKE), Artifact Registry
- **Databases**: PostgreSQL (via Bank of Anthos)
- **Frameworks**: FastAPI, uvicorn

## License

MIT License — see [LICENSE](LICENSE) for details.

## Acknowledgements

Developed for the **GKE 10th Birthday Hackathon**. Thanks to the Google Cloud team for the excellent SDKs and infrastructure that made this project possible.
