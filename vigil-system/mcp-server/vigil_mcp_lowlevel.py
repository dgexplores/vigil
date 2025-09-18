#!/usr/bin/env python3
"""
Vigil MCP Server (Low-Level) - ADK-compatible MCP server implementation.

This provides a low-level MCP server implementation that's more compatible with
ADK deployment patterns and gives finer control over the MCP protocol.
"""

import asyncio
import json
import logging
import os
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

import httpx
import jwt
import mcp.types as types
from mcp.server.lowlevel import NotificationOptions, Server
from mcp.server.models import InitializationOptions
from pydantic import BaseModel, Field

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configuration
BANK_BASE_URL = os.getenv('BANK_BASE_URL', 'http://bank-of-anthos')
REQUEST_TIMEOUT = int(os.getenv('REQUEST_TIMEOUT', '30'))
AUTH_USERNAME = os.getenv('AUTH_USERNAME', 'admin')
AUTH_PASSWORD = os.getenv('AUTH_PASSWORD', 'password')
JWT_SECRET = os.getenv('JWT_SECRET', 'secret-key-change-in-production')


class AuthManager:
    """Manages JWT authentication for Bank of Anthos API calls."""
    
    def __init__(self):
        self.token: Optional[str] = None
        self.token_expiry: Optional[datetime] = None
        self.http_client = httpx.AsyncClient(timeout=REQUEST_TIMEOUT)
    
    async def get_valid_token(self) -> str:
        """Returns a valid JWT token, refreshing if necessary."""
        if self.token and self.token_expiry and datetime.utcnow() < self.token_expiry:
            return self.token
        
        await self._refresh_token()
        return self.token
    
    async def _refresh_token(self) -> None:
        """Refreshes the JWT token by authenticating with the user service."""
        try:
            response = await self.http_client.post(
                f"{BANK_BASE_URL}/login",
                json={
                    "username": AUTH_USERNAME,
                    "password": AUTH_PASSWORD
                }
            )
            response.raise_for_status()
            
            data = response.json()
            self.token = data.get('token')
            
            if not self.token:
                raise ValueError("No token received from login response")
            
            # Set token expiry to 45 minutes from now (assuming 1-hour token validity)
            self.token_expiry = datetime.utcnow() + timedelta(minutes=45)
            
            logger.info("JWT token refreshed successfully")
            
        except Exception as e:
            logger.error(f"Failed to refresh JWT token: {e}")
            raise RuntimeError(f"Authentication failed: {e}")
    
    async def close(self):
        """Close the HTTP client."""
        await self.http_client.aclose()


class BankAPIClient:
    """Client for making authenticated requests to Bank of Anthos microservices."""
    
    def __init__(self, auth_manager: AuthManager):
        self.auth_manager = auth_manager
        self.http_client = httpx.AsyncClient(timeout=REQUEST_TIMEOUT)
    
    async def _make_request(self, method: str, url: str, **kwargs) -> Dict[str, Any]:
        """Makes an authenticated HTTP request to a Bank of Anthos service."""
        token = await self.auth_manager.get_valid_token()
        
        headers = kwargs.get('headers', {})
        headers['Authorization'] = f'Bearer {token}'
        headers['Content-Type'] = 'application/json'
        kwargs['headers'] = headers
        
        try:
            response = await self.http_client.request(method, url, **kwargs)
            response.raise_for_status()
            return response.json()
            
        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error {e.response.status_code}: {e.response.text}")
            raise RuntimeError(f"Bank API error ({e.response.status_code}): {e.response.text}")
        except Exception as e:
            logger.error(f"Request failed: {e}")
            raise RuntimeError(f"Request failed: {str(e)}")
    
    async def get_transactions(self, account_id: str) -> Dict[str, Any]:
        """Retrieves transaction history for a given account."""
        url = f"{BANK_BASE_URL}/transactionhistory/transactions/{account_id}"
        return await self._make_request('GET', url)
    
    async def submit_transaction(self, transaction_data: Dict[str, Any]) -> Dict[str, Any]:
        """Submits a new transaction to the ledger."""
        url = f"{BANK_BASE_URL}/ledgerwriter/transactions"
        return await self._make_request('POST', url, json=transaction_data)
    
    async def get_user_details(self, user_id: str) -> Dict[str, Any]:
        """Retrieves user details from the user service."""
        url = f"{BANK_BASE_URL}/userservice/users/{user_id}"
        return await self._make_request('GET', url)
    
    async def lock_account(self, user_id: str, reason: str) -> Dict[str, Any]:
        """Locks a user account with the specified reason."""
        url = f"{BANK_BASE_URL}/userservice/users/{user_id}/lock"
        return await self._make_request('POST', url, json={"reason": reason})
    
    async def login(self, username: str, password: str) -> Dict[str, Any]:
        """Authenticates a user and returns a JWT token."""
        url = f"{BANK_BASE_URL}/userservice/login"
        return await self._make_request('POST', url, json={
            "username": username,
            "password": password
        })
    
    async def close(self):
        """Close the HTTP client."""
        await self.http_client.aclose()


