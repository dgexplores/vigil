#!/usr/bin/env python3
"""
Example ADK agent that connects to the Vigil MCP Server.

This demonstrates how to use Google ADK agents as MCP clients to access
the Vigil fraud detection banking tools.
"""

import os
from google.adk.agents import LlmAgent
from google.adk.tools.mcp_tool.mcp_toolset import MCPToolset
from google.adk.tools.mcp_tool.mcp_session_manager import StdioConnectionParams
from mcp import StdioServerParameters

# IMPORTANT: Replace this with the ABSOLUTE path to your vigil_mcp_lowlevel.py script
PATH_TO_VIGIL_MCP_SERVER = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), 
    "..", 
    "vigil_mcp_lowlevel.py"
)

if not os.path.exists(PATH_TO_VIGIL_MCP_SERVER):
    print(f"WARNING: MCP server script not found at {PATH_TO_VIGIL_MCP_SERVER}")
    print("Please update the PATH_TO_VIGIL_MCP_SERVER variable in this file.")

# Synchronous agent definition (required for ADK deployment)
root_agent = LlmAgent(
    model='gemini-2.5-flash',
    name='vigil_fraud_detection_agent',
    instruction="""You are the Vigil fraud detection assistant. You have access to banking 
    operations through secure MCP tools. You can:
    
    1. Retrieve transaction histories for accounts
    2. Submit new transactions to the banking system
    3. Get detailed user information
    4. Lock accounts when fraud is suspected
    5. Authenticate users
    
    Always be careful with banking operations and ask for confirmation before:
    - Submitting transactions
    - Locking user accounts
    - Accessing sensitive user data
    
    Use the tools responsibly and explain what each operation does before performing it.""",
    tools=[
        MCPToolset(
            connection_params=StdioConnectionParams(
                server_params=StdioServerParameters(
                    command='python3',
                    args=[PATH_TO_VIGIL_MCP_SERVER, '--transport', 'stdio']
                )
            ),
            # Optional: Filter which tools are exposed to the agent
            # Uncomment and customize as needed:
            # tool_filter=['get_transactions', 'get_user_details', 'lock_account']
        )
    ],
)


# Alternative: Asynchronous agent definition (for adk web development)
async def get_agent_async():
    """Creates an ADK Agent equipped with tools from the Vigil MCP Server."""
    return LlmAgent(
        model='gemini-2.5-flash',
        name='vigil_fraud_detection_agent_async',
        instruction="""You are the Vigil fraud detection assistant. You have access to banking 
        operations through secure MCP tools for detecting and preventing fraud.""",
        tools=[
            MCPToolset(
                connection_params=StdioConnectionParams(
                    server_params=StdioServerParameters(
                        command='python3',
                        args=[PATH_TO_VIGIL_MCP_SERVER, '--transport', 'stdio']
                    )
                )
            )
        ],
    )