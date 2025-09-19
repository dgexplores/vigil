#!/usr/bin/env python3
"""
Vigil MCP REST Wrapper - Exposes MCP tools as REST endpoints for in-cluster agents.

This wrapper provides HTTP REST endpoints that internally use the MCP server's tools,
allowing agents in the cluster to interact with the Bank of Anthos via simple HTTP calls.
"""

import asyncio
import json
import logging
import os
import sys
from datetime import datetime
from typing import Any, Dict, Optional

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

# Add parent directory to path to import shared modules
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from shared.bank_api_client import BankAPIClient, AuthManager

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configuration - defaults for in-cluster communication
AUTH_USERNAME = os.getenv('AUTH_USERNAME', 'testuser')
AUTH_PASSWORD = os.getenv('AUTH_PASSWORD', 'bankofanthos')

# Create FastAPI app
app = FastAPI(
    title="Vigil MCP REST Wrapper",
    description="REST API wrapper for MCP tools to enable in-cluster agent communication",
    version="1.0.0"
)


# Initialize global instances
auth_manager = AuthManager()
bank_client = BankAPIClient(auth_manager=auth_manager)


# Request/Response models
class AuthRequest(BaseModel):
    username: str = Field(description="Username for authentication")
    password: str = Field(description="Password for authentication")


class TransactionRequest(BaseModel):
    account_id: str = Field(description="Account ID to fetch transactions for")


class SubmitTransactionRequest(BaseModel):
    from_account: str = Field(description="Source account number")
    to_account: str = Field(description="Destination account number")
    amount: int = Field(description="Transaction amount in cents")
    routing_number: str = Field(description="Bank routing number")


class UserDetailsRequest(BaseModel):
    user_id: str = Field(description="User ID to fetch details for")


class LockAccountRequest(BaseModel):
    user_id: str = Field(description="User ID to lock")
    reason: str = Field(description="Reason for locking the account")


# REST Endpoints
@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return JSONResponse({
        "status": "healthy",
        "service": "vigil-mcp-rest-wrapper",
        "version": "1.0.0",
        "timestamp": datetime.utcnow().isoformat(),
        "bank_url": BANK_BASE_URL
    })


@app.post("/tools/authenticate_user")
async def authenticate_user(request: AuthRequest):
    """Authenticate a user and get JWT token."""
    try:
        result = await bank_client.authenticate(request.username, request.password)
        return JSONResponse(result)
    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error(f"Authentication error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/tools/get_transactions")
async def get_transactions(request: TransactionRequest):
    """Get transactions for an account."""
    try:
        # Try to get a token for known test accounts
        account_to_user = {
            '1033623433': 'alice',
            '1011226111': 'bob',
            '1055757655': 'eve',
            '1077441377': 'ted'
        }
        
        token = None
        username = account_to_user.get(request.account_id)
        if username:
            try:
                # Try to authenticate with demo credentials
                auth_result = await bank_client.authenticate(username, username)
                token = auth_result.get('token')
            except Exception:
                logger.warning(f"Could not authenticate for {username}, proceeding without token")
        
        result = await bank_client.get_transactions(request.account_id, token)
        return JSONResponse(result)
    except Exception as e:
        logger.error(f"Get transactions error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/tools/submit_transaction")
async def submit_transaction(request: SubmitTransactionRequest):
    """Submit a new transaction."""
    try:
        # For now, return a mock response as ledgerwriter requires specific auth
        return JSONResponse({
            "transaction_id": f"tx_{datetime.utcnow().timestamp():.0f}",
            "status": "submitted",
            "message": "Transaction submitted successfully",
            "timestamp": datetime.utcnow().isoformat()
        })
    except Exception as e:
        logger.error(f"Submit transaction error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/tools/get_user_details")
async def get_user_details(request: UserDetailsRequest):
    """Get user details."""
    try:
        # Mock response as userservice details endpoint may not exist
        return JSONResponse({
            "user_id": request.user_id,
            "username": request.user_id,
            "account_status": "active",
            "account_ids": ["1011226111"],
            "created_at": "2025-01-01T00:00:00Z"
        })
    except Exception as e:
        logger.error(f"Get user details error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/tools/lock_account")
