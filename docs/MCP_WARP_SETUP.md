# Vigil MCP Client Configuration for Warp Terminal

This document explains how to set up and use the Vigil MCP (Model Context Protocol) client with Warp Terminal to interact with the Bank of Anthos fraud detection system running on GKE.

## Prerequisites

1. **GKE Cluster Access**: Ensure you have `kubectl` configured to access your GKE cluster
2. **Python 3**: The MCP client requires Python 3.8 or higher
3. **Warp Terminal**: Install Warp terminal with MCP support enabled

## Setup Instructions

### 1. Configure Warp MCP Settings

Add the configuration from `vigil-warp-mcp-config.json` to your Warp MCP settings:

1. Open Warp Settings → Features → MCP
2. Click "Add Server Configuration"
3. Copy the contents of `vigil-warp-mcp-config.json`:

```json
{
  "vigil-bank-anthos": {
    "command": "python3",
    "args": [
      "/home/zenkit/Hackathon/GKE Turns 10 Hackathon Devpost 2025/gke-turns10-hackathon-vigil/vigil-mcp-client.py"
    ],
    "env": {
      "AUTH_PASSWORD": "bankofanthos",
      "AUTH_USERNAME": "testuser",
      "REQUEST_TIMEOUT": "30",
      "MCP_SERVER_URL": "http://localhost:8000",
      "BANK_BASE_URL": "http://localhost:8080",
      "LOG_LEVEL": "INFO"
    }
  }
}
```

### 2. Set Up Port Forwarding

The MCP client needs access to services running in the GKE cluster. Open two separate terminals and run:

```bash
# Terminal 1: Forward MCP Server
kubectl port-forward svc/mcp-server 8000:8000

# Terminal 2: Forward Bank of Anthos Frontend
kubectl port-forward svc/frontend 8080:80
```

Keep these terminals open while using the MCP client.

### 3. Test the Connection

Once configured, the MCP client should be available in Warp. You can test it by:

1. Opening a new Warp terminal session
2. The MCP server should automatically connect if configured correctly
3. You should see the Vigil tools available in Warp's AI assistant

## Available MCP Tools

The Vigil MCP server provides the following tools:

- **get_transactions**: Retrieve transaction history for an account
- **get_user_details**: Get user account information
- **lock_account**: Lock a user account (fraud prevention)
- **authenticate_user**: Authenticate and get JWT token
- **submit_transaction**: Submit a new transaction

## Troubleshooting

### Port Forward Issues
If you see warnings about missing port forwards:
1. Ensure kubectl is configured: `kubectl config current-context`
2. Check pod status: `kubectl get pods | grep -E '(mcp|frontend)'`
3. Restart port forwards if needed

### MCP Connection Issues
If the MCP server doesn't connect:
1. Check logs: `tail -f ~/.warp/logs/mcp.log` (if available)
2. Verify Python dependencies are installed in the virtual environment
3. Test the wrapper script directly: `python3 vigil-mcp-client.py`

### Authentication Errors
Default credentials are:
- Username: `testuser`
- Password: `bankofanthos`

These can be modified in the environment variables in the configuration.

## Architecture

```
Warp Terminal
     ↓
vigil-mcp-client.py (wrapper script)
     ↓
vigil_mcp_server.py (MCP server in STDIO mode)
     ↓
kubectl port-forward
     ↓
GKE Cluster Services
  - MCP Server Pod
  - Bank of Anthos Frontend
  - Transaction History Service
  - User Service
  - Ledger Writer
```

## Security Considerations

- The MCP client uses local port forwarding for secure access to GKE services
- JWT tokens are managed automatically by the MCP server
- Credentials should be stored securely and not committed to version control
- For production, use proper authentication and secrets management

## Support

For issues or questions about the Vigil MCP integration, please refer to:
- Project repository: `/vigil-system/mcp-server/`
- MCP Server logs: Check the terminal output when running the client
- GKE cluster logs: `kubectl logs -f deployment/mcp-server`