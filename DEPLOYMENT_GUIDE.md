# Vigil AI Fraud Shield - Deployment Guide

Ahoy, Captain! This guide will walk you through deploying the Vigil AI Fraud Shield to your GKE cluster. Follow these steps carefully to get the system up and running.

## 1. Prerequisites

Before you begin, make sure you have the following tools installed and configured:
- `gcloud` CLI: Authenticated to your Google Cloud project.
- `kubectl`: Configured to connect to your GKE cluster.
- `docker`: Installed and running.

You should have already deployed the Bank of Anthos application to your GKE cluster.

## 2. Configuration

### 2.1. Configure the Gemini API Key

The system requires a Gemini API key to function. A template for the Kubernetes secret has been provided.

1.  **Copy the example file:**
    ```bash
    cp vigil-system/gemini-api-key-secret.yaml.example vigil-system/gemini-api-key-secret.yaml
    ```

2.  **Edit the new file:**
    Open `vigil-system/gemini-api-key-secret.yaml` in a text editor and replace the placeholder `REPLACE_ME_WITH_YOUR_GEMINI_API_KEY` with your actual Gemini API key.

    **Important:** The `gemini-api-key-secret.yaml` file is listed in `.gitignore` to prevent you from accidentally committing your secret key.

### 2.2. Create the Artifact Registry Repository

The container images need a place to live. Create a new Artifact Registry repository for them.

```bash
gcloud artifacts repositories create vigil-repo \
    --repository-format=docker \
    --location=southamerica-east1 \
    --description="Repository for Vigil AI Fraud Shield images"
```

### 2.3. Configure Docker Authentication

Configure Docker to use your `gcloud` credentials to authenticate with the Artifact Registry.

```bash
gcloud auth configure-docker southamerica-east1-docker.pkg.dev
```

## 3. Build and Push Container Images

Now it's time to build the Docker images for each component and push them to your Artifact Registry.

Here are the commands to do this for each service. Run these commands from the root of the repository.

**Project ID:** `vigil-demo-hackathon`
**Repo:** `vigil-repo`
**Region:** `southamerica-east1`

```bash
# Define variables
export PROJECT_ID="vigil-demo-hackathon"
export REGION="southamerica-east1"
export REPO="vigil-repo"
export IMAGE_PREFIX="${REGION}-docker.pkg.dev/${PROJECT_ID}/${REPO}"

# Build and push genal-toolbox
docker build -t "${IMAGE_PREFIX}/genal-toolbox:latest" -f vigil-system/genal_toolbox/Dockerfile .
docker push "${IMAGE_PREFIX}/genal-toolbox:latest"

# Build and push transaction-monitor-agent
docker build -t "${IMAGE_PREFIX}/transaction-monitor-agent:latest" -f vigil-system/transaction_monitor_agent/Dockerfile .
docker push "${IMAGE_PREFIX}/transaction-monitor-agent:latest"

# Build and push orchestrator-agent
docker build -t "${IMAGE_PREFIX}/orchestrator-agent:latest" -f vigil-system/orchestrator_agent/Dockerfile .
docker push "${IMAGE_PREFIX}/orchestrator-agent:latest"

# Build and push investigation-agent
docker build -t "${IMAGE_PREFIX}/investigation-agent:latest" -f vigil-system/investigation_agent/Dockerfile .
docker push "${IMAGE_PREFIX}/investigation-agent:latest"

# Build and push critic-agent
docker build -t "${IMAGE_PREFIX}/critic-agent:latest" -f vigil-system/critic_agent/Dockerfile .
docker push "${IMAGE_PREFIX}/critic-agent:latest"

# Build and push actuator-agent
docker build -t "${IMAGE_PREFIX}/actuator-agent:latest" -f vigil-system/actuator_agent/Dockerfile .
docker push "${IMAGE_PREFIX}/actuator-agent:latest"
```

## 4. Deploy the Application

With the configuration in place and the images in the registry, you can now deploy the application to your GKE cluster.

Apply the manifests in the following order:

1.  **Apply the Secret and ConfigMap:**
    ```bash
    kubectl apply -f vigil-system/gemini-api-key-secret.yaml
    kubectl apply -f vigil-system/genal_toolbox/toolbox-configmap.yaml
    ```

2.  **Apply the Deployments and Services:**
    ```bash
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

    # Critic Agent
    kubectl apply -f vigil-system/critic_agent/critic_agent_deployment.yaml
    kubectl apply -f vigil-system/critic_agent/critic_agent_service.yaml

    # Actuator Agent
    kubectl apply -f vigil-system/actuator_agent/actuator_agent_deployment.yaml
    kubectl apply -f vigil-system/actuator_agent/actuator_agent_service.yaml
    ```

## 5. Verify the Deployment

Check the status of the pods to ensure they are all running correctly.

```bash
kubectl get pods
```

You should see pods for all the deployed components in the `Running` state. It might take a few minutes for the containers to pull the images and start.

If you encounter any issues, you can check the logs of a specific pod to debug:

```bash
# Example for the orchestrator-agent
kubectl logs -l app=orchestrator-agent
```

Good luck, Captain! May your seas be calm and your deployments successful.
