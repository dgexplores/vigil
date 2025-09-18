# Project Vigil: Agentic Proactive Fraud Shield

### 1. Project Overview

**Mission:** To engineer an intelligent, multi-agent system that proactively shields Bank of Anthos customers from fraudulent activities, with a specific focus on the Latin America region. Vigil leverages Google's Gemini AI and Google Kubernetes Engine (GKE) to create a dynamic, context-aware defense mechanism that understands user behavior, identifies threat patterns, and neutralizes fraudulent activities in real-time.

**Core Problem:** Traditional fraud detection systems are reactive, relying on static rules and classical machine learning models that are slow to adapt to new fraud tactics, generate high false positives, and fail to prevent sophisticated fraud schemes. This results in financial losses and erodes customer trust.

**The Agentic Solution:** Vigil employs a team of autonomous AI agents that collaborate to monitor, analyze, and act upon transactional data streams in real-time. This represents a paradigm shift from passive detection to active, intelligent protection. By building new, containerized components that interact with the existing Bank of Anthos application via its APIs, Vigil enhances the application with cutting-edge agentic AI capabilities without modifying the core codebase.

---

### 2. System Architecture

Vigil is designed as a multi-agent system (MAS) where each agent has a specialized role. This modular architecture, built using the Google Agent Development Kit (ADK), ensures a clear separation of concerns, enhances scalability, and simplifies development.

[Image of a multi-agent system architecture diagram]

The system consists of three distinct agent types:

* **Observer Agent:** The system's sensory apparatus, responsible for continuous monitoring of financial activity data streams from the Bank of Anthos application.
* **Analyst Agent:** The cognitive core of Vigil, housing the Gemini model and performing real-time risk assessment.
* **Actuator Agent:** The system's enforcement arm, responsible for taking decisive, proactive measures to mitigate threats based on the Analyst's findings.

---

### 3. Component Deep Dive

#### 3.1. Observer Agent

* **Role:** The Observer agent continuously monitors the financial activity data stream flowing through the Bank of Anthos application.
* **Function:**
    * Implemented as a long-running process that periodically queries the `transaction-history` and `ledger-writer` microservices.
    * Interacts with a custom-built Model Context Protocol (MCP) server, which provides a standardized interface to the bank's internal APIs.
    * Normalizes raw transaction data into a structured format for analysis.
    * Passes the structured data to the Analyst agent for risk assessment.
* **Implementation:**
    * Use the ADK's `Loop` workflow agent for continuous execution.
    * Maintain an internal state of the last processed transaction to avoid reprocessing old data.
    * Use the Agent2Agent (A2A) protocol to dispatch new transaction details to the Analyst agent.

#### 3.2. Analyst Agent

