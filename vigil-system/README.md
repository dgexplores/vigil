# Vigil - AI-Powered Fraud Detection System

🛡️ **Vigil** is an advanced fraud detection system that protects Latin American digital banking by leveraging Google's Agent Development Kit (ADK) and Gemini 2.5-flash for real-time transaction analysis.

## 🎯 Overview

Vigil consists of three intelligent ADK agents that work together to monitor, analyze, and respond to fraudulent activities:

1. **Observer Agent** 🔍 - Continuously monitors Bank of Anthos transactions
2. **Analyst Agent** 🧠 - Uses Gemini 2.5-flash for sophisticated fraud analysis  
3. **Actuator Agent** ⚡ - Executes protective actions when fraud is detected

## 🏗️ System Architecture

```
┌─────────────────┐    A2A     ┌─────────────────┐    A2A     ┌─────────────────┐
│  Observer       │ ────────>  │  Analyst        │ ────────>  │  Actuator       │
│  Agent          │            │  Agent          │            │  Agent          │
│                 │            │                 │            │                 │
│ • Monitors txns │            │ • AI analysis   │            │ • Lock accounts │
│ • Normalizes    │            │ • Risk scoring  │            │ • Block txns    │
│ • Enriches data │            │ • Decision      │            │ • Alert teams   │
└─────────────────┘            └─────────────────┘            └─────────────────┘
         │                               │                               │
         │                               │                               │
         ▼                               ▼                               ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│                          MCP Server (Model Context Protocol)                    │
│                                                                                 │
│  • get_transactions()     • get_user_details()     • lock_account()            │
│  • get_account_balance()  • send_notification()    • block_transaction()       │
└─────────────────────────────────────────────────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│                              Bank of Anthos                                    │
│                                                                                 │
│  • Transaction History    • User Service         • Ledger Writer               │
│  • Balance Reader        • Contacts Service      • Account Management           │
└─────────────────────────────────────────────────────────────────────────────────┘
```

## 🧠 AI-Powered Fraud Detection

### Gemini 2.5-flash Analysis

The Analyst Agent uses Gemini 2.5-flash with expertly crafted prompts for:

- **Regional Expertise**: Specialized knowledge of Latin American fraud patterns
- **PIX Payment Analysis**: Brazilian instant payment fraud detection
- **Behavioral Modeling**: User transaction pattern analysis
- **Geographic Validation**: Cross-border fraud identification
- **Social Engineering Detection**: Keyword and context analysis

### Risk Scoring Framework

```
Risk Score Range | Action Level  | Response
━━━━━━━━━━━━━━━━━┿━━━━━━━━━━━━━━━┿━━━━━━━━━━━━━━━━━━━━━━━━
0-25            | Normal        | Continue monitoring
26-50           | Low Risk      | Enhanced monitoring  
51-75           | Medium Risk   | Verification request
76-90           | High Risk     | Account restrictions
91-100          | Critical      | Immediate lockdown
```

## 🚀 Quick Start

### Prerequisites

- Google Cloud Platform account
- Docker installed
- kubectl configured
- Google ADK access
- Gemini API key

### 1. Environment Setup

```bash
# Set your GCP project
export PROJECT_ID="your-gcp-project-id"
export REGION="us-central1"

# Clone and navigate to the project
cd vigil-system
```

### 2. Deploy to GKE

The automated deployment script handles everything:

```bash
# Build, push, and deploy all agents
./deploy.sh all

# Or step by step:
./deploy.sh build    # Build Docker images
./deploy.sh push     # Push to registry  
./deploy.sh deploy   # Deploy to GKE
```

### 3. Verify Deployment

```bash
# Check agent status
kubectl get pods

# View logs
kubectl logs -f deployment/vigil-analyst
kubectl logs -f deployment/vigil-observer
kubectl logs -f deployment/vigil-actuator
```

### 4. Run Integration Tests

```bash
# Test the complete system
python test_vigil_integration.py
```

## 📁 Project Structure

```
vigil-system/
├── analyst-agent/           # AI-powered fraud analysis
│   ├── agent.py            # Gemini 2.5-flash integration
│   ├── requirements.txt    # Python dependencies
│   ├── config.yaml         # Agent configuration
│   └── Dockerfile          # Container definition
│
├── observer-agent/          # Transaction monitoring
│   ├── agent.py            # Loop agent for monitoring
│   ├── requirements.txt    # Python dependencies
│   └── Dockerfile          # Container definition
│
├── actuator-agent/          # Protective actions
│   ├── agent.py            # Action execution logic
│   ├── requirements.txt    # Python dependencies
│   └── Dockerfile          # Container definition
│
├── k8s/                     # Kubernetes manifests
│   ├── namespace-and-config.yaml
│   ├── analyst-deployment.yaml
│   ├── observer-deployment.yaml
│   └── actuator-deployment.yaml
│
├── vigil_mcp_server.py      # MCP protocol server
├── test_vigil_integration.py # Integration tests
├── deploy.sh                # Automated deployment
└── README.md               # This file
```