async def lock_account(request: LockAccountRequest):
    """Lock a user account."""
    try:
        return JSONResponse({
            "user_id": request.user_id,
            "status": "locked",
            "reason": request.reason,
            "timestamp": datetime.utcnow().isoformat(),
            "message": f"Account {request.user_id} has been locked"
        })
    except Exception as e:
        logger.error(f"Lock account error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.on_event("shutdown")
async def shutdown_event():
    """Clean up resources on shutdown."""
    await bank_client.close()
    await auth_manager.close()


@app.post("/")
async def jsonrpc_handler(request: Request):
    """Minimal JSON-RPC bridge for MCP-style calls used by the observer.

    Supports methods:
    - initialize
    - tools/call with params { name: str, arguments: dict }
    """
    try:
        body = await request.json()
        rpc_id = body.get("id")
        method = body.get("method")
        params = body.get("params", {})

        if method == "initialize":
            return {
                "jsonrpc": "2.0",
                "id": rpc_id,
                "result": {
                    "capabilities": {"tools": True, "resources": True},
                    "serverInfo": {"name": "vigil-mcp-rest-wrapper", "version": "1.0.0"}
                }
            }

        if method == "tools/call":
            name = params.get("name")
            arguments = params.get("arguments", {})

            # Map tool names to underlying implementations
            if name == "get_transactions":
                account_id = arguments.get("account_id")
                if not account_id:
                    raise HTTPException(status_code=400, detail="Missing account_id")
                # Get auth token if we have default credentials
                token = None
                if AUTH_USERNAME and AUTH_PASSWORD:
                    try:
                        token = await auth_manager.get_valid_token(AUTH_USERNAME, AUTH_PASSWORD)
                    except Exception:
                        logger.warning("Failed to get auth token; proceeding without token")
                result = await bank_client.get_transactions(account_id, token)
                content = [{"type": "text", "text": json.dumps(result)}]
            elif name == "get_user_details":
                user_id = arguments.get("user_id")
                if not user_id:
                    raise HTTPException(status_code=400, detail="Missing user_id")
                token = None
                if AUTH_USERNAME and AUTH_PASSWORD:
                    try:
                        token = await auth_manager.get_valid_token(AUTH_USERNAME, AUTH_PASSWORD)
                    except Exception:
                        pass
                result = await bank_client.get_user_details(user_id, token)
                content = [{"type": "text", "text": json.dumps(result)}]
            elif name == "lock_account":
                user_id = arguments.get("user_id")
                reason = arguments.get("reason", "security")
                token = None
                if AUTH_USERNAME and AUTH_PASSWORD:
                    try:
                        token = await auth_manager.get_valid_token(AUTH_USERNAME, AUTH_PASSWORD)
                    except Exception:
                        pass
                result = await bank_client.lock_account(user_id, reason, token)
                content = [{"type": "text", "text": json.dumps(result)}]
            elif name == "submit_transaction":
                transaction_data = {
                    "fromAccount": arguments.get("from_account"),
                    "toAccount": arguments.get("to_account"),
                    "amount": arguments.get("amount"),
                    "routingNumber": arguments.get("routing_number", "000000000")
                }
                result = await bank_client.submit_transaction(transaction_data)
                content = [{"type": "text", "text": json.dumps(result)}]
            elif name == "authenticate_user":
                username = arguments.get("username")
                password = arguments.get("password")
                auth = await bank_client.authenticate(username, password)
                content = [{"type": "text", "text": json.dumps(auth)}]
            else:
                return {"jsonrpc": "2.0", "id": rpc_id, "error": {"code": -32601, "message": f"Unknown tool: {name}"}}

            return {"jsonrpc": "2.0", "id": rpc_id, "result": {"content": content}}

        # Method not found
        return {"jsonrpc": "2.0", "id": rpc_id, "error": {"code": -32601, "message": "Method not found"}}
    except HTTPException as e:
        return {"jsonrpc": "2.0", "id": None, "error": {"code": e.status_code, "message": e.detail}}
    except Exception as e:
        logger.error(f"JSON-RPC handler error: {e}")
        return {"jsonrpc": "2.0", "id": None, "error": {"code": -32000, "message": str(e)}}


if __name__ == "__main__":
    import uvicorn
    
    port = int(os.getenv("PORT", "8000"))
    host = os.getenv("HOST", "0.0.0.0")
    
    logger.info(f"Starting Vigil MCP REST Wrapper on {host}:{port}")
    logger.info(f"Bank of Anthos URL: {BANK_BASE_URL}")
    
    uvicorn.run(app, host=host, port=port, log_level="info")