* **Role:** The Analyst agent is the cognitive core of Vigil, performing real-time risk assessment using the Gemini model.
* **Function:**
    * Receives structured transaction data from the Observer agent.
    * Enriches the data with additional context by querying other Bank of Anthos services (e.g., user's historical transaction patterns, login locations).
    * Uses advanced prompt engineering to present the comprehensive context to the Gemini API, generating a precise risk score and a natural-language justification for its assessment.
    * If a high-risk score is generated, it formulates a recommended action and sends it to the Actuator agent.
* **Implementation:**
    * Implement as an `LlmAgent` from the ADK, initialized with a Gemini model (e.g., `gemini-2.5-flash`).
    * Expose an A2A endpoint to listen for incoming transaction data from the Observer.
    * Use the `get_user_details` tool via the MCP server to gather user context.
    * Utilize a meticulously engineered prompt with a defined persona, few-shot examples, and structured JSON input to query the Gemini model.
    * If the risk score exceeds a predefined threshold, send a command to the Actuator agent via A2A.

**Prompt Engineering for Gemini:**

The prompt is crucial for eliciting accurate and reliable analysis from the Gemini model. The following prompt establishes the agent's persona and objectives:

> "You are 'Vigil', a senior fraud and risk analyst for a digital bank operating in Latin America. Your mission is to protect customers by analyzing financial transactions with extreme prejudice and accuracy. For each transaction you analyze, you must provide a JSON object containing two keys: 'risk_score' (an integer from 0 to 100) and 'justification' (a brief, clear explanation for your score). In your analysis, you must consider the user's historical behavior, transaction velocity, geographic plausibility, and known regional fraud patterns like PIX scams and ATO indicators."

The prompt will also include few-shot examples of fraudulent and legitimate transactions to guide the model's response format and style.

#### 3.3. Actuator Agent

* **Role:** The Actuator agent is the system's enforcement arm, taking proactive measures to mitigate threats based on the Analyst's findings.
* **Function:**
    * Receives high-risk alerts and recommended actions from the Analyst agent.
    * Interacts with the Bank of Anthos APIs via the MCP server to execute these actions.
    * Interventions can range from placing a temporary hold on a transaction and requesting step-up authentication to temporarily locking an account in high-confidence account takeover scenarios.
* **Implementation:**
    * Implement as a standard ADK Agent that exposes an A2A endpoint to listen for commands from the Analyst.
    * Parse incoming A2A commands and execute the corresponding tool call on the MCP server (e.g., invoking the `lock_account` tool).

#### 3.4. MCP Server

* **Purpose:** The Model Context Protocol (MCP) server acts as a universal translator for the Bank of Anthos application, transforming its undocumented internal APIs into a clean, tool-based interface that the AI agents can reliably use.
* **Inferred Bank of Anthos API Contract:**

| Tool Name (for MCP) | Target Microservice | HTTP Method | Path | Auth Required | Request Payload (JSON Schema) | Success Response (JSON Schema) |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `get_transactions` | `transactionhistory` | GET | `/transactions/{account_id}` | JWT | N/A | `{"transactions": [{"amount": float, "timestamp": str,...}]}` |
| `submit_transaction` | `ledgerwriter` | POST | `/transactions` | JWT | `{"fromAccount": str, "toAccount": str, "amount": int, "routingNumber": str}` | `{"transaction_id": str, "status": "ok"}` |
| `get_user_details` | `userservice` | GET | `/users/{user_id}` | JWT | N/A | `{"username": str, "account_num": str,...}` |
| `lock_account` | `userservice` | POST | `/users/{user_id}/lock` | JWT | `{"reason": "string"}` | `{"status": "locked", "user_id": str}` |
| `login` | `userservice` | POST | `/login` | None | `{"username": "string", "password": "string"}` | `{"token": "jwt_string"}` |

* **Implementation:**
    * Implement as a lightweight web server using Python and FastAPI.
    * Utilize the `mcp.py` library to ensure compliance with the MCP specification.
    * The server will receive MCP tool calls from the agents, look up the corresponding API details, construct the HTTP request for the target microservice, add the cached JWT for authentication, and dispatch the request to the internal Kubernetes service DNS name.

---

### 4. GKE Deployment Architecture

* **Namespace Strategy:**
    * `default`: Both the Bank of Anthos application and all Vigil components (agents and MCP Server) are deployed in the default namespace to simplify service discovery and inter-service communication.
* **Kubernetes Manifests:**
    * **Deployments:** Each of the four Vigil components will be managed by its own Kubernetes `Deployment` resource, specifying the container image, replicas, resource requests and limits, and environment variables.
    * **Services:** Kubernetes `Service` objects of type `ClusterIP` will manage network connectivity between the Vigil agents and the MCP server, allowing them to communicate using stable internal DNS names.
    * **ConfigMaps & Secrets:**
        * A `ConfigMap` named `vigil-config` will store non-sensitive configuration data.
        * A Kubernetes `Secret` named `gemini-api-key` will securely store the API key for the Google AI Platform, which will be mounted as an environment variable into the Analyst agent's pod.

---

### 5. Fraud Detection Scenarios

#### 5.1. Scenario 1: Anomalous High-Velocity PIX Transfer (Brazil)

1.  **Trigger:** A user with a typical transaction value of 250 BRL initiates a 1,500 BRL PIX transfer to a new recipient.
2.  **Observer Detection:** The Observer agent detects the transaction and forwards it to the Analyst.
3.  **Analyst Assessment:** The Analyst agent gathers the user's history, notes the 6x increase in transaction value and the new recipient, and presents this to the Gemini model. The model, aware of PIX scams, returns a high risk score (e.g., 95) with a justification.
4.  **Actuator Response:** The Analyst commands the Actuator to lock the user's account via the `lock_account` tool to prevent further transfers and alerts the user.

#### 5.2. Scenario 2: Cross-Border Card-Not-Present (CNP) Fraud (Mexico)

1.  **Trigger:** A 750 EUR CNP transaction occurs at an online gaming site in Eastern Europe five minutes after the user logged in from Mexico City.
2.  **Observer Detection:** The Observer detects the CNP transaction.
3.  **Analyst Assessment:** The Analyst retrieves the user's recent login location and presents the geographic data to Gemini. The model identifies the "impossible travel" velocity and the high-risk merchant, returning a near-certain risk score (e.g., 99).
4.  **Actuator Response:** Based on the high-confidence assessment, the Analyst commands the Actuator to immediately lock the account using the `lock_account` tool to prevent further unauthorized use.