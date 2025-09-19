#!/usr/bin/env python3
"""
Vigil MCP Server - Model Context Protocol server for Bank of Anthos API integration.

This server provides a standardized interface to the Bank of Anthos microservices,
allowing AI agents to interact with banking APIs through MCP tools.
"""

import asyncio
import json
import logging
import os
import sys
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, Optional

from pydantic import BaseModel, Field

from mcp.server.fastmcp import Context, FastMCP

# Add parent directory to path to import shared modules
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from shared.bank_api_client import BankAPIClient, AuthManager

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configuration
BANK_BASE_URL = os.getenv('BANK_BASE_URL', 'http://userservice:8080')
REQUEST_TIMEOUT = int(os.getenv('REQUEST_TIMEOUT', '30'))
AUTH_USERNAME = os.getenv('AUTH_USERNAME', 'testuser')
AUTH_PASSWORD = os.getenv('AUTH_PASSWORD', 'bankofanthos')


@dataclass
class VigilContext:
    """Application context with Bank of Anthos API clients."""
    
    auth_manager: AuthManager
    bank_client: BankAPIClient


# AuthManager and BankAPIClient are now imported from shared.bank_api_client


    


@asynccontextmanager
async def app_lifespan(server: FastMCP) -> AsyncIterator[VigilContext]:
    """Manage application lifecycle with Bank of Anthos API clients."""
    # Initialize on startup
    auth_manager = AuthManager()
    bank_client = BankAPIClient(auth_manager=auth_manager)
    
    logger.info("Vigil MCP Server starting up...")
    logger.info(f"Bank of Anthos base URL: {BANK_BASE_URL}")
    
    try:
        yield VigilContext(auth_manager=auth_manager, bank_client=bank_client)
    finally:
        # Cleanup on shutdown
        logger.info("Shutting down Vigil MCP Server...")
        await auth_manager.close()
        await bank_client.close()


# Create MCP server
mcp = FastMCP(
    "Vigil MCP Server", 
    lifespan=app_lifespan,
    host="0.0.0.0",
    port=8000
)


# Structured output models
class Transaction(BaseModel):
    """Transaction data structure."""
    transaction_id: str = Field(description="Unique transaction identifier")
    from_account: str = Field(description="Source account number")
    to_account: str = Field(description="Destination account number") 
    amount: int = Field(description="Transaction amount in cents")
    timestamp: str = Field(description="Transaction timestamp")
    status: str = Field(description="Transaction status")
    description: Optional[str] = Field(default=None, description="Transaction description")


class TransactionHistory(BaseModel):
    """Transaction history response."""
    account_id: str = Field(description="Account identifier")
    transactions: List[Transaction] = Field(description="List of transactions")
    total_count: int = Field(description="Total number of transactions")


class TransactionResult(BaseModel):
    """Transaction submission result."""
    transaction_id: str = Field(description="Generated transaction ID")
    status: str = Field(description="Transaction status")
    message: str = Field(description="Result message")
    timestamp: str = Field(description="Submission timestamp")


class UserDetails(BaseModel):
    """User details structure."""
    user_id: str = Field(description="Unique user identifier")
    username: str = Field(description="Username")
    email: Optional[str] = Field(default=None, description="User email address")
    account_status: str = Field(description="Account status (active, locked, etc.)")
    account_ids: List[str] = Field(description="Associated account numbers")
    created_at: str = Field(description="Account creation timestamp")
    last_login: Optional[str] = Field(default=None, description="Last login timestamp")


class LockResult(BaseModel):
    """Account lock operation result."""
    user_id: str = Field(description="User identifier")
    status: str = Field(description="Operation status")
    reason: str = Field(description="Lock reason")
    timestamp: str = Field(description="Lock timestamp")
    message: str = Field(description="Operation result message")


class LoginResult(BaseModel):
    """Authentication result."""
    username: str = Field(description="Authenticated username")
    token: str = Field(description="JWT authentication token")
    expires_at: str = Field(description="Token expiration timestamp")
    user_id: str = Field(description="User identifier")
    permissions: List[str] = Field(description="User permissions")


