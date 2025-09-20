# **Vigil AI Fraud Shield: Agentic Microservice Development Guide**

**Mission:** To construct a proactive, hierarchical multi-agent system on GKE that enhances the Bank of Anthos application by detecting and mitigating financial fraud. This system will fully leverage the "strongly recommended" Google agentic stack (ADK, MCP via GenAl Toolbox, A2A) to maximize technical excellence and competitive viability for the GKE Turns 10 Hackathon.

## **1\. Revised System Architecture**

The original Vigil architecture (Observer \-\> Analyst \-\> Actuator) is evolved into a more sophisticated, decoupled, and secure Hierarchical Multi-Agent System. The core change is the replacement of the custom-built MCP server with the **GenAl Toolbox**, which acts as a secure data access layer. An **Orchestrator Agent** is introduced to manage the workflow, delegating tasks to specialized agents.

Given the use of a GKE Autopilot cluster, we will simplify the deployment by co-locating all microservices into a single default namespace. Crucially, the architecture will interface with the Bank of Anthos application's two distinct databases: the **Accounts DB** (for user and contact information) and the **Ledger DB** (for financial transactions).

### **1.1. Architectural Diagram**

This diagram illustrates the revised data and communication flow, showing the GenAl Toolbox connecting to both databases.

graph TD  
    subgraph "GKE Autopilot Cluster (Default Namespace)"  
        subgraph "Bank of Anthos Services"  
            UserService\[userservice\] \--\> AccountsDB\[(Accounts DB)\]  
            ContactsService\[contacts\] \--\> AccountsDB  
            LedgerWriter\[ledgerwriter\] \--\> LedgerDB\[(Ledger DB)\]  
            BalanceReader\[balancereader\] \--\> LedgerDB  
            TransactionHistory\[transactionhistory\] \--\> LedgerDB  
        end

        subgraph "Vigil Agentic Services"  
            UI\[User Interface / API Gateway\] \-- HTTP/gRPC \--\> OrchestratorAgent  
              
            OrchestratorAgent \-- A2A Protocol \--\> TransactionMonitorAgent  
            OrchestratorAgent \-- A2A Protocol \--\> InvestigationAgent  
            OrchestratorAgent \-- A2A Protocol \--\> CriticAgent  
            OrchestratorAgent \-- A2A Protocol \--\> ActuatorAgent  
              
            TransactionMonitorAgent \-- MCP (HTTP) \--\> GenAlToolbox  
            InvestigationAgent \-- MCP (HTTP) \--\> GenAlToolbox  
            ActuatorAgent \-- MCP (HTTP) \--\> GenAlToolbox  
              
            GenAlToolbox \-- SQL \--\> AccountsDB  
            GenAlToolbox \-- SQL \--\> LedgerDB  
        end  
    end

    User\[External System/User\] \--\> UI

### **1.2. Component Roles & Responsibilities**

| Component | Technology/Protocol | GKE Deployment | Role & Responsibility |
| :---- | :---- | :---- | :---- |
| **Orchestrator Agent** | ADK (LlmAgent) | Deployment | The system's central "brain." Receives high-level tasks (e.g., "monitor for fraud"), plans multi-step workflows, and delegates sub-tasks to specialized agents using the A2A protocol. |
| **TransactionMonitor Agent** | ADK (Loop or CustomAgent) | Deployment | The system's sensor. Continuously monitors the Ledger DB for new transactions using a GenAl Toolbox tool. Flags anomalies and initiates an investigation via an A2A call to the Orchestrator. |
| **Investigation Agent** | ADK (LlmAgent with Gemini) | Deployment | The digital detective. Gathers comprehensive context on a flagged transaction using various database tools across both the Ledger DB and Accounts DB. Synthesizes findings into a "case file". |
| **Critic Agent** | ADK (LlmAgent with Gemini) | Deployment | The quality assurance layer. Receives the case file and adversarially challenges the initial suspicion to reduce false positives before any action is taken. A key innovation. |
| **Actuator Agent** | ADK (CustomAgent) | Deployment | The enforcement arm. Receives validated commands from the Orchestrator. Executes actions (e.g., locking an account in the Accounts DB) by invoking tools on the GenAl Toolbox. |
| **GenAl Toolbox Service** | GenAl Toolbox (Go binary) | Deployment | The secure MCP server. Connects to both Bank of Anthos databases and exposes pre-defined, parameterized SQL queries as "tools" for the agents to consume. |

