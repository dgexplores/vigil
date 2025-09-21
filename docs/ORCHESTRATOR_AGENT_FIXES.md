# Orchestrator Agent CrashLoop Fix Documentation

## Overview

This document details the comprehensive fixes applied to resolve the orchestrator agent CrashLoopBackOff issue in the Vigil AI Fraud Shield deployment. The fixes address import path errors, Docker build context issues, and API compatibility problems between Google ADK and the A2A protocol.

## Problem Summary

The orchestrator agent was experiencing a CrashLoopBackOff with the error:
```
ModuleNotFoundError: No module named 'google.adk.rpc'
```

## Root Causes Identified

### 1. Docker Build Context Issues
- **Problem**: Dockerfile was copying from current directory (`.`) but build was executed from project root
- **Impact**: `requirements.txt` file was not found during Docker build
- **Symptoms**: Build failures during `pip install -r requirements.txt`

### 2. Incorrect A2A Protocol Imports  
- **Problem**: Code was importing A2A classes from `google.adk.rpc` which doesn't exist
- **Reality**: A2A protocol is a separate package (`a2a-sdk`) from Google ADK
- **Impact**: Runtime import errors preventing agent startup

### 3. Google ADK API Incompatibility
- **Problem**: Code used outdated/incorrect ADK API patterns
- **Issues**: 
  - Non-existent `@tool` decorator
  - Non-existent `@rpc` decorator
  - Wrong FunctionTool constructor parameters
  - Missing required LlmAgent fields

## Detailed Fixes Applied

### Fix 1: Docker Build Context Correction

**Files Modified**: 
- `vigil-system/orchestrator_agent/Dockerfile`
- `vigil-system/transaction_monitor_agent/Dockerfile`

**Before**:
```dockerfile
COPY . /app/
```

**After**:
```dockerfile
COPY vigil-system/orchestrator_agent/requirements.txt /app/
COPY vigil-system/orchestrator_agent/agent.py /app/
```

**Rationale**: Ensures correct files are copied when building from project root directory.

### Fix 2: A2A Protocol Integration

**Files Modified**: 
- `vigil-system/orchestrator_agent/requirements.txt`
- `vigil-system/orchestrator_agent/agent.py`

**Requirements Update**:
```txt
google-adk
a2a-sdk
```

**Import Changes**:
```python
# Before (incorrect)
from google.adk.rpc import A2AServer, A2AClient, rpc

# After (correct)  
from a2a.client import ClientFactory
```

**Client Creation Changes**:
```python
# Before (deprecated)
investigation_client = A2AClient(INVESTIGATION_AGENT_URL)

# After (modern API)
def create_client(url):
    return ClientFactory.create_client_with_jsonrpc_transport(url=url)

investigation_client = None  # Lazy initialization
```

### Fix 3: Google ADK API Compatibility

**Function Tool Creation**:
```python
# Before (incorrect parameters)
investigation_tool = FunctionTool(
    name="delegate_to_investigation_agent",
    description="...",
    function=delegate_to_investigation_agent
)

# After (correct API)
investigation_tool = FunctionTool(delegate_to_investigation_agent)
```

**LlmAgent Configuration**:
```python
# Before (missing required field)
self.llm_agent = LlmAgent(
    model=Gemini(api_key=GEMINI_API_KEY),
    instruction=ORCHESTRATOR_PROMPT,
    tools=[...],
)

# After (with required name field)
self.llm_agent = LlmAgent(
    name="orchestrator_agent",  # Must be valid identifier
    model=Gemini(api_key=GEMINI_API_KEY),
    instruction=ORCHESTRATOR_PROMPT,
    tools=[...],
)
```

### Fix 4: Simulation Mode Implementation

Since other agents are not yet deployed, implemented simulation mode:

```python
def delegate_to_investigation_agent(transaction_details: str) -> str:
    logger.info(f"Delegating to InvestigationAgent with transaction: {transaction_details}")
    try:
        global investigation_client
        if investigation_client is None:
            investigation_client = create_client(INVESTIGATION_AGENT_URL)
        
        # Simulation mode for development
        logger.info("Simulating investigation response (other agents not yet deployed)")
        return json.dumps({
            "status": "investigation_completed",
            "risk_score": 0.75,
            "findings": "High-value transaction to new recipient",
            "recommendation": "Review required"
        })
    except Exception as e:
        logger.error(f"Error calling InvestigationAgent: {e}", exc_info=True)
        return f"Error: {e}"
```

## Testing and Validation

### Docker Image Testing
```bash
# Build test
docker build -t orchestrator-agent:test -f vigil-system/orchestrator_agent/Dockerfile .

# Runtime test
docker run --rm -e GEMINI_API_KEY="test-key" orchestrator-agent:test timeout 3 python agent.py
```

**Expected Output**:
```
INFO - Starting OrchestratorAgent...
INFO - Initializing OrchestratorService...
INFO - OrchestratorService initialized.
INFO - OrchestratorAgent service created successfully
INFO - OrchestratorAgent is ready to receive requests
```

### Kubernetes Deployment Validation
```bash
# Check pod status
kubectl get pods -l app=orchestrator-agent

# Expected status: Running with 0 restarts
NAME                                  READY   STATUS    RESTARTS   AGE
orchestrator-agent-54dcbdf648-9xxtj   1/1     Running   0          5m
```

## Key Learnings

### 1. A2A Protocol Architecture
- A2A is an independent protocol, not part of Google ADK
- Uses separate `a2a-sdk` Python package
- Modern API uses `ClientFactory.create_client_with_jsonrpc_transport()`
- Legacy `A2AClient` constructor is deprecated

### 2. Google ADK Current API
- `LlmAgent` requires a `name` field (valid Python identifier)
- `FunctionTool` constructor only accepts the function, no metadata
- No `@tool` or `@rpc` decorators in current version
- Tools are passed as list to `LlmAgent` constructor

### 3. Docker Build Best Practices
- Always specify exact file paths when building from different contexts
- Use `COPY source destination` explicitly rather than copying entire directories
- Validate build context matches Dockerfile expectations

## Dependencies and Versions

```txt
google-adk==1.14.1
a2a-sdk==latest
```

## Future Improvements

1. **Complete A2A Integration**: Implement actual A2A communication once all agents are deployed
2. **Error Handling**: Add more robust error handling for A2A communication failures  
3. **Observability**: Add structured logging and metrics for monitoring
4. **Configuration**: Move hardcoded URLs to environment variables or ConfigMaps

## Related Issues

- Original CrashLoopBackOff: `ModuleNotFoundError: No module named 'google.adk.rpc'`
- Docker build failures: Missing requirements.txt during build
- ADK API validation errors: Missing required fields and incorrect constructors

## References

- [Google ADK Documentation](https://github.com/google/adk-docs)
- [A2A Protocol Repository](https://github.com/a2aproject/A2A)
- [A2A Python SDK](https://pypi.org/project/a2a-sdk/)