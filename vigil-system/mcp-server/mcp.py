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
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Sequence

import httpx
import jwt
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

try:
    from mcp.server.fastmcp import FastMCP
    from mcp.types import (
        TextContent,
        Tool,
        CallToolRequest,
        CallToolResult,
    )
except ImportError:
    # Fallback for older mcp library versions
    from mcp.server import Server as FastMCP
    from mcp.types import Tool, TextContent, CallToolRequest, CallToolResult

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
            raise HTTPException(status_code=401, detail="Authentication failed")
    
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
            raise HTTPException(
                status_code=e.response.status_code,
                detail=f"Bank API error: {e.response.text}"
            )
        except Exception as e:
            logger.error(f"Request failed: {e}")
            raise HTTPException(status_code=500, detail=f"Request failed: {str(e)}")
    
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


# Global instances
auth_manager = AuthManager()
bank_client = BankAPIClient(auth_manager)

# Create MCP server
mcp = FastMCP("Vigil MCP Server")


@mcp.tool()
async def get_transactions(account_id: str) -> str:
    """Retrieve transaction history for a specific account.
    
    Args:
        account_id: The unique identifier for the bank account
        
    Returns:
        JSON string containing the transaction history
    """
    try:
        logger.info(f"Fetching transactions for account: {account_id}")
        result = await bank_client.get_transactions(account_id)
        return json.dumps(result, indent=2)
    except Exception as e:
        error_msg = f"Failed to get transactions for account {account_id}: {str(e)}"
        logger.error(error_msg)
        return json.dumps({"error": error_msg})


@mcp.tool()
async def submit_transaction(
    from_account: str,
    to_account: str,
    amount: int,
    routing_number: str
) -> str:
    """Submit a new transaction to the ledger.
    
    Args:
        from_account: Source account number
        to_account: Destination account number  
        amount: Transaction amount in cents
        routing_number: Bank routing number
        
    Returns:
        JSON string containing transaction result
    """
    try:
        transaction_data = {
            "fromAccount": from_account,
            "toAccount": to_account,
            "amount": amount,
            "routingNumber": routing_number
        }
        
        logger.info(f"Submitting transaction: {transaction_data}")
        result = await bank_client.submit_transaction(transaction_data)
        return json.dumps(result, indent=2)
    except Exception as e:
        error_msg = f"Failed to submit transaction: {str(e)}"
        logger.error(error_msg)
        return json.dumps({"error": error_msg})


@mcp.tool()
async def get_user_details(user_id: str) -> str:
    """Retrieve detailed information about a specific user.
    
    Args:
        user_id: The unique identifier for the user
        
    Returns:
        JSON string containing user details
    """
    try:
        logger.info(f"Fetching user details for: {user_id}")
        result = await bank_client.get_user_details(user_id)
        return json.dumps(result, indent=2)
    except Exception as e:
        error_msg = f"Failed to get user details for {user_id}: {str(e)}"
        logger.error(error_msg)
        return json.dumps({"error": error_msg})


@mcp.tool()
async def lock_account(user_id: str, reason: str) -> str:
    """Lock a user account to prevent further transactions.
    
    Args:
        user_id: The unique identifier for the user
        reason: Reason for locking the account (e.g., 'Suspected fraud')
        
    Returns:
        JSON string containing lock operation result
    """
    try:
        logger.info(f"Locking account for user {user_id}, reason: {reason}")
        result = await bank_client.lock_account(user_id, reason)
        return json.dumps(result, indent=2)
    except Exception as e:
        error_msg = f"Failed to lock account for user {user_id}: {str(e)}"
        logger.error(error_msg)
        return json.dumps({"error": error_msg})


@mcp.tool()
async def login(username: str, password: str) -> str:
    """Authenticate a user and retrieve their JWT token.
    
    Args:
        username: User's username
        password: User's password
        
    Returns:
        JSON string containing authentication result
    """
    try:
        logger.info(f"Authenticating user: {username}")
        result = await bank_client.login(username, password)
        return json.dumps(result, indent=2)
    except Exception as e:
        error_msg = f"Failed to authenticate user {username}: {str(e)}"
        logger.error(error_msg)
        return json.dumps({"error": error_msg})


# Health check endpoint
@mcp.get("/health")
async def health_check():
    """Health check endpoint for Kubernetes probes."""
    return {"status": "healthy", "timestamp": datetime.utcnow().isoformat()}


# Cleanup handler
@mcp.on_event("shutdown")
async def shutdown_event():
    """Clean up resources on server shutdown."""
    logger.info("Shutting down MCP server...")
    await auth_manager.close()
    await bank_client.close()


if __name__ == "__main__":
    import uvicorn
    
    # Get configuration from environment
    host = os.getenv('HOST', '0.0.0.0')
    port = int(os.getenv('PORT', '8000'))
    log_level = os.getenv('LOG_LEVEL', 'info')
    
    logger.info(f"Starting Vigil MCP Server on {host}:{port}")
    logger.info(f"Bank of Anthos base URL: {BANK_BASE_URL}")
    
    uvicorn.run(
        "mcp:mcp",
        host=host,
        port=port,
        log_level=log_level,
        reload=False
    )