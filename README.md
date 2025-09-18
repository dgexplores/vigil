# Vigil - AI-Powered Fraud Detection System for Bank of Anthos

🛡️ **Vigil** is an advanced fraud detection system that protects digital banking infrastructure by leveraging Google's Agent Development Kit (ADK), Gemini AI, and Model Context Protocol (MCP) for real-time transaction analysis.

## 🏆 GKE Turns 10 Hackathon Submission

This project demonstrates the power of Google Kubernetes Engine (GKE) combined with cutting-edge AI technologies to create an intelligent, scalable fraud detection system for financial institutions.

## 🎯 Key Features

- **Real-time Fraud Detection**: Monitors Bank of Anthos transactions in real-time
- **AI-Powered Analysis**: Uses Gemini 2.5 Flash for sophisticated fraud pattern recognition
- **MCP Integration**: Exposes banking APIs through Model Context Protocol for AI agent interaction
- **Automated Response**: Automatically locks accounts and blocks suspicious transactions
- **Regional Expertise**: Specialized in Latin American fraud patterns (PIX, cross-border transactions)

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                     GKE Cluster                                 │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │                 Bank of Anthos                          │    │
│  │  (Microservices: Frontend, Ledger, Transactions, Users) │    │
│  └─────────────────┬───────────────────────────────────────┘    │
│                    │                                            │
│        ┌───────────▼────────────┐ ┌─────────────────────────┐   │
│        │    MCP Server          │ │    Vigil Agents         │   │
│        │  • Transaction API     │ │  • Observer Agent       │   │
│        │  • User Management     │ │  • Analyst Agent        │   │
│        │  • Account Operations  │ │  • Actuator Agent       │   │
│        │  • Database Fallback   │ │  • AI-Powered Analysis  │   │
│        └────────────────────────┘ └─────────────────────────┘   │
└─────────────────┬──────────────────────────────────────────────┘
                  │ Port Forward
                  │ (Optional for local access)
      ┌───────────▼────────────┐
      │   AI Agents / Warp     │
      │  Terminal Integration  │
      │  • Local MCP Client    │
      │  • Agent Tools Access  │
      └────────────────────────┘
```

## 📁 Project Structure

```
gke-turns10-hackathon-vigil/
├── vigil-system/           # Core Vigil fraud detection system
│   ├── observer-agent/     # Transaction monitoring agent
│   ├── analyst-agent/      # AI-powered fraud analysis
│   ├── actuator-agent/     # Protective action execution
│   ├── mcp-server/        # Model Context Protocol server (runs in cluster)
│   └── k8s/               # Kubernetes manifests
│
├── bank-of-anthos/        # Bank of Anthos submodule
│
├── scripts/               # Utility scripts
│   ├── vigil-mcp-client.py        # MCP client for Warp
│   └── vigil-terminal-functions.sh # Helper functions
│
├── config/                # Configuration files
│   └── vigil-warp-mcp-config.json # Warp MCP configuration
│
└── docs/                  # Documentation
    ├── MCP_INTEGRATION_COMPLETE.md
    ├── MCP_WARP_SETUP.md
    └── WARP_MCP_INTEGRATION.md
```

## 🚀 Quick Start

### Prerequisites

- Google Cloud Platform account with GKE enabled
- `gcloud` CLI configured
- `kubectl` installed
- Docker installed
- Python 3.8+

### 1. Clone the Repository

```bash
git clone --recursive https://github.com/yourusername/gke-turns10-hackathon-vigil.git
cd gke-turns10-hackathon-vigil
```

### 2. Deploy Bank of Anthos

```bash
# Create GKE cluster
gcloud container clusters create-auto bank-of-anthos \
  --project=${PROJECT_ID} --region=${REGION}

# Deploy Bank of Anthos
kubectl apply -f bank-of-anthos/extras/jwt/jwt-secret.yaml
kubectl apply -f bank-of-anthos/kubernetes-manifests
```

### 3. Deploy Vigil System

```bash
cd vigil-system
./deploy.sh all
```

### 4. Set Up Port Forwarding (Optional - for Local MCP Access)

The MCP server runs in the cluster, but for local development and Warp Terminal integration, you can forward services:

```bash
# Port forward Bank of Anthos services for local MCP server access
kubectl port-forward svc/userservice 8081:8080 &
kubectl port-forward svc/transactionhistory 8082:8080 &
kubectl port-forward svc/ledgerwriter 8083:8080 &