## 🔧 Configuration

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `PROJECT_ID` | - | GCP project ID |
| `RISK_THRESHOLD` | 75 | Risk score threshold for alerts |
| `POLLING_INTERVAL` | 5 | Observer polling interval (seconds) |
| `AUTO_EXECUTE_ACTIONS` | false | Enable automatic protective actions |

### Gemini API Setup

1. Get your Gemini API key from Google AI Studio
2. Update the Kubernetes secret:

```bash
# Encode your API key
echo -n "your-gemini-api-key" | base64

# Update the secret in k8s/namespace-and-config.yaml
```

## 🎯 Fraud Detection Features

### Regional Specialization

- **Brazil**: PIX payment fraud, social engineering detection
- **Mexico**: Cross-border transaction analysis  
- **Colombia**: Velocity fraud patterns
- **Argentina**: Account takeover indicators
- **Chile**: Geographic impossibility detection

### Detection Capabilities

- **Velocity Fraud**: Multiple rapid transactions
- **Geographic Anomalies**: Impossible location changes
- **Social Engineering**: Keyword detection in Portuguese/Spanish
- **Account Takeover**: Unusual device/IP patterns
- **Amount Anomalies**: Unusual transaction amounts
- **Recipient Risk**: New or suspicious beneficiaries

## 📊 Monitoring & Observability

### Agent Health Checks

```bash
# Check agent health
kubectl get pods
kubectl describe pod <pod-name>
```

### Logs and Metrics

```bash
# Stream logs
kubectl logs -f deployment/vigil-analyst

# Check metrics (if enabled)
kubectl port-forward svc/vigil-analyst 8091:8091
curl http://localhost:8091/metrics
```

### Configuration Updates

```bash
# Update configuration without restart
kubectl edit configmap vigil-config
```

## 🧪 Testing

### Unit Tests

```bash
# Run individual agent tests
cd analyst-agent && python agent.py
cd observer-agent && python agent.py  
cd actuator-agent && python agent.py
```

### Integration Tests

```bash
# Complete system test
python test_vigil_integration.py

# Test specific components
pytest -v test_vigil_integration.py::test_analyst_agent_fraud_detection
```

### Load Testing

```bash
# Simulate high transaction volume
kubectl scale deployment vigil-observer --replicas=3
kubectl scale deployment vigil-analyst --replicas=5
```

## 🔒 Security

### Authentication

- MCP server authentication for Bank of Anthos access
- Kubernetes RBAC for pod permissions
- Secret management for API keys

### Data Protection

- No sensitive data stored in logs (configurable)
- Encrypted communication between agents
- Minimal privilege principles

### Action Safeguards

- Demo mode prevents actual account locks
- Confirmation workflows for high-impact actions
- Audit logging for all protective actions

## 🛠️ Troubleshooting

### Common Issues

**Agent pods not starting:**
```bash
kubectl describe pod <pod-name> -n vigil-system
kubectl logs <pod-name> -n vigil-system
```

**MCP connection failures:**
```bash
# Check if Bank of Anthos is accessible
kubectl exec -it <observer-pod> -n vigil-system -- curl http://ledgerwriter:8080/health
```

**High risk transactions not triggering actions:**
```bash
# Check risk threshold configuration
kubectl get configmap vigil-config -n vigil-system -o yaml
```

### Performance Tuning

```bash
# Scale agents based on load
kubectl scale deployment vigil-analyst --replicas=3 -n vigil-system

# Adjust resource limits
kubectl edit deployment vigil-analyst -n vigil-system
```

## 🤝 Contributing

### Development Workflow

1. Fork the repository
2. Create feature branch: `git checkout -b feature/amazing-fraud-detection`
3. Make changes and test: `python test_vigil_integration.py`
4. Submit pull request

### Code Standards

- Python 3.11+ with type hints
- Async/await patterns for I/O operations  
- Comprehensive logging and error handling
- ADK best practices for agent development

## 📈 Roadmap

- [ ] Machine learning model integration
- [ ] Advanced behavioral analysis
- [ ] Multi-region deployment support
- [ ] Real-time dashboard
- [ ] Webhook integrations for external systems
- [ ] Advanced A2A communication patterns

## 📄 License

This project is part of the GKE Turns 10 Hackathon and is licensed under the MIT License.

## 🏆 GKE Turns 10 Hackathon

Vigil showcases the power of Google Kubernetes Engine for deploying sophisticated AI-powered fraud detection systems. Built with:

- **Google Agent Development Kit (ADK)** for intelligent agent orchestration
- **Gemini 2.5-flash** for advanced fraud analysis
- **GKE** for scalable, reliable deployment
- **Model Context Protocol (MCP)** for secure Bank of Anthos integration

---

**Built with 💙 for the GKE Turns 10 Hackathon**

*Protecting Latin American digital banking with AI-powered fraud detection*