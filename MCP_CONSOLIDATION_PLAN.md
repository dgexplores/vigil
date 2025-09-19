# MCP Files Consolidation Plan

## Current Structure Analysis

### MCP Server Components

1. **Core MCP Server** (`mcp-server/vigil_mcp_server.py`)
   - 506 lines
   - Main MCP server using FastMCP
   - Implements tools: get_transactions, submit_transaction, get_user_details, lock_account, authenticate_user
   - Supports multiple transports: stdio, sse, streamable-http
   - Direct integration with Bank of Anthos APIs

2. **Stdio Wrapper** (`mcp-server/vigil_mcp_stdio_server.py`)
   - 59 lines
   - Thin wrapper that runs vigil_mcp_server in stdio mode
   - Sets environment variables and launches the main server
   - Used for sidecar deployments

3. **REST Wrapper** (`mcp-server/vigil_mcp_rest_wrapper.py`)
   - 428 lines
   - FastAPI server exposing MCP tools as REST endpoints
   - Provides JSON-RPC bridge at root endpoint "/"
   - Duplicates Bank API client logic from main server
   - Used for in-cluster HTTP communication

4. **Low-level MCP** (`shared/vigil_mcp_lowlevel.py`)
   - 493 lines
   - Centralized in shared/ directory
   - Symlinked from mcp-server/ and observer-agent/
   - Contains low-level MCP protocol implementation

### MCP Client Components (in observer-agent/)

1. **mcp_client_bridge.py** - Bridge for MCP client connections
2. **mcp_cluster_proxy.py** - Proxy for in-cluster MCP access
3. **mcp_stdio_client.py** - Client for stdio-based MCP communication

## Issues Identified

### 1. Code Duplication
- BankAPIClient logic duplicated between vigil_mcp_server.py and vigil_mcp_rest_wrapper.py
- Transaction fetching with DB fallback implemented in both places
- Authentication logic repeated

### 2. Multiple Transport Wrappers
- Three different ways to expose the same tools (stdio, REST, JSON-RPC)
- Each wrapper has its own configuration and setup

### 3. Symlink Management
- vigil_mcp_lowlevel.py correctly centralized but symlinks need maintenance
- Some Dockerfiles copy symlinks incorrectly

## Consolidation Strategy

### Phase 1: Centralize Bank API Client

1. Create `shared/bank_api_client.py`
   - Extract BankAPIClient from both server files
   - Include all methods: authenticate, get_transactions, submit_transaction, etc.
   - Include DB fallback logic in one place

2. Update servers to import from shared:
   - `vigil_mcp_server.py` imports BankAPIClient
   - `vigil_mcp_rest_wrapper.py` imports BankAPIClient

### Phase 2: Simplify Transport Layer

1. Keep `vigil_mcp_server.py` as the core MCP implementation
2. Keep `vigil_mcp_stdio_server.py` as a thin wrapper (already minimal)
3. Refactor `vigil_mcp_rest_wrapper.py`:
   - Import and call vigil_mcp_server tools directly
   - Remove duplicate business logic
   - Focus only on HTTP/JSON-RPC translation

### Phase 3: Consolidate Client Components

1. Review if all three client files are needed:
   - mcp_client_bridge.py
   - mcp_cluster_proxy.py  
   - mcp_stdio_client.py

2. Consider merging into a single configurable client

### Phase 4: Clean Up File Structure

```
vigil-system/
├── shared/
│   ├── vigil_mcp_lowlevel.py     # Low-level MCP protocol
│   └── bank_api_client.py        # Centralized Bank API client
├── mcp-server/
│   ├── vigil_mcp_server.py       # Core MCP server
│   ├── vigil_mcp_stdio_server.py # Stdio wrapper (minimal)
│   └── vigil_mcp_rest_wrapper.py # REST/JSON-RPC wrapper (simplified)
└── observer-agent/
    ├── agent.py
    └── mcp_client.py             # Unified MCP client
```

## Implementation Steps

1. **Extract shared components**
   - Create shared/bank_api_client.py
   - Move common authentication and API logic

2. **Update imports**
   - Modify both server files to use shared client
   - Update Dockerfiles to copy shared files correctly

3. **Test each transport**
   - Verify stdio mode works
   - Verify REST endpoints work
   - Verify JSON-RPC bridge works

4. **Remove duplicates**
   - Delete redundant code
   - Consolidate configuration

5. **Update documentation**
   - Document the simplified structure
   - Update deployment guides

## Benefits

1. **Reduced maintenance**: Single source of truth for Bank API integration
2. **Consistency**: Same business logic across all transports
3. **Modularity**: Clear separation of concerns
4. **Testability**: Easier to test shared components
5. **Smaller images**: Less duplicate code in Docker images