# Optional: Port forward MCP server itself for direct access
kubectl port-forward svc/mcp-server 8000:8000 &
```

### 5. Configure Local MCP Integration (Optional - for Warp Terminal)

For local AI agent access through Warp Terminal or other MCP clients:

```bash
# Set up local MCP client environment
cd vigil-system/mcp-server
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Configure Warp Terminal MCP integration
# The config points to scripts/vigil-mcp-client.py which starts a local MCP server
# that connects to the cluster services via port forwarding
```

## 🧪 Testing

### Test MCP Integration

```bash
# The MCP server provides tools to interact with Bank of Anthos
# Example: Get transaction history for Alice (account: 1033623433)
# This can be done through Warp Terminal with MCP tools
```

### Monitor Vigil Agents

```bash
# Check agent status
kubectl get pods

# View logs
kubectl logs -f deployment/vigil-observer
kubectl logs -f deployment/vigil-analyst
kubectl logs -f deployment/vigil-actuator
```

## 🛠️ Key Components

### Vigil Agents (ADK-based)

1. **Observer Agent**: Continuously monitors transactions
2. **Analyst Agent**: Uses Gemini AI for fraud detection
3. **Actuator Agent**: Executes protective actions

### MCP Server

**Deployment**: Runs as a service in the GKE cluster alongside Bank of Anthos
**Local Access**: Can be accessed locally through port forwarding for development

Provides standardized API access to Bank of Anthos for AI agents:
- `get_transactions`: Retrieve transaction history
- `authenticate_user`: User authentication  
- `get_user_details`: Fetch user information
- `lock_account`: Fraud mitigation actions
- `submit_transaction`: Process new transactions

### Integration Features

- **Cluster Deployment**: MCP server runs natively in the GKE cluster
- **Local Development**: Port forwarding enables local AI agent access
- **Automatic Fallback**: Falls back to direct database queries when APIs fail
- **GKE Authentication**: Properly configured for cluster service access
- **Warp Terminal Support**: Native MCP integration for AI-powered terminal

## 📊 Fraud Detection Capabilities

- **Velocity Analysis**: Detects rapid successive transactions
- **Geographic Validation**: Identifies impossible location changes
- **Pattern Recognition**: AI-powered behavioral analysis
- **Amount Anomaly Detection**: Flags unusual transaction amounts
- **Network Analysis**: Identifies suspicious account relationships

## 🔧 Configuration

Key environment variables:

```bash
# For MCP Server
BANK_BASE_URL=http://localhost:8080
USE_GKE_GCLOUD_AUTH_PLUGIN=True

# For Vigil Agents
RISK_THRESHOLD=75
POLLING_INTERVAL=5
AUTO_EXECUTE_ACTIONS=false
```

## 📚 Documentation

- [MCP Integration Guide](docs/MCP_INTEGRATION_COMPLETE.md)
- [Warp Terminal Setup](docs/MCP_WARP_SETUP.md)
- [System Architecture](vigil-system/README.md)

## 🎯 Use Cases

1. **Real-time Fraud Prevention**: Monitor and block suspicious transactions
2. **Account Protection**: Automatically lock compromised accounts
3. **Compliance Monitoring**: Track and report suspicious activities
4. **AI-Assisted Investigation**: Use AI agents to analyze fraud patterns

## 🤝 Contributing

This project was created for the GKE Turns 10 Hackathon. Feel free to fork and extend!

## 📝 License

This project is licensed under the Apache License 2.0.

## 🙏 Acknowledgments

- **Google Cloud Platform** for GKE and the amazing cloud infrastructure
- **Google ADK team** for the Agent Development Kit framework
- **Warp Terminal team** for creating an exceptional tool that enables seamless agentic AI-assisted development through MCP integration
- **Anthropic** for the Model Context Protocol (MCP) standard
- **Bank of Anthos team** for the comprehensive sample banking application

---

Built with ❤️ for the GKE Turns 10 Hackathon