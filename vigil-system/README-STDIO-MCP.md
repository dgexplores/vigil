# Vigil MCP Stdio Communication Refactoring

## Overview

This refactoring transforms the Vigil system's MCP (Model Context Protocol) server from an HTTP-based service to a stdio-based subprocess communication model. This change enables true sidecar deployment where the MCP server runs as a child process of each agent, communicating via standard input/output streams.

## Architecture Changes

### Before (HTTP-based)
- MCP server deployed as a separate pod/container
- Agents communicate with MCP server via HTTP/REST
- Network overhead and potential connectivity issues
- Complex service discovery and load balancing

### After (Stdio-based)
- MCP server runs as a subprocess within the agent container
- Direct stdio communication (stdin/stdout)
- Zero network overhead for MCP communication
- Simplified deployment and improved reliability

## Components

### 1. MCP Stdio Server (`mcp-server/vigil_mcp_stdio_server.py`)
- Wrapper that runs the MCP server in stdio transport mode
- Handles environment configuration
- Logs to stderr to avoid polluting stdout

### 2. MCP Stdio Client (`observer-agent/mcp_stdio_client.py`)
- Uses the official MCP Python SDK
- Manages subprocess lifecycle
- Handles stdio communication with proper MCP protocol

### 3. Updated Observer Agent (`observer-agent/agent.py`)
- Modified to use `MCPStdioClient` instead of raw JSON-RPC
- Maintains all existing functionality
- Improved error handling and connection management

### 4. Deployment Configuration
- Single container deployment (no sidecar needed)
- MCP server launched as subprocess
- Simplified Kubernetes manifests

## Building and Deployment

### Build the Docker Image

```bash
cd vigil-system
chmod +x build-observer-stdio.sh
./build-observer-stdio.sh
```

Or manually:

```bash
cd vigil-system
docker build -f observer-agent/Dockerfile.stdio -t vigil-observer-stdio:latest .
```

### Push to Registry

```bash
# Tag for GCR
docker tag vigil-observer-stdio:latest gcr.io/vigil-demo-hackathon/vigil-observer-stdio:latest

# Push to GCR
docker push gcr.io/vigil-demo-hackathon/vigil-observer-stdio:latest
```

### Deploy to Kubernetes

```bash
# Deploy the stdio-based observer
kubectl apply -f k8s/observer-deployment-stdio.yaml

# Check deployment status
kubectl get pods -l app=vigil-observer-stdio

# Check logs
kubectl logs -l app=vigil-observer-stdio
```

## Testing

### Local Testing

Run the test script to verify stdio communication:

```bash
cd vigil-system
python test_stdio_integration.py
```

### In-Container Testing

```bash
docker run --rm -it vigil-observer-stdio:latest python test_stdio_integration.py
```

### Testing in Kubernetes

```bash
# Port-forward to access health endpoints
kubectl port-forward deployment/vigil-observer-stdio 8000:8000

# Check health
curl http://localhost:8000/health
curl http://localhost:8000/ready
curl http://localhost:8000/metrics
```

## Benefits of Stdio Communication

1. **Reliability**: No network failures between agent and MCP server
2. **Performance**: Zero network latency for MCP calls
3. **Security**: No exposed MCP endpoints, communication stays within container
4. **Simplicity**: Single container deployment, easier to manage
5. **Resource Efficiency**: No separate MCP server pods needed

## Migration Guide

### For Existing Deployments

1. Build and push the new image
2. Deploy the stdio-based version alongside existing deployment
3. Verify functionality with the new deployment
4. Switch traffic to new deployment
5. Remove old deployment

```bash
# Deploy new version
kubectl apply -f k8s/observer-deployment-stdio.yaml

# Wait for ready
kubectl wait --for=condition=ready pod -l app=vigil-observer-stdio

# Scale down old deployment
kubectl scale deployment vigil-observer --replicas=0

# After verification, delete old deployment
kubectl delete deployment vigil-observer
```

## Environment Variables

The following environment variables configure both the observer agent and MCP server:

### Observer Agent
- `MCP_SERVER_PATH`: Path to MCP server script (default: `/app/vigil_mcp_stdio_server.py`)
- `OBSERVER_PORT`: Health check port (default: `8000`)
- `POLLING_INTERVAL`: Transaction polling interval in seconds (default: `5`)
- `BATCH_SIZE`: Transaction batch size (default: `100`)

### MCP Server (subprocess)
- `BANK_BASE_URL`: Bank of Anthos API base URL
- `REQUEST_TIMEOUT`: API request timeout in seconds
- `AUTH_USERNAME`: Authentication username
- `AUTH_PASSWORD`: Authentication password
- `JWT_SECRET`: JWT signing secret
- `LOG_LEVEL`: Logging level (debug, info, warning, error)

## Troubleshooting

### MCP Server Not Starting

Check logs for the observer pod:
```bash
kubectl logs -l app=vigil-observer-stdio --tail=100
```

Look for MCP server initialization messages.

### Connection Issues

Verify the MCP server script is present:
```bash
kubectl exec -it <pod-name> -- ls -la /app/vigil_mcp_stdio_server.py
```

### Testing MCP Communication

Run the test inside the container:
```bash
kubectl exec -it <pod-name> -- python -c "
from mcp_stdio_client import MCPStdioClient
import asyncio

async def test():
    client = MCPStdioClient()
    connected = await client.connect()
    print(f'Connected: {connected}')
    if connected:
        await client.close()

asyncio.run(test())
"
```

## Future Improvements

1. **Connection pooling**: Reuse MCP subprocess for better performance
2. **Health monitoring**: Add MCP server health to agent health checks
3. **Metrics**: Export MCP call metrics for monitoring
4. **Circuit breaker**: Add circuit breaker pattern for MCP calls
5. **Retry logic**: Implement exponential backoff for failed calls

## Related Files

- `vigil-system/mcp-server/vigil_mcp_stdio_server.py` - MCP stdio server wrapper
- `vigil-system/observer-agent/mcp_stdio_client.py` - MCP stdio client
- `vigil-system/observer-agent/agent.py` - Updated observer agent
- `vigil-system/observer-agent/Dockerfile.stdio` - Container build file
- `vigil-system/k8s/observer-deployment-stdio.yaml` - Kubernetes deployment
- `vigil-system/test_stdio_integration.py` - Integration tests
- `vigil-system/build-observer-stdio.sh` - Build script