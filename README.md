# Vigil AI Fraud Shield

Vigil is a proactive, hierarchical multi-agent system that enhances the security of microservice-based financial applications. It uses agentic AI to detect and mitigate financial fraud in real-time. This project was developed for the Google Kubernetes Engine (GKE) 10th Birthday Hackathon.

## Key Features

*   **Hierarchical Multi-Agent System:** A sophisticated architecture with specialized agents for monitoring, investigation, and action, all coordinated by a central orchestrator.
*   **Proactive Fraud Detection:** The system continuously monitors transactions to identify and mitigate potential fraud before it can cause harm.
*   **Risk-Gated Enforcement:** The Orchestrator uses investigation results to compute a risk score and only escalates to the Actuator Agent when a configurable threshold is exceeded.
*   **Secure Data Access:** The **GenAl Toolbox** provides a secure bridge to the application's databases, exposing only the necessary data through a well-defined API.
*   **Seamless Integration:** The Vigil System interacts with the existing Bank of Anthos application through its APIs, demonstrating how agentic AI can enhance legacy systems without modifying their core code.

## Architecture

The Vigil architecture is a decoupled and secure Hierarchical Multi-Agent System. A central **Orchestrator Agent** manages the workflow, delegating tasks to specialized agents. The system interfaces with the Bank of Anthos application's databases through the **GenAl Toolbox**, which acts as a secure data access layer.

### Architectural Diagram

<img width="3840" height="1848" alt="vigil_system _ Mermaid Chart-2025-09-22-203418" src="https://github.com/user-attachments/assets/c99292af-76db-4fe7-8318-88c514952b66" />

### Component Roles & Responsibilities

| Component                | Technology/Protocol       | Role & Responsibility                                                                                                                                                           |
| :----------------------- | :------------------------ | :------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| **Orchestrator Agent**   | FastAPI + A2A             | The system's central "brain." Receives alerts, runs rule-based orchestration, and delegates to the Investigation and Actuator agents when risk thresholds are exceeded.        |
| **TransactionMonitor Agent** | ADK (Loop or CustomAgent) | The system's sensor. Continuously monitors the Ledger DB for new transactions, flags anomalies, and initiates an investigation via an A2A call to the Orchestrator.            |
| **Investigation Agent**  | ADK (LlmAgent with Gemini) | The digital detective. Gathers comprehensive context on a flagged transaction using various database tools. Synthesizes findings into a "case file" for review.               |
| **Actuator Agent**       | ADK (CustomAgent)         | The enforcement arm. Receives validated commands from the Orchestrator and executes actions (e.g., locking an account) by invoking tools on the GenAl Toolbox.                   |
| **GenAl Toolbox Service**| GenAl Toolbox (Go binary) | The secure MCP server. Connects to both Bank of Anthos databases and exposes pre-defined SQL queries as "tools" for the agents to consume.                                       |

## Getting Started

Before you can deploy the Vigil AI Fraud Shield, you need to have the following prerequisites in place:

*   **Google Cloud Project:** A Google Cloud project with billing enabled.
*   **GKE Cluster:** A running GKE cluster in your project.
*   **kubectl:** The `kubectl` command-line tool configured to connect to your GKE cluster.
*   **gcloud CLI:** The `gcloud` command-line tool authenticated to your Google Cloud project.
*   **Docker:** Docker installed and running on your local machine.

### Bank of Anthos

The Vigil system is designed to protect the **Bank of Anthos** application, a sample web-based banking application. You must deploy the Bank of Anthos to your GKE cluster before deploying Vigil.

