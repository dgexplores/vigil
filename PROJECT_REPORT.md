# Vigil System - Project Report & Systems Design Documentation

**Project**: Vigil - Real-time Fraud Detection System  
**Event**: GKE Turns 10 Hackathon 2025  
**Date**: September 19, 2025  
**Status**: In Development

## Executive Summary

Vigil is a fraud detection system built for the GKE Turns 10 Hackathon that fundamentally integrates the Model Context Protocol (MCP) for agent communication within a Kubernetes cluster. The system monitors Bank of Anthos transactions in real-time to detect and mitigate fraudulent activities through intelligent agents deployed in Google Kubernetes Engine (GKE).

## Table of Contents
- [System Architecture](#system-architecture)
- [Component Details](#component-details)
- [Implementation Journey](#implementation-journey)
- [Problems & Solutions](#problems--solutions)
- [Current System State](#current-system-state)
- [Technical Debt & Limitations](#technical-debt--limitations)
- [Recommendations](#recommendations)
- [Conclusion](#conclusion)

## System Architecture

### High-Level Architecture Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                        GKE Cluster                           │
│                                                              │
│  ┌─────────────────┐        ┌─────────────────┐            │
│  │ Bank of Anthos  │        │   Vigil System   │            │
│  │  Microservices  │        │                  │            │
│  │                 │        │ ┌──────────────┐ │            │
│  │ • userservice   │◄───────┤ │ MCP Server   │ │            │
│  │ • ledgerwriter  │        │ └──────▲───────┘ │            │
│  │ • transactionhist│        │        │         │            │
│  └─────────────────┘        │        │stdio    │            │
│                             │        │         │            │
│                             │ ┌──────▼───────┐ │            │
│                             │ │  MCP Proxy   │ │            │
│                             │ └──────▲───────┘ │            │
│                             │        │         │            │
│                             │ ┌──────▼───────┐ │            │
│                             │ │   Observer   │ │            │
│                             │ │    Agent     │ │            │
│                             │ └──────────────┘ │            │
│                             └──────────────────┘            │
└─────────────────────────────────────────────────────────────┘
                                    │
                              Port Forward
                                    │
                                    ▼
                            ┌─────────────┐
                            │ Warp Terminal│
                            │  MCP Client  │
                            └─────────────┘
```

### Core Technologies
- **Container Orchestration**: Google Kubernetes Engine (GKE)
- **Protocol**: Model Context Protocol (MCP) v2024-11-05
- **Agent Framework**: Google Agent Development Kit (ADK) v1.14.1
- **Language**: Python 3.11
- **Banking Backend**: Bank of Anthos microservices
- **Development Environment**: Warp Terminal with MCP integration

## Component Details

### 1. MCP Server (`mcp-server`)

**Technology Stack**:
- Python-based FastMCP server
- Protocol: MCP over HTTP/SSE
- Service Port: 8000

**Functionality**:
- Exposes Bank of Anthos operations as MCP tools
- Handles authentication and transaction queries
- Provides tool discovery via `/capabilities` endpoint
- Manages account operations for fraud mitigation

**Available MCP Tools**:
| Tool Name | Purpose | Parameters |
|-----------|---------|------------|
| `authenticate_user` | JWT token generation | username, password |
| `get_transactions` | Retrieve transaction history | account_id |
| `get_user_details` | Fetch user account information | user_id |
| `lock_account` | Fraud mitigation action | user_id, reason |
| `submit_transaction` | Create new transactions | from_account, to_account, amount, routing_number |

### 2. Observer Agent (`vigil-observer`)

**Technology Stack**:
- Python 3.11 with async/await
- Google ADK for agent orchestration
- MCP toolset integration

**Architecture Pattern**: 
- LLM Agent with MCP toolset integration
- Subprocess-based MCP client communication
- Health monitoring with Kubernetes probes

**Key Components**:
```python
# Main Components
TransactionProcessor    # Core monitoring logic
McpToolset             # ADK integration for MCP tools
mcp_cluster_proxy.py   # stdio-to-HTTP bridge
health_server          # K8s health/readiness endpoints
```

**Monitoring Configuration**:
- Polling Interval: 5 seconds
- Batch Size: 100 transactions
- Health Endpoints: `/health`, `/ready`, `/metrics`

### 3. MCP Cluster Proxy

**Purpose**: Bridge between stdio-based MCP client protocol and HTTP-based MCP server

**Protocol Translation Flow**:
```
ADK Agent → JSON-RPC/stdio → Subprocess → Proxy → HTTP/REST → MCP Server
```

**Implementation Details**:
- Subprocess spawned by Observer Agent
- Handles protocol version negotiation
- Manages tool discovery and invocation
- Error handling and logging

### 4. Kubernetes Infrastructure

**Deployments**:
```yaml
Deployments:
  - mcp-server (1 replica)
  - vigil-observer (1 replica)
  
Services:
  - mcp-server (ClusterIP, port 8000)
  
Container Registry:
  - gcr.io/vigil-demo-hackathon/vigil-observer-agent
  - gcr.io/vigil-demo-hackathon/mcp-server
```

## Implementation Journey

### Phase 1: Initial Setup ✅
- Deployed Bank of Anthos in GKE cluster
- Created MCP server with banking tool integrations
- Established basic Kubernetes deployments

### Phase 2: MCP Integration 🔄
- Implemented MCP server with FastMCP
- Created stdio-to-HTTP proxy for cluster communication
- Integrated ADK MCP toolset with Observer agent

### Phase 3: Protocol Refinement ✅
- Fixed protocol version compatibility (1.0.0 → 2024-11-05)
- Resolved Python path issues in containers
- Corrected syntax errors in proxy implementation

### Phase 4: ADK Integration Challenges ⚠️
- Attempted multiple tool invocation patterns
- Converted to LlmAgent for better MCP support
- Encountered execution model mismatches

## Problems & Solutions

### ✅ Resolved Issues

#### 1. MCP Protocol Version Mismatch
- **Problem**: Client rejected protocol version "1.0.0"
- **Solution**: Updated to standard version "2024-11-05"
- **Impact**: Enabled successful MCP handshake

#### 2. Container Python Path Issues
- **Problem**: Subprocess couldn't find Python interpreter
- **Solution**: Explicitly specified `/usr/local/bin/python3`
- **Impact**: Proxy subprocess launches successfully

#### 3. Proxy Syntax Errors
- **Problem**: Malformed JSON construction in proxy (line 126)
- **Solution**: Fixed parentheses, rebuilt without cache
- **Impact**: Proxy handles requests correctly

#### 4. Demo Data Fallback
- **Problem**: Agent using demo data instead of MCP
- **Solution**: Removed all demo data generation code
- **Impact**: Forces real MCP communication

### ⚠️ Partially Resolved Issues

#### 5. ADK Tool Invocation
- **Problem**: No straightforward programmatic tool access
- **Attempted Solutions**:
  - Direct invocation methods (`execute`, `invoke`, `run`) - Failed
  - `run_async()` with parameters - Failed
  - `process_llm_request()` - Failed
  - LlmAgent conversion - Partially successful
- **Current State**: MCP communication works, tool execution challenging

### ❌ Unresolved Issues

#### 6. LLM Agent Execution Model
- **Problem**: LlmAgent lacks expected execution methods
- **Analysis**: Agent is configuration object, not executable
- **Impact**: Cannot trigger tool calls programmatically

## Current System State

### ✅ What's Working
1. **MCP Server**: Successfully deployed and running
2. **Protocol Communication**: Full MCP handshake successful
3. **Tool Discovery**: All tools discovered from server
4. **Health Monitoring**: K8s probes operational
5. **Infrastructure**: All pods healthy and running
6. **Port Forwarding**: External MCP client connectivity

### ❌ What's Not Working
1. **Tool Execution**: Cannot pass parameters to MCP tools
2. **Data Retrieval**: No transaction data being fetched
3. **Agent Execution**: LLM agent model mismatch

### System Metrics
```
Component Status:
- MCP Server: RUNNING ✅
- Observer Agent: RUNNING ✅
- MCP Communication: ESTABLISHED ✅
- Tool Discovery: SUCCESS ✅
- Tool Execution: FAILED ❌
- Transaction Monitoring: INACTIVE ❌
```

## Technical Debt & Limitations

### 1. Framework Impedance Mismatch
The Google ADK assumes LLM-driven conversational agents, while our use case requires deterministic, programmatic tool invocation.

### 2. Missing Dependencies
The `google.adk.llm` module referenced in documentation is unavailable, limiting proper LLM message construction.

### 3. Documentation Gaps
- Limited examples of programmatic MCP tool invocation
- Unclear LlmAgent execution patterns
- Missing MCP-ADK integration guides

### 4. Architectural Complexity
Multiple abstraction layers complicate debugging:
```
ADK Agent → MCP Toolset → Subprocess → Proxy → HTTP → MCP Server
```

## Recommendations

### Immediate Actions
1. **Direct MCP Client**: Consider bypassing ADK for direct MCP communication
2. **Custom Wrapper**: Build translation layer for programmatic calls
3. **Alternative Framework**: Evaluate other agent frameworks with MCP support

### Long-term Improvements
1. **Simplify Architecture**: Reduce abstraction layers
2. **Comprehensive Logging**: Add detailed tracing at each layer
3. **Integration Testing**: Create component interaction tests
4. **Documentation**: Document working patterns for future reference

## Conclusion

### Achievements ✅
- **Successful MCP Integration**: Demonstrated MCP protocol working in Kubernetes
- **Tool Discovery**: Automatic tool discovery from MCP server functioning
- **Infrastructure**: Robust Kubernetes deployment with health monitoring
- **Protocol Compliance**: Proper MCP version negotiation and handshake

### Challenges ❌
- **Execution Model**: ADK's LLM-oriented design doesn't match our needs
- **Tool Invocation**: Cannot programmatically invoke MCP tools with parameters
- **Framework Limitations**: ADK abstractions prevent direct tool access

### Key Takeaway
The Vigil system successfully demonstrates MCP protocol integration in a Kubernetes environment with proper tool discovery and protocol negotiation. The primary challenge remains the impedance mismatch between ADK's conversational AI design and our need for deterministic, programmatic monitoring.

**Project Status**: Proof of concept successful for MCP communication; tool execution requires alternative approach.

---

*This report documents the state of the Vigil project as of September 19, 2025, during the GKE Turns 10 Hackathon.*