# Global instances for server context
auth_manager = AuthManager()
bank_client = BankAPIClient(auth_manager)

# Create low-level MCP server
server = Server("vigil-mcp-server")


@server.list_tools()
async def handle_list_tools() -> List[types.Tool]:
    """List available tools for ADK agents."""
    return [
        types.Tool(
            name="get_transactions",
            description="Retrieve transaction history for a specific bank account",
            inputSchema={
                "type": "object",
                "properties": {
                    "account_id": {
                        "type": "string",
                        "description": "Unique identifier for the bank account"
                    }
                },
                "required": ["account_id"]
            }
        ),
        types.Tool(
            name="submit_transaction",
            description="Submit a new transaction to the banking ledger",
            inputSchema={
                "type": "object",
                "properties": {
                    "from_account": {
                        "type": "string",
                        "description": "Source account number"
                    },
                    "to_account": {
                        "type": "string",
                        "description": "Destination account number"
                    },
                    "amount": {
                        "type": "integer",
                        "description": "Transaction amount in cents"
                    },
                    "routing_number": {
                        "type": "string",
                        "description": "Bank routing number"
                    }
                },
                "required": ["from_account", "to_account", "amount", "routing_number"]
            }
        ),
        types.Tool(
            name="get_user_details",
            description="Retrieve detailed information about a specific user",
            inputSchema={
                "type": "object",
                "properties": {
                    "user_id": {
                        "type": "string",
                        "description": "Unique identifier for the user"
                    }
                },
                "required": ["user_id"]
            }
        ),
        types.Tool(
            name="lock_account",
            description="Lock a user account to prevent further transactions (fraud mitigation)",
            inputSchema={
                "type": "object",
                "properties": {
                    "user_id": {
                        "type": "string",
                        "description": "Unique identifier for the user"
                    },
                    "reason": {
                        "type": "string",
                        "description": "Reason for locking the account"
                    }
                },
                "required": ["user_id", "reason"]
            }
        ),
        types.Tool(
            name="authenticate_user",
            description="Authenticate a user and retrieve their JWT token",
            inputSchema={
                "type": "object",
                "properties": {
                    "username": {
                        "type": "string",
                        "description": "User's username"
                    },
                    "password": {
                        "type": "string",
                        "description": "User's password"
                    }
                },
                "required": ["username", "password"]
            }
        )
    ]


@server.call_tool()
async def handle_call_tool(name: str, arguments: Dict[str, Any]) -> List[types.ContentBlock]:
    """Handle tool calls from ADK agents and other MCP clients."""
    try:
        logger.info(f"Executing tool: {name} with arguments: {arguments}")
        
        if name == "get_transactions":
            result = await bank_client.get_transactions(arguments["account_id"])
            return [types.TextContent(type="text", text=json.dumps(result, indent=2))]
        
        elif name == "submit_transaction":
            transaction_data = {
                "fromAccount": arguments["from_account"],
                "toAccount": arguments["to_account"],
                "amount": arguments["amount"],
                "routingNumber": arguments["routing_number"]
            }
            result = await bank_client.submit_transaction(transaction_data)
            return [types.TextContent(type="text", text=json.dumps(result, indent=2))]
        
        elif name == "get_user_details":
            result = await bank_client.get_user_details(arguments["user_id"])
            return [types.TextContent(type="text", text=json.dumps(result, indent=2))]
        
        elif name == "lock_account":
            result = await bank_client.lock_account(arguments["user_id"], arguments["reason"])
            return [types.TextContent(type="text", text=json.dumps(result, indent=2))]
        
        elif name == "authenticate_user":
            result = await bank_client.login(arguments["username"], arguments["password"])
            return [types.TextContent(type="text", text=json.dumps(result, indent=2))]
        
        else:
            raise ValueError(f"Unknown tool: {name}")
    
    except Exception as e:
        error_msg = f"Tool execution failed: {str(e)}"
        logger.error(error_msg)
        return [types.TextContent(type="text", text=json.dumps({"error": error_msg}))]


