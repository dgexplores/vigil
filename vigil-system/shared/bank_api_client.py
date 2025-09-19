#!/usr/bin/env python3
"""
Shared Bank API Client for Vigil MCP Services.

This module provides a centralized client for interacting with Bank of Anthos services,
used by MCP servers to expose real banking tools to AI agents.
"""

import asyncio
import logging
import os
import shlex
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

import httpx

logger = logging.getLogger(__name__)

# Configuration with defaults for in-cluster communication
BANK_BASE_URL = os.getenv('BANK_BASE_URL', 'http://userservice:8080')
TRANSACTION_HISTORY_URL = os.getenv('TRANSACTION_HISTORY_URL', 'http://transactionhistory:8080')
LEDGER_WRITER_URL = os.getenv('LEDGER_WRITER_URL', 'http://ledgerwriter:8080')
BALANCES_URL = os.getenv('BALANCES_URL', 'http://balancereader:8080')
CONTACTS_URL = os.getenv('CONTACTS_URL', 'http://contacts:8080')
REQUEST_TIMEOUT = int(os.getenv('REQUEST_TIMEOUT', '30'))


class AuthManager:
    """Manages JWT authentication for Bank of Anthos API calls."""
    
    def __init__(self):
        self.token: Optional[str] = None
        self.token_expiry: Optional[datetime] = None
        self.http_client = httpx.AsyncClient(timeout=REQUEST_TIMEOUT)
    
    async def get_valid_token(self, username: str, password: str) -> str:
        """Returns a valid JWT token, refreshing if necessary."""
        if self.token and self.token_expiry and datetime.utcnow() < self.token_expiry:
            return self.token
        
        await self._refresh_token(username, password)
        return self.token
    
    async def _refresh_token(self, username: str, password: str) -> None:
        """Refreshes the JWT token by authenticating with the user service."""
        try:
            # Bank of Anthos uses form-encoded authentication
            response = await self.http_client.post(
                f"{BANK_BASE_URL}/login",
                data={
                    "username": username,
                    "password": password
                },
                headers={"Content-Type": "application/x-www-form-urlencoded"},
                follow_redirects=False
            )
            
            if response.status_code == 302:  # Successful login redirects
                # Extract token from cookies
                token = None
                for cookie_name in response.cookies:
                    if cookie_name == 'token':
                        token = response.cookies['token']
                        break
                
                if token:
                    self.token = token
                    self.token_expiry = datetime.utcnow() + timedelta(minutes=45)
                    logger.info("JWT token refreshed successfully")
                    return
            
            # If form auth didn't work, try JSON
            response = await self.http_client.post(
                f"{BANK_BASE_URL}/login",
                json={
                    "username": username,
                    "password": password
                }
            )
            
            if response.status_code == 200:
                data = response.json()
                self.token = data.get('token')
                
                if not self.token:
                    raise ValueError("No token received from login response")
                
                self.token_expiry = datetime.utcnow() + timedelta(minutes=45)
                logger.info("JWT token refreshed successfully")
                
        except Exception as e:
            logger.error(f"Failed to refresh JWT token: {e}")
            raise RuntimeError(f"Authentication failed: {e}")
    
    async def close(self):
        """Close the HTTP client."""
        await self.http_client.aclose()