## **2\. Component Implementation Details**

### **2.1. GenAl Toolbox Service: The Secure Data Bridge**

This component is critical. It must be configured to connect to both the Accounts DB and the Ledger DB, routing each tool call to the correct data source.

**Action Steps:**

1. **Containerize and Deploy:** Create a Dockerfile for the GenAl Toolbox Go binary. Deploy it as a Deployment and Service named genal-toolbox-service in the cluster's default namespace.  
2. **Create tools.yaml ConfigMap:** The core logic resides in a configuration file. Create a Kubernetes ConfigMap named toolbox-config. This configuration now defines **two sources**.  
   \# tools.yaml  
   sources:  
     \- name: accounts-db  
       type: postgres  
       \# Use GKE internal service DNS. This will be injected via environment variables.  
       uri: ${ACCOUNTS\_DB\_URL}  
     \- name: ledger-db  
       type: postgres  
       \# Use GKE internal service DNS. This will be injected via environment variables.  
       uri: ${LEDGER\_DB\_URL}

   toolsets:  
     \- name: vigil\_tools  
       tools:  
         \- name: get\_new\_transactions  
           source: ledger-db \# \<-- This tool targets the Ledger DB  
           description: "Retrieves all transactions that have occurred since the given timestamp."  
           statement: "SELECT transaction\_id, amount, timestamp, from\_account\_id, to\_account\_id FROM transactions WHERE timestamp \> @last\_timestamp ORDER BY timestamp ASC;"  
           parameters:  
             \- name: last\_timestamp  
               type: string  
               description: "The ISO 8601 timestamp of the last transaction processed."

         \- name: get\_user\_details\_by\_account  
           source: accounts-db \# \<-- This tool targets the Accounts DB  
           description: "Fetches user profile information for a given account ID."  
           statement: "SELECT u.user\_id, u.username, u.ext\_user\_id, a.account\_id FROM users u JOIN accounts a ON u.ext\_user\_id \= a.ext\_user\_id WHERE a.account\_id \= @account\_id;"  
           parameters:  
             \- name: account\_id  
               type: string  
               description: "The account ID to fetch user details for."

         \- name: get\_user\_transaction\_history  
           source: ledger-db \# \<-- This tool targets the Ledger DB  
           description: "Retrieves the 50 most recent transactions for a given user ID to understand their history."  
           statement: "SELECT \* FROM transactions WHERE from\_account\_id \= @account\_id ORDER BY timestamp DESC LIMIT 50;"  
           parameters:  
             \- name: account\_id  
               type: string  
               description: "The user's account ID."

         \- name: lock\_account  
           source: accounts-db \# \<-- This tool targets the Accounts DB  
           description: "Locks a user's account to prevent further activity. This is a critical security action."  
           \# NOTE: The Bank of Anthos schema does not have a native 'locked' status.  
           \# We simulate this by updating a user's description field.  
           statement: "UPDATE users SET user\_info \= 'ACCOUNT\_LOCKED\_BY\_VIGIL' WHERE ext\_user\_id \= @ext\_user\_id;"  
           parameters:  
             \- name: ext\_user\_id  
               type: string  
               description: "The external user ID associated with the account to be locked."

### **2.2. Agent Development (Python ADK)**

Each agent is a separate Python application, containerized and deployed to GKE. The agent logic remains the same, but they will now seamlessly access tools that draw from different databases without needing to know the underlying topology.

#### **Orchestrator Agent (LlmAgent)**

* **Logic:** Its primary role is planning and delegation. It does not call the GenAl Toolbox directly.  
* **System Prompt:**"You are 'Vigil Control', a master orchestrator for a team of AI fraud detection agents. Your mission is to analyze high-level alerts and delegate tasks to the appropriate specialized agent using the available A2A tools. For a new transaction alert, you must first delegate to the 'InvestigationAgent'. If the investigation yields a high-risk score, you must then delegate to the 'CriticAgent' for verification. Only after the CriticAgent concurs should you delegate to the 'ActuatorAgent' to take protective action. Sequence your calls logically and precisely."  
* **A2A Client:** It will be configured with the internal GKE service URLs for the Investigation, Critic, and Actuator agents and will use the ADK's A2A client library to invoke them.