# MCP Tools
@mcp.tool()
async def get_transactions(account_id: str, ctx: Context[Any, VigilContext]) -> Dict[str, Any]:
    """Retrieve transaction history for a specific account.
    
    Args:
        account_id: The unique identifier for the bank account
        
    Returns:
        Transaction history data
    """
    try:
        await ctx.info(f"Fetching transactions for account: {account_id}")
        bank_client = ctx.request_context.lifespan_context.bank_client
        auth_manager = ctx.request_context.lifespan_context.auth_manager
        
        # Get auth token if we have credentials
        token = None
        if AUTH_USERNAME and AUTH_PASSWORD:
            try:
                token = await auth_manager.get_valid_token(AUTH_USERNAME, AUTH_PASSWORD)
            except Exception as auth_err:
                await ctx.info(f"Login failed for {username}, proceeding without token (will use DB fallback): {auth_err}")
        
        # Always attempt the API call; client will fall back to DB on failure
        result = await bank_client.get_transactions(account_id, token)
        return result
    except Exception as e:
        error_msg = f"Failed to get transactions for account {account_id}: {str(e)}"
        await ctx.error(error_msg)
        return {"error": error_msg}


@mcp.tool()
async def submit_transaction(
    from_account: str,
    to_account: str, 
    amount: int,
    routing_number: str,
    ctx: Context[Any, VigilContext]
) -> Dict[str, Any]:
    """Submit a new transaction to the banking ledger.
    
    Args:
        from_account: Source account number
        to_account: Destination account number
        amount: Transaction amount in cents
        routing_number: Bank routing number
        
    Returns:
        Transaction submission result
    """
    try:
        transaction_data = {
            "fromAccount": from_account,
            "toAccount": to_account,
            "amount": amount,
            "routingNumber": routing_number
        }
        
        await ctx.info(f"Submitting transaction: {transaction_data}")
        bank_client = ctx.request_context.lifespan_context.bank_client
        result = await bank_client.submit_transaction(transaction_data)
        return result
    except Exception as e:
        error_msg = f"Failed to submit transaction: {str(e)}"
        await ctx.error(error_msg)
        return {"error": error_msg}


@mcp.tool()
async def get_user_details(user_id: str, ctx: Context[Any, VigilContext]) -> Dict[str, Any]:
    """Retrieve detailed information about a specific user.
    
    Args:
        user_id: The unique identifier for the user
        
    Returns:
        User details data
    """
    try:
        await ctx.info(f"Fetching user details for: {user_id}")
        bank_client = ctx.request_context.lifespan_context.bank_client
        result = await bank_client.get_user_details(user_id)
        return result
    except Exception as e:
        error_msg = f"Failed to get user details for {user_id}: {str(e)}"
        await ctx.error(error_msg)
        return {"error": error_msg}


@mcp.tool()
async def lock_account(user_id: str, reason: str, ctx: Context[Any, VigilContext]) -> Dict[str, Any]:
    """Lock a user account to prevent further transactions (fraud mitigation).
    
    Args:
        user_id: The unique identifier for the user
        reason: Reason for locking the account (e.g., 'Suspected fraud')
        
    Returns:
        Account lock operation result
    """
    try:
        await ctx.info(f"Locking account for user {user_id}, reason: {reason}")
        bank_client = ctx.request_context.lifespan_context.bank_client
        result = await bank_client.lock_account(user_id, reason)
        return result
    except Exception as e:
        error_msg = f"Failed to lock account for user {user_id}: {str(e)}"
        await ctx.error(error_msg)
        return {"error": error_msg}


@mcp.tool()
async def authenticate_user(username: str, password: str, ctx: Context[Any, VigilContext]) -> Dict[str, Any]:
    """Authenticate a user and retrieve their JWT token.
    
    Args:
        username: User's username
        password: User's password
        
    Returns:
        Authentication result with token
    """
    try:
        await ctx.info(f"Authenticating user: {username}")
        bank_client = ctx.request_context.lifespan_context.bank_client
        result = await bank_client.authenticate(username, password)
        return result
    except Exception as e:
        error_msg = f"Failed to authenticate user {username}: {str(e)}"
        await ctx.error(error_msg)
        return {"error": error_msg}


# MCP Resources
@mcp.resource("vigil://config/bank-connection")
def get_bank_config() -> str:
    """Get Bank of Anthos connection configuration."""
    config = {
        "base_url": BANK_BASE_URL,
        "timeout": REQUEST_TIMEOUT,
        "auth_username": AUTH_USERNAME,
        "status": "configured"
    }
    return json.dumps(config, indent=2)


@mcp.resource("vigil://status/health")
def get_health_status() -> str:
    """Get current health status of Vigil MCP Server."""
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


if __name__ == "__main__":
    import click
    
    @click.command()
    @click.option("--transport", 
                  type=click.Choice(["stdio", "sse", "streamable-http"]), 
                  default="streamable-http",
                  help="Transport type")
    def main(transport: str):
        """Run the Vigil MCP Server."""
        logger.info(f"Starting Vigil MCP Server with {transport} transport")
        logger.info(f"Bank of Anthos base URL: {BANK_BASE_URL}")
        
        mcp.run(transport=transport)
    
    main()