class BankAPIClient:
    """Client for making requests to Bank of Anthos microservices."""
    
    def __init__(self, auth_manager: Optional[AuthManager] = None):
        self.auth_manager = auth_manager or AuthManager()
        self.http_client = httpx.AsyncClient(timeout=REQUEST_TIMEOUT)
    
    async def _make_request(self, method: str, url: str, **kwargs) -> Dict[str, Any]:
        """Makes an HTTP request to a Bank of Anthos service."""
        headers = kwargs.get('headers', {})
        if 'json' in kwargs:
            headers['Content-Type'] = 'application/json'
        kwargs['headers'] = headers
        
        try:
            response = await self.http_client.request(method, url, **kwargs)
            response.raise_for_status()
            
            # Handle different response types
            content_type = response.headers.get('content-type', '')
            if 'application/json' in content_type:
                return response.json()
            else:
                return {'response': response.text}
            
        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error {e.response.status_code}: {e.response.text}")
            raise RuntimeError(f"Bank API error ({e.response.status_code}): {e.response.text}")
        except Exception as e:
            logger.error(f"Request failed: {e}")
            raise RuntimeError(f"Request failed: {str(e)}")
    
    async def authenticate(self, username: str, password: str) -> Dict[str, Any]:
        """Authenticate with the Bank of Anthos."""
        token = await self.auth_manager.get_valid_token(username, password)
        return {
            "token": token,
            "username": username,
            "status": "authenticated"
        }
    
    async def get_transactions(self, account_id: str, token: Optional[str] = None) -> Dict[str, Any]:
        """Retrieves transaction history for a given account.
        
        First tries the transactionhistory service API.
        Falls back to direct database query if API is unavailable.
        """
        # Try the transaction history service
        url = f"{TRANSACTION_HISTORY_URL}/transactions/{account_id}"
        headers = {}
        if token:
            headers['Authorization'] = f'Bearer {token}'
        
        try:
            return await self._make_request('GET', url, headers=headers)
        except Exception as e:
            logger.warning(f"Transaction history API failed, attempting database fallback: {e}")
            # Fallback to direct database access
            return await self._get_transactions_via_db(account_id)
    
    async def _get_transactions_via_db(self, account_id: str) -> Dict[str, Any]:
        """Fallback: query the ledger Postgres DB directly via kubectl.
        
        This requires kubectl access to the cluster and ledger-db-0 pod.
        """
        # Build SQL query
        sql = (
            "SELECT transaction_id, from_acct, to_acct, amount, "
            "to_char(timestamp, 'YYYY-MM-DD\"T\"HH24:MI:SS') AS ts "
            "FROM transactions "
            f"WHERE from_acct='{account_id}' OR to_acct='{account_id}' "
            "ORDER BY timestamp DESC LIMIT 50;"
        )
        
        cmd = (
            f"kubectl exec ledger-db-0 -- psql -U admin -d postgresdb -t -A -F , -c {shlex.quote(sql)}"
        )
        
        # Set environment for GKE auth
        env = os.environ.copy()
        env['USE_GKE_GCLOUD_AUTH_PLUGIN'] = 'True'
        
        proc = await asyncio.create_subprocess_shell(
            cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=env
        )
        
        stdout, stderr = await proc.communicate()
        
        if proc.returncode != 0:
            error_msg = stderr.decode('utf-8', errors='ignore')
            logger.error(f"Database query failed: {error_msg}")
            raise RuntimeError(f"Database query failed: {error_msg}")
        
        # Parse the CSV output
        lines = [l.strip() for l in stdout.decode('utf-8', errors='ignore').splitlines() if l.strip()]
        transactions: List[Dict[str, Any]] = []
        
        for line in lines:
            parts = line.split(',')
            if len(parts) >= 5:
                try:
                    transactions.append({
                        "transaction_id": parts[0],
                        "fromAccountNum": parts[1],
                        "toAccountNum": parts[2],
                        "amount": int(parts[3]),
                        "timestamp": parts[4],
                        "status": "COMPLETED"
                    })
                except (ValueError, IndexError) as e:
                    logger.warning(f"Failed to parse transaction line: {line}, error: {e}")
                    continue
        
        return {
            "account_id": account_id,
            "transactions": transactions,
            "total_count": len(transactions)
        }
    
    async def submit_transaction(self, transaction_data: Dict[str, Any]) -> Dict[str, Any]:
        """Submits a new transaction to the ledger writer service."""
        url = f"{LEDGER_WRITER_URL}/transactions"
        return await self._make_request('POST', url, json=transaction_data)
    
    async def get_account_balance(self, account_id: str, token: Optional[str] = None) -> Dict[str, Any]:
        """Retrieves the current balance for an account from the balance reader service."""
        url = f"{BALANCES_URL}/balances/{account_id}"
        headers = {}
        if token:
            headers['Authorization'] = f'Bearer {token}'
        return await self._make_request('GET', url, headers=headers)
    
    async def get_contacts(self, user_id: str, token: Optional[str] = None) -> Dict[str, Any]:
        """Retrieves contacts for a user from the contacts service."""
        url = f"{CONTACTS_URL}/contacts/{user_id}"
        headers = {}
        if token:
            headers['Authorization'] = f'Bearer {token}'
        return await self._make_request('GET', url, headers=headers)
    
    async def add_contact(self, user_id: str, contact_data: Dict[str, Any], token: Optional[str] = None) -> Dict[str, Any]:
        """Adds a new contact for a user."""
        url = f"{CONTACTS_URL}/contacts/{user_id}"
        headers = {}
        if token:
            headers['Authorization'] = f'Bearer {token}'
        return await self._make_request('POST', url, json=contact_data, headers=headers)
    
    async def get_user_details(self, user_id: str, token: Optional[str] = None) -> Dict[str, Any]:
        """Retrieves user details from the user service."""
        url = f"{BANK_BASE_URL}/users/{user_id}"
        headers = {}
        if token:
            headers['Authorization'] = f'Bearer {token}'
        return await self._make_request('GET', url, headers=headers)
    
    async def lock_account(self, user_id: str, reason: str, token: Optional[str] = None) -> Dict[str, Any]:
        """Locks a user account for security reasons."""
        url = f"{BANK_BASE_URL}/users/{user_id}/lock"
        headers = {}
        if token:
            headers['Authorization'] = f'Bearer {token}'
        return await self._make_request('POST', url, json={"reason": reason}, headers=headers)
    
    async def close(self):
        """Close HTTP clients."""
        await self.http_client.aclose()
        if self.auth_manager:
            await self.auth_manager.close()