@server.list_resources()
async def handle_list_resources() -> List[types.Resource]:
    """List available resources for ADK agents."""
    return [
        types.Resource(
            uri="vigil://config/bank-connection",
            name="Bank Connection Config",
            description="Current Bank of Anthos connection configuration",
            mimeType="application/json"
        ),
        types.Resource(
            uri="vigil://status/health",
            name="Server Health Status",
            description="Current health status of the Vigil MCP Server",
            mimeType="application/json"
        )
    ]


@server.read_resource()
async def handle_read_resource(uri: str) -> str:
    """Handle resource read requests."""
    if uri == "vigil://config/bank-connection":
        config = {
            "base_url": BANK_BASE_URL,
            "timeout": REQUEST_TIMEOUT,
            "auth_username": AUTH_USERNAME,
            "status": "configured"
        }
        return json.dumps(config, indent=2)
    
    elif uri == "vigil://status/health":
        status = {
            "status": "healthy",
            "timestamp": datetime.utcnow().isoformat(),
            "services": {
                "bank_api": "connected",
                "authentication": "active"
            },
            "version": "1.0.0"
        }
        return json.dumps(status, indent=2)
    
    else:
        raise ValueError(f"Unknown resource: {uri}")


async def run_stdio_server():
    """Run the MCP server using stdio transport (ADK compatible)."""
    import mcp.server.stdio
    
    logger.info("Starting Vigil MCP Server (Low-Level) with stdio transport")
    logger.info(f"Bank of Anthos base URL: {BANK_BASE_URL}")
    
    try:
        async with mcp.server.stdio.stdio_server() as (read_stream, write_stream):
            await server.run(
                read_stream,
                write_stream,
                InitializationOptions(
                    server_name="vigil-mcp-server",
                    server_version="1.0.0",
                    capabilities=server.get_capabilities(
                        notification_options=NotificationOptions(),
                        experimental_capabilities={},
                    ),
                ),
            )
    finally:
        await auth_manager.close()
        await bank_client.close()


async def run_streamable_http_server(host: str = "0.0.0.0", port: int = 8000):
    """Run the MCP server using streamable HTTP transport."""
    from mcp.server.streamable_http_manager import StreamableHTTPSessionManager
    from starlette.applications import Starlette
    from starlette.routing import Mount
    import uvicorn
    
    logger.info(f"Starting Vigil MCP Server (Low-Level) with streamable HTTP on {host}:{port}")
    logger.info(f"Bank of Anthos base URL: {BANK_BASE_URL}")
    
    # Create session manager
    session_manager = StreamableHTTPSessionManager()
    
    # Create ASGI app for the MCP server
    async def mcp_app(scope, receive, send):
        async with session_manager.connect_http(scope, receive, send) as streams:
            if streams is not None:
                read_stream, write_stream = streams
                await server.run(
                    read_stream,
                    write_stream,
                    InitializationOptions(
                        server_name="vigil-mcp-server",
                        server_version="1.0.0",
                        capabilities=server.get_capabilities(
                            notification_options=NotificationOptions(),
                            experimental_capabilities={},
                        ),
                    ),
                )
    
    # Create Starlette app
    starlette_app = Starlette(
        routes=[
            Mount("/mcp", app=mcp_app),
        ]
    )
    
    try:
        # Run with uvicorn
        config = uvicorn.Config(
            starlette_app,
            host=host,
            port=port,
            log_level="info"
        )
        server_instance = uvicorn.Server(config)
        await server_instance.serve()
    finally:
        await auth_manager.close()
        await bank_client.close()


if __name__ == "__main__":
    import click
    
    @click.command()
    @click.option("--transport", 
                  type=click.Choice(["stdio", "streamable-http"]), 
                  default="stdio",
                  help="Transport type")
    @click.option("--port", default=8000, help="Port for HTTP transport")
    @click.option("--host", default="0.0.0.0", help="Host for HTTP transport")
    def main(transport: str, port: int, host: str):
        """Run the Vigil MCP Server (Low-Level Implementation)."""
        if transport == "streamable-http":
            asyncio.run(run_streamable_http_server(host, port))
        else:  # stdio
            asyncio.run(run_stdio_server())
    
    main()