#### **TransactionMonitor Agent (CustomAgent)**

* **Logic:** Implement as a simple, continuous loop.  
  1. Initialize last\_processed\_timestamp to the current time.  
  2. In a loop (e.g., every 5 seconds):  
     a. Invoke the get\_new\_transactions tool via the GenAl Toolbox client, passing the last\_processed\_timestamp.  
     b. For each new transaction, perform a basic heuristic check (e.g., amount \> $1000, new recipient).  
     c. If a transaction is flagged, make an A2A call to the Orchestrator with the transaction details.  
     d. Update last\_processed\_timestamp to the timestamp of the latest transaction processed.

#### **Investigation, Critic, and Actuator Agents**

* **Investigation Agent (LlmAgent):**  
  * Exposes an A2A server endpoint.  
  * Receives transaction data.  
  * Calls get\_user\_transaction\_history and get\_user\_details\_by\_account tools. The GenAl Toolbox handles routing these to the correct DB.  
  * Uses a detailed prompt (as specified in the original Vigil document) to query Gemini for a risk score and justification.  
  * Returns the structured "case file" (input data \+ Gemini analysis) in its A2A response.  
* **Critic Agent (LlmAgent):**  
  * Exposes an A2A server endpoint.  
  * Receives the case file.  
  * **System Prompt:** \> "You are a skeptical risk analyst. Your role is to challenge the findings in this case file. Find evidence that contradicts the suspicion of fraud. Identify legitimate alternative explanations for the observed behavior. Conclude with a 'concur' or 'dissent' verdict."  
  * Returns the verdict in its A2A response.  
* **Actuator Agent (CustomAgent):**  
  * Exposes an A2A server endpoint.  
  * Receives a validated action command (e.g., { "action": "lock\_account", "ext\_user\_id": "..." }).  
  * Parses the command and invokes the corresponding tool (lock\_account) on the GenAl Toolbox.  
  * Logs the action and returns a success/failure status.

## **3\. Workflow Orchestration (A2A Protocol)**

This outlines the end-to-end flow for the "Anomalous PIX Transfer" scenario.

1. **Detection:** The TransactionMonitorAgent detects a high-value PIX transfer in the **Ledger DB** and flags it.  
2. **Initiation:** The TransactionMonitorAgent makes an A2A call to the OrchestratorAgent with the transaction payload.  
3. **A2A Call 1 (Orchestrator → Investigation):** The OrchestratorAgent delegates by making an A2A call to the InvestigationAgent.  
4. **Analysis:** The InvestigationAgent queries the **Ledger DB** for transaction history and the **Accounts DB** for user details, gets a high risk score from Gemini, and returns the case file.  
5. **A2A Call 2 (Orchestrator → Critic):** The Orchestrator forwards the case file in a new A2A call to the CriticAgent.  
6. **Validation:** The CriticAgent reviews the case and returns a { "verdict": "concur" } response.  
7. **A2A Call 3 (Orchestrator → Actuator):** The Orchestrator sends a precise command via A2A to the ActuatorAgent.  
8. **Action:** The ActuatorAgent invokes the lock\_account tool, which writes the change to the **Accounts DB**, securing the account.

## **4\. GKE Deployment Plan**

* **Namespace:** All Bank of Anthos and Vigil components will be deployed into the default namespace to simplify management within the GKE Autopilot environment.  
* **Manifests:** Use declarative YAML files for all resources.  
  * **Deployments:** One for each agent and one for the GenAl Toolbox. The Toolbox pod's deployment manifest must now include environment variables for both ACCOUNTS\_DB\_URL and LEDGER\_DB\_URL.  
  * **Services:** Create ClusterIP services for the GenAl Toolbox and for each agent that exposes an A2A server endpoint.  
* **Secrets:** Create a Kubernetes Secret named gemini-api-key and mount it as an environment variable into the Investigation and Critic agent pods.