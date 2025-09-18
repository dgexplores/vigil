# Vigil MCP Server

A fully compliant Model Context Protocol (MCP) server for the Vigil fraud detection system. This server provides a standardized MCP interface to Bank of Anthos APIs, allowing AI agents and MCP clients to interact with banking services through well-defined tools and resources.

## MCP Compliance

This server implements the [Model Context Protocol specification](https://modelcontextprotocol.io/) using the official MCP Python SDK. It supports:

- **FastMCP Framework**: Built on the official MCP Python SDK with FastMCP
- **Streamable HTTP Transport**: Production-ready transport for scalable deployments
- **Structured Output**: Tools return properly typed, validated data structures
- **Lifespan Management**: Proper resource lifecycle management with dependency injection
- **Context Integration**: Full MCP Context support for logging, progress, and resource access

## Overview

The MCP server acts as a universal translator between the Vigil AI agents and the Bank of Anthos microservices. It transforms undocumented internal APIs into a clean, tool-based interface that AI agents can reliably use.

## Features

- **JWT Authentication Management**: Automatic token refresh and secure authentication with Bank of Anthos services
- **Comprehensive API Coverage**: All Bank of Anthos operations needed for fraud detection
- **Error Handling**: Robust error handling with meaningful error messages
- **Health Monitoring**: Built-in health checks for Kubernetes deployment
- **Security**: Non-root container execution and security-focused configuration

## Available MCP Tools

All tools use the MCP Context system for logging and error handling, and return structured data validated against output schemas.

### 1. `get_transactions(account_id: str)`
Retrieves transaction history for a specific bank account.

**Parameters:**
- `account_id`: Unique identifier for the bank account

**Returns:** Structured transaction history with validated schema

### 2. `submit_transaction(from_account: str, to_account: str, amount: int, routing_number: str)`
Submits a new transaction to the banking ledger.

**Parameters:**
- `from_account`: Source account number
- `to_account`: Destination account number
- `amount`: Transaction amount in cents
- `routing_number`: Bank routing number

**Returns:** Structured transaction result with confirmation details

### 3. `get_user_details(user_id: str)`
Retrieves detailed information about a specific user.

**Parameters:**
- `user_id`: Unique identifier for the user

**Returns:** Structured user details with account information

### 4. `lock_account(user_id: str, reason: str)`
Locks a user account to prevent further transactions (fraud mitigation).

**Parameters:**
- `user_id`: Unique identifier for the user
- `reason`: Reason for locking (e.g., "Suspected fraud")

**Returns:** Structured lock operation result

### 5. `authenticate_user(username: str, password: str)`
Authenticates a user and retrieves their JWT token.

**Parameters:**
- `username`: User's username
- `password`: User's password

**Returns:** Structured authentication result with token details

## Available MCP Resources

### 1. `vigil://config/bank-connection`
Returns current Bank of Anthos connection configuration including base URL, timeout settings, and authentication username.

### 2. `vigil://status/health` 
Provides current health status of the Vigil MCP Server including service status and version information.

## Configuration

The server is configured through environment variables:

| Variable | Default | Description |
|----------|---------|-------------|
| `BANK_BASE_URL` | `http://bank-of-anthos` | Base URL for Bank of Anthos services |
| `REQUEST_TIMEOUT` | `30` | HTTP request timeout in seconds |
| `AUTH_USERNAME` | `admin` | Username for service authentication |
| `AUTH_PASSWORD` | `password` | Password for service authentication |
| `JWT_SECRET` | `secret-key-change-in-production` | JWT signing secret |
| `HOST` | `0.0.0.0` | Server bind address |
| `PORT` | `8000` | Server port |
| `LOG_LEVEL` | `info` | Logging level |

## Development

### Local Development

1. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

2. Set environment variables:
   ```bash
   export BANK_BASE_URL=\"http://localhost:8080\"
   export AUTH_USERNAME=\"your-username\"
   export AUTH_PASSWORD=\"your-password\"
   ```

3. Run the server:
   ```bash
   python mcp.py
   ```

The server will be available at `http://localhost:8000`.

### Testing

#### MCP Compliance Testing

Test the MCP server functionality:
```bash
# Forward the service port
kubectl port-forward -n vigil-system svc/mcp-server 8080:8000 &

# Run the compliance test
python test_mcp_compliance.py
```

#### Manual MCP Client Testing

Connect with any MCP client using the streamable HTTP transport:
- **Transport**: streamable-http
- **URL**: `http://localhost:8080/mcp` (when port-forwarded)
- **URL**: `http://mcp-server.vigil-system.svc.cluster.local:8000/mcp` (from within cluster)

### Building Docker Image

Use the provided build script:
```bash
export PROJECT_ID=your-gcp-project-id
./build.sh
```

## Deployment

### Prerequisites

- Kubernetes cluster (GKE recommended)
- `kubectl` configured to access your cluster
- Bank of Anthos deployed in `bank-of-anthos` namespace

### Deploy to Kubernetes

1. Update configuration in `../kubernetes-manifests/mcp-server.yaml` if needed
2. Run the deployment script:
   ```bash
   ../deploy.sh
   ```

The MCP server will be deployed to the `vigil-system` namespace and available at:
`mcp-server.vigil-system.svc.cluster.local:8000`

## Security Considerations

- The server runs as a non-root user (UID 1000)
- Read-only root filesystem for enhanced security
- Network policies restrict ingress/egress traffic
- Secrets are stored in Kubernetes Secrets (base64 encoded)
- JWT tokens are automatically refreshed to minimize exposure

## Monitoring

The server provides several monitoring endpoints and features:

- **Health Check**: `GET /health` - Returns server health status
- **Kubernetes Probes**: Liveness and readiness probes configured
- **Logging**: Structured logging with configurable levels
- **Metrics**: Basic HTTP metrics through FastAPI

## Troubleshooting

### Common Issues

1. **Authentication Failures**
   - Check `AUTH_USERNAME` and `AUTH_PASSWORD` configuration
   - Verify Bank of Anthos services are accessible
   - Check JWT token expiration settings

2. **Connection Issues**
   - Verify `BANK_BASE_URL` points to correct Bank of Anthos services
   - Check network policies and firewall rules
   - Ensure DNS resolution works in the cluster

3. **Performance Issues**
   - Adjust `REQUEST_TIMEOUT` if requests are timing out
   - Monitor resource usage and adjust limits/requests
   - Check for connection pool exhaustion

### Debugging

View server logs:
```bash
kubectl logs -l app=mcp-server -n vigil-system --follow
```

Check service status:
```bash
kubectl get pods -l app=mcp-server -n vigil-system
kubectl describe deployment mcp-server -n vigil-system
```

## Architecture Integration

This MCP server is part of the larger Vigil fraud detection system:

1. **Observer Agent** → Monitors Bank of Anthos transaction streams
2. **Analyst Agent** → Uses Gemini AI to analyze transaction risk
3. **Actuator Agent** → Takes protective actions based on analysis
4. **MCP Server** → Provides unified API access to Bank of Anthos services

All agents communicate with Bank of Anthos exclusively through this MCP server, ensuring consistent authentication, error handling, and API abstraction.

## License

This project is part of the Vigil fraud detection system for the GKE Turns 10 Hackathon.