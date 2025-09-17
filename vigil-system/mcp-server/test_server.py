#!/usr/bin/env python3
"""
Test version of Vigil MCP Server - for local testing without MCP library dependency.
"""

import asyncio
import json
import logging
import os
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

import httpx
import jwt
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configuration
BANK_BASE_URL = os.getenv('BANK_BASE_URL', 'http://localhost:8080')
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
            # For testing, create a mock token
            logger.warning("Creating mock token for testing purposes")
            self.token = "mock-jwt-token-for-testing"
            self.token_expiry = datetime.utcnow() + timedelta(minutes=45)
    
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
            # For testing, return mock data
            return self._get_mock_response(method, url)
        except Exception as e:
            logger.error(f"Request failed: {e}")
            # For testing, return mock data
            return self._get_mock_response(method, url)
    
    def _get_mock_response(self, method: str, url: str) -> Dict[str, Any]:
        """Generate mock responses for testing."""
        if "transactions" in url and method == "GET":
            return {
                "transactions": [
                    {
                        "transaction_id": "tx-001",
                        "amount": 250.0,
                        "timestamp": "2025-01-17T03:00:00Z",
                        "from_account": "acc-001",
                        "to_account": "acc-002",
                        "description": "Regular transfer"
                    },
                    {
                        "transaction_id": "tx-002",
                        "amount": 1500.0,
                        "timestamp": "2025-01-17T03:15:00Z",
                        "from_account": "acc-001",
                        "to_account": "acc-003",
                        "description": "High-value PIX transfer"
                    }
                ]
            }
        elif "users" in url and method == "GET":
            return {
                "user_id": "user-001",
                "username": "test_user",
                "account_num": "acc-001",
                "email": "user@example.com",
                "last_login": "2025-01-17T02:30:00Z",
                "location": "São Paulo, Brazil"
            }
        elif "lock" in url and method == "POST":
            return {
                "status": "locked",
                "user_id": "user-001",
                "timestamp": datetime.utcnow().isoformat()
            }
        elif method == "POST" and "transactions" in url:
            return {
                "transaction_id": "tx-new-001",
                "status": "ok",
                "timestamp": datetime.utcnow().isoformat()
            }
        elif "login" in url:
            return {
                "token": "mock-jwt-token",
                "expires_in": 3600
            }
        else:
            return {"error": f"Mock response for {method} {url}", "status": "testing"}
    
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

# Create FastAPI app
app = FastAPI(title="Vigil MCP Server (Test Mode)", version="1.0.0")


# Tool endpoints for testing
class ToolRequest(BaseModel):
    account_id: Optional[str] = None
    user_id: Optional[str] = None
    from_account: Optional[str] = None
    to_account: Optional[str] = None
    amount: Optional[int] = None
    routing_number: Optional[str] = None
    reason: Optional[str] = None
    username: Optional[str] = None
    password: Optional[str] = None


@app.post("/tools/get_transactions")
async def get_transactions_endpoint(request: ToolRequest):
    """Test endpoint for get_transactions tool."""
    if not request.account_id:
        raise HTTPException(status_code=400, detail="account_id is required")
    
    try:
        logger.info(f"Fetching transactions for account: {request.account_id}")
        result = await bank_client.get_transactions(request.account_id)
        return {"result": result, "status": "success"}
    except Exception as e:
        error_msg = f"Failed to get transactions for account {request.account_id}: {str(e)}"
        logger.error(error_msg)
        return {"error": error_msg, "status": "error"}


@app.post("/tools/submit_transaction")
async def submit_transaction_endpoint(request: ToolRequest):
    """Test endpoint for submit_transaction tool."""
    required_fields = ['from_account', 'to_account', 'amount', 'routing_number']
    for field in required_fields:
        if not getattr(request, field):
            raise HTTPException(status_code=400, detail=f"{field} is required")
    
    try:
        transaction_data = {
            "fromAccount": request.from_account,
            "toAccount": request.to_account,
            "amount": request.amount,
            "routingNumber": request.routing_number
        }
        
        logger.info(f"Submitting transaction: {transaction_data}")
        result = await bank_client.submit_transaction(transaction_data)
        return {"result": result, "status": "success"}
    except Exception as e:
        error_msg = f"Failed to submit transaction: {str(e)}"
        logger.error(error_msg)
        return {"error": error_msg, "status": "error"}


@app.post("/tools/get_user_details")
async def get_user_details_endpoint(request: ToolRequest):
    """Test endpoint for get_user_details tool."""
    if not request.user_id:
        raise HTTPException(status_code=400, detail="user_id is required")
    
    try:
        logger.info(f"Fetching user details for: {request.user_id}")
        result = await bank_client.get_user_details(request.user_id)
        return {"result": result, "status": "success"}
    except Exception as e:
        error_msg = f"Failed to get user details for {request.user_id}: {str(e)}"
        logger.error(error_msg)
        return {"error": error_msg, "status": "error"}


@app.post("/tools/lock_account")
async def lock_account_endpoint(request: ToolRequest):
    """Test endpoint for lock_account tool."""
    if not request.user_id or not request.reason:
        raise HTTPException(status_code=400, detail="user_id and reason are required")
    
    try:
        logger.info(f"Locking account for user {request.user_id}, reason: {request.reason}")
        result = await bank_client.lock_account(request.user_id, request.reason)
        return {"result": result, "status": "success"}
    except Exception as e:
        error_msg = f"Failed to lock account for user {request.user_id}: {str(e)}"
        logger.error(error_msg)
        return {"error": error_msg, "status": "error"}


@app.post("/tools/login")
async def login_endpoint(request: ToolRequest):
    """Test endpoint for login tool."""
    if not request.username or not request.password:
        raise HTTPException(status_code=400, detail="username and password are required")
    
    try:
        logger.info(f"Authenticating user: {request.username}")
        result = await bank_client.login(request.username, request.password)
        return {"result": result, "status": "success"}
    except Exception as e:
        error_msg = f"Failed to authenticate user {request.username}: {str(e)}"
        logger.error(error_msg)
        return {"error": error_msg, "status": "error"}


# Health check endpoint
@app.get("/health")
async def health_check():
    """Health check endpoint for Kubernetes probes."""
    return {"status": "healthy", "timestamp": datetime.utcnow().isoformat(), "mode": "testing"}


# API info endpoint
@app.get("/")
async def root():
    """Root endpoint with API information."""
    return {
        "service": "Vigil MCP Server",
        "version": "1.0.0",
        "mode": "testing",
        "available_tools": [
            "/tools/get_transactions",
            "/tools/submit_transaction", 
            "/tools/get_user_details",
            "/tools/lock_account",
            "/tools/login"
        ],
        "config": {
            "bank_base_url": BANK_BASE_URL,
            "request_timeout": REQUEST_TIMEOUT,
            "auth_username": AUTH_USERNAME
        }
    }


# Cleanup handler
@app.on_event("shutdown")
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
    
    logger.info(f"Starting Vigil MCP Server (Test Mode) on {host}:{port}")
    logger.info(f"Bank of Anthos base URL: {BANK_BASE_URL}")
    
    uvicorn.run(
        "test_server:app",
        host=host,
        port=port,
        log_level=log_level,
        reload=False
    )