For instructions on how to deploy the Bank of Anthos, please refer to the official Google Cloud repository: [https://github.com/GoogleCloudPlatform/bank-of-anthos](https://github.com/GoogleCloudPlatform/bank-of-anthos)

## Deployment Guide

Follow these steps to deploy the Vigil AI Fraud Shield to your GKE cluster.

### 1. Configure the Gemini API Key

Create a Kubernetes secret for your Gemini API key.

1.  Copy the example file:
    ```bash
    cp vigil-system/gemini-api-key-secret.yaml.example vigil-system/gemini-api-key-secret.yaml
    ```
2.  Edit `vigil-system/gemini-api-key-secret.yaml` and replace the placeholder with your actual Gemini API key.

### 2. Create Artifact Registry Repository

Create a repository in Google Artifact Registry to store the container images for the Vigil system.

```bash
gcloud artifacts repositories create vigil-repo \
    --repository-format=docker \
    --location=us-central1 \
    --description="Repository for Vigil AI Fraud Shield images"
```
*Note: You can replace `us-central1` with the region of your choice.*

### 3. Configure Docker Authentication

Configure Docker to use your Google Cloud credentials to authenticate with Artifact Registry.

```bash
gcloud auth configure-docker us-central1-docker.pkg.dev
```

### 4. Build and Push Container Images

Run these commands from the root of the repository to build and push the images for each service.

```bash
# Define variables
export PROJECT_ID=$(gcloud config get-value project)
export REGION="us-central1"
export REPO="vigil-repo"
export IMAGE_PREFIX="${REGION}-docker.pkg.dev/${PROJECT_ID}/${REPO}"

# Build and push images for each agent and the GenAl Toolbox
docker build -t "${IMAGE_PREFIX}/genal-toolbox:latest" -f vigil-system/genal_toolbox/Dockerfile .
docker push "${IMAGE_PREFIX}/genal-toolbox:latest"

docker build -t "${IMAGE_PREFIX}/transaction-monitor-agent:latest" -f vigil-system/transaction_monitor_agent/Dockerfile .
docker push "${IMAGE_PREFIX}/transaction-monitor-agent:latest"

docker build -t "${IMAGE_PREFIX}/orchestrator-agent:latest" -f vigil-system/orchestrator_agent/Dockerfile .
docker push "${IMAGE_PREFIX}/orchestrator-agent:latest"

docker build -t "${IMAGE_PREFIX}/investigation-agent:latest" -f vigil-system/investigation_agent/Dockerfile .
docker push "${IMAGE_PREFIX}/investigation-agent:latest"

docker build -t "${IMAGE_PREFIX}/actuator-agent:latest" -f vigil-system/actuator_agent/Dockerfile .
docker push "${IMAGE_PREFIX}/actuator-agent:latest"
```

### 5. Deploy the Application

Apply the Kubernetes manifests to your GKE cluster in the following order:

```bash
# 1. Apply the Secret and ConfigMap
kubectl apply -f vigil-system/gemini-api-key-secret.yaml
kubectl apply -f vigil-system/genal_toolbox/toolbox-configmap.yaml

# 2. Apply the Deployments and Services for each component
# GenAl Toolbox
kubectl apply -f vigil-system/genal_toolbox/genal_toolbox_deployment.yaml
kubectl apply -f vigil-system/genal_toolbox/genal_toolbox_service.yaml

# TransactionMonitor Agent
kubectl apply -f vigil-system/transaction_monitor_agent/transaction_monitor_agent_deployment.yaml

# Orchestrator Agent
kubectl apply -f vigil-system/orchestrator_agent/orchestrator_agent_deployment.yaml
kubectl apply -f vigil-system/orchestrator_agent/orchestrator_agent_service.yaml

# Investigation Agent
kubectl apply -f vigil-system/investigation_agent/investigation_agent_deployment.yaml
kubectl apply -f vigil-system/investigation_agent/investigation_agent_service.yaml

# Actuator Agent
kubectl apply -f vigil-system/actuator_agent/actuator_agent_deployment.yaml
kubectl apply -f vigil-system/actuator_agent/actuator_agent_service.yaml
```

### 6. Verify the Deployment

Check the status of the pods to ensure they are all running correctly.

```bash
kubectl get pods
```
You should see output similar to this:
```
NAME                                            READY   STATUS    RESTARTS   AGE
actuator-agent-594bb8b5d5-z6j6c                 1/1     Running   0          10m
genal-toolbox-589b9b8c5c-6j5x6                  1/1     Running   0          10m
investigation-agent-5c4f8f8b8d-n9x5g             1/1     Running   0          10m
orchestrator-agent-5d4b8b8b8d-6x2g4              1/1     Running   0          10m
transaction-monitor-agent-5f4g8g8b8d-5g5g2       1/1     Running   0          10m
```

## Usage and Observation

Once deployed, the Vigil System will automatically begin monitoring the Bank of Anthos transactions. Here's how you can observe the system in action:

### Checking Logs

You can monitor the logs of each agent to see the real-time activity of the system.

```bash
# Get the name of the pod for the agent you want to monitor
kubectl get pods

# Stream the logs for a specific pod
kubectl logs -f <pod-name>
```
For example, to monitor the Orchestrator Agent, you would run:
```bash
kubectl logs -f orchestrator-agent-5d4b8b8b8d-6x2g4
```

### End-to-End Workflow

The end-to-end workflow for a typical fraud detection scenario is as follows:

1.  **Detection:** The **TransactionMonitorAgent** detects a high-value transaction and flags it.
2.  **Initiation:** The **TransactionMonitorAgent** sends an alert to the **OrchestratorAgent**.
3.  **Investigation:** The **OrchestratorAgent** delegates the investigation to the **InvestigationAgent**, which gathers details about the transaction and the user.
4.  **Assessment:** The **OrchestratorAgent** interprets the investigation results and compares the reported risk score to the configured threshold.
5.  **Action:** If the risk score meets or exceeds the threshold, the **OrchestratorAgent** commands the **ActuatorAgent** to take action, such as locking the user's account.

### Triggering a Test Scenario

To test the system, you can manually insert a high-value transaction into the Bank of Anthos database. This will trigger the fraud detection workflow.

1.  Connect to the `ledger-db` database in the Bank of Anthos application.
2.  Insert a new transaction with a high value (e.g., > $1000).

*Note: The default risk threshold is `7`. You can override it by setting the `RISK_SCORE_THRESHOLD` environment variable on the Orchestrator deployment.*

## Developer's Guide

This section provides technical details for developers working on the Vigil AI Fraud Shield project.

### Technology Stack

*   **Google Kubernetes Engine (GKE):** The deployment platform for the entire system.
*   **Google AI Models (Gemini):** Powers the intelligence of the Investigation agent.
*   **Agent Development Kit (ADK):** The toolkit used to build the agents.
*   **Model Context Protocol (MCP):** Used for communication between the agents and the GenAl Toolbox.
*   **Agent2Agent (A2A) protocol:** Facilitates communication and orchestration between the agents.

### Developer Notes

This section contains key learnings and best practices for working with the project's technology stack.

*   **A2A is a separate protocol:** The Agent2Agent (A2A) protocol is not part of the Google ADK. It is a separate package (`a2a-sdk`) and should be imported accordingly.
*   **Use the ClientFactory:** The modern A2A API uses `ClientFactory.create_client_with_jsonrpc_transport()` to create clients. The legacy `A2AClient` constructor is deprecated.
*   **LlmAgent requires a name:** The `LlmAgent` constructor requires a `name` field, which must be a valid Python identifier (e.g., "orchestrator_agent").
*   **FunctionTool is minimal:** The `FunctionTool` constructor only accepts the function as an argument. It does not take `name` or `description` parameters.
*   **No decorators:** The current version of the ADK does not use `@tool` or `@rpc` decorators.

### FastAPI-based Architecture

*   The agents have been refactored to use a FastAPI-based architecture for handling A2A communication. This provides a more robust and modern approach than the legacy ADK RPC server.
*   The standard port for the FastAPI servers is `8000`.
*   A `/health` endpoint is available on each agent for Kubernetes readiness and liveness probes.

### Docker Best Practices

*   **Specify file paths:** When building Docker images from the root of the repository, be sure to specify the full path to the files you want to copy (e.g., `COPY vigil-system/orchestrator_agent/agent.py /app/`). Do not rely on copying the entire directory (`COPY . /app/`).
*   **Build context matters:** Always be aware of the build context when running `docker build` commands to ensure that the Dockerfile can find all the necessary files.

## Troubleshooting

This section provides solutions to common issues that you may encounter when working with the Vigil System.

### `CrashLoopBackOff` in Orchestrator Agent

*   **Symptom:** The orchestrator agent pod is in a `CrashLoopBackOff` state with the error `ModuleNotFoundError: No module named 'google.adk.rpc'`.
*   **Cause:** This is due to incorrect A2A protocol imports and outdated ADK API usage.
*   **Solution:**
    1.  Ensure that the `a2a-sdk` package is included in `requirements.txt`.
    2.  Update the code to import from `a2a.client` instead of `google.adk.rpc`.
    3.  Update the code to use the modern ADK and A2A APIs as described in the "Developer Notes" section.

### Database Connection Errors

*   **Symptom:** The `genai-toolbox` service fails to connect to the Bank of Anthos databases with errors like `password authentication failed`.
*   **Cause:** Incorrect database credentials or database names in the `tools.yaml` configuration file.
*   **Solution:** Verify that the `user`, `password`, and `database` fields in `tools.yaml` match the actual credentials for the Bank of Anthos databases.

### Database Schema Mismatches

*   **Symptom:** SQL errors like `column "from_account_id" does not exist`.
*   **Cause:** The SQL queries in `tools.yaml` do not match the actual schema of the Bank of Anthos database.
*   **Solution:** Update the SQL queries in `tools.yaml` to use the correct column names. You can use aliases (e.g., `SELECT from_acct as from_account_id`) to map the database schema to the expected API schema.

### JSON Parsing Errors

*   **Symptom:** Errors like `'str' object has no attribute 'get'` when processing responses from the `genai-toolbox`.
*   **Cause:** The `genai-toolbox` may return JSON data as a string within a `result` field (e.g., `{"result": "[{...}]"}`).
*   **Solution:** Before processing the response, check if the data is a string. If it is, parse it using `json.loads()`.
