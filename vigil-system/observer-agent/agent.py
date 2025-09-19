#!/usr/bin/env python3
"""
Vigil Observer Agent - Continuous Transaction Monitoring (Refactored)

This agent continuously monitors bank transactions from Bank of Anthos microservices
through the MCP server, normalizes the data, and sends structured transaction data 
to the Analyst agent for fraud detection via A2A communication.

Uses direct HTTP calls to the MCP server to avoid ADK import issues.
"""

import asyncio
import json
import logging
import os
from typing import Any, Dict, List, Set, Optional
from datetime import datetime, timedelta
import random
from aiohttp import web
from dataclasses import dataclass
from dateutil import parser
import traceback
import subprocess
import httpx
from mcp_stdio_client import MCPStdioClient

# Configure structured logging for better observability
logging.basicConfig(
    level=logging.INFO, 
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('/app/logs/observer.log', mode='a') if os.path.exists('/app/logs') else logging.NullHandler()
    ]
)
logger = logging.getLogger(__name__)

# Configuration from environment with validation
MCP_SERVER_PATH = os.getenv('MCP_SERVER_PATH', '/app/vigil_mcp_server.py')
OBSERVER_PORT = int(os.getenv('OBSERVER_PORT', '8000'))
ANALYST_AGENT_URL = os.getenv('ANALYST_AGENT_URL', 'http://vigil-analyst:8001')
POLLING_INTERVAL = int(os.getenv('POLLING_INTERVAL', '5'))
BATCH_SIZE = int(os.getenv('BATCH_SIZE', '100'))
ENABLE_METRICS = os.getenv('ENABLE_METRICS', 'true').lower() == 'true'
ENABLE_TRACING = os.getenv('ENABLE_TRACING', 'true').lower() == 'true'

# Global health status with proper state management
@dataclass
class HealthStatus:
    ready: bool = False
    healthy: bool = False
    last_transaction_time: Optional[datetime] = None
    transactions_processed: int = 0
    errors_count: int = 0
    mcp_connected: bool = False
    
health_status = HealthStatus()


# --- HEALTH CHECK ENDPOINTS WITH DETAILED STATUS ---
async def health_handler(request):
    """Enhanced health check endpoint with detailed status."""
    status = {
        "status": "healthy" if health_status.healthy else "unhealthy",
        "timestamp": datetime.utcnow().isoformat(),
        "transactions_processed": health_status.transactions_processed,
        "errors_count": health_status.errors_count,
        "last_transaction_time": health_status.last_transaction_time.isoformat() if health_status.last_transaction_time else None,
        "mcp_connected": health_status.mcp_connected
    }
    
    if health_status.healthy:
        return web.json_response(status)
    else:
        return web.json_response(status, status=503)


async def ready_handler(request):
    """Enhanced readiness check endpoint."""
    status = {
        "status": "ready" if health_status.ready else "not ready",
        "timestamp": datetime.utcnow().isoformat(),
        "agent_initialized": health_status.ready,
        "mcp_connected": health_status.mcp_connected
    }
    
    if health_status.ready:
        return web.json_response(status)
    else:
        return web.json_response(status, status=503)


async def metrics_handler(request):
    """Prometheus-compatible metrics endpoint for monitoring."""
    metrics = [
        f"# HELP vigil_observer_transactions_total Total number of transactions processed",
        f"# TYPE vigil_observer_transactions_total counter",
        f"vigil_observer_transactions_total {health_status.transactions_processed}",
        f"# HELP vigil_observer_errors_total Total number of errors",
        f"# TYPE vigil_observer_errors_total counter",
        f"vigil_observer_errors_total {health_status.errors_count}",
        f"# HELP vigil_observer_up Observer agent up status",
        f"# TYPE vigil_observer_up gauge",
        f"vigil_observer_up {1 if health_status.healthy else 0}",
        f"# HELP vigil_observer_mcp_connected MCP server connection status",
        f"# TYPE vigil_observer_mcp_connected gauge",
        f"vigil_observer_mcp_connected {1 if health_status.mcp_connected else 0}"
    ]
    return web.Response(text="\n".join(metrics), content_type="text/plain")


async def start_health_server():
    """Start the enhanced health check HTTP server with metrics."""
    app = web.Application()
    app.router.add_get('/health', health_handler)
    app.router.add_get('/ready', ready_handler)
    app.router.add_get('/metrics', metrics_handler)
    
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', OBSERVER_PORT)
    await site.start()
    
    health_status.healthy = True
    logger.info(f"Health server started on port {OBSERVER_PORT} with /health, /ready, and /metrics endpoints")
    return runner


# MCPClient is now imported from mcp_stdio_client module
# The old implementation is replaced with MCPStdioClient


class TransactionProcessor:
    """Enhanced transaction processor with MCP integration."""
    
    def __init__(self, mcp_client: MCPStdioClient):
        self.mcp_client = mcp_client
        self.processed_transactions: Set[str] = set()
        self.last_check_time = datetime.utcnow() - timedelta(minutes=5)
        
    async def get_new_transactions(self) -> List[Dict[str, Any]]:
        """Fetch new transactions using MCP tools."""
        try:
            logger.info("Fetching new transactions via MCP server...")
            
            transactions = []
            
            # Test accounts from Bank of Anthos
            test_accounts = ['1011226111', '1033623433', '1055757655']
            
            for account_id in test_accounts:
                try:
                    logger.debug(f"Fetching transactions for account {account_id}")
                    
                    # Call the MCP tool
                    result = await self.mcp_client.call_tool(
                        'get_transactions',
                        {'account_id': account_id}
                    )
                    
                    if result and isinstance(result, dict):
                        if 'transactions' in result:
                            account_transactions = result['transactions']
                            if isinstance(account_transactions, list):
                                transactions.extend(account_transactions)
                                logger.info(f"Found {len(account_transactions)} transactions for account {account_id}")
                        elif 'result' in result and isinstance(result['result'], dict):
                            # Handle nested result structure
                            if 'transactions' in result['result']:
                                account_transactions = result['result']['transactions']
                                if isinstance(account_transactions, list):
                                    transactions.extend(account_transactions)
                    
                except Exception as e:
                    logger.debug(f"Could not fetch transactions for account {account_id}: {e}")
            
            # If no real transactions, continue monitoring
            if not transactions:
                logger.debug("No new transactions found in this polling cycle.")
            
            # Filter out already processed transactions
            new_transactions = []
            for tx in transactions:
                tx_id = tx.get('transaction_id', tx.get('id', ''))
                if tx_id and tx_id not in self.processed_transactions:
                    new_transactions.append(tx)
                    self.processed_transactions.add(tx_id)
                    health_status.transactions_processed += 1
            
            # Update monitoring data
            self.last_check_time = datetime.utcnow()
            health_status.last_transaction_time = self.last_check_time
            
            # Prevent memory leak with circular buffer pattern
            if len(self.processed_transactions) > 10000:
                recent_ids = list(self.processed_transactions)[-5000:]
                self.processed_transactions = set(recent_ids)
                logger.info("Cleaned up transaction cache to prevent memory leak")
            
            logger.info(f"Found {len(new_transactions)} new transactions to process")
            return new_transactions
            
        except Exception as e:
            logger.error(f"Critical error in get_new_transactions: {e}\n{traceback.format_exc()}")
            health_status.errors_count += 1
            return []
    
    async def normalize_transaction(self, tx_data: Dict[str, Any]) -> Dict[str, Any]:
        """Normalize transaction data to standard format for fraud analysis."""
        try:
            # Handle both fromAccountNum and from_account field names
            from_account = tx_data.get('from_account', tx_data.get('fromAccountNum', ''))
            to_account = tx_data.get('to_account', tx_data.get('toAccountNum', ''))
            
            # Handle amount and description variations
            amount = tx_data.get('amount', 0.0)
            description = tx_data.get('description', tx_data.get('memo', ''))
            
            # Generate a unique ID if not present
            tx_id = tx_data.get('transaction_id', tx_data.get('id'))
            if not tx_id:
                tx_id = f"gen_{from_account}_{to_account}_{int(datetime.utcnow().timestamp())}"

            # Standardize timestamp
            timestamp_str = tx_data.get('timestamp', datetime.utcnow().isoformat())
            try:
                timestamp = parser.parse(timestamp_str).isoformat()
            except (parser.ParserError, TypeError):
                timestamp = datetime.utcnow().isoformat()

            normalized_tx = {
                'transaction_id': tx_id,
                'from_account': from_account,
                'to_account': to_account,
                'amount': float(amount),
                'currency': tx_data.get('currency', 'USD'),
                'timestamp': timestamp,
                'type': tx_data.get('type', 'unknown'),
                'status': tx_data.get('status', 'completed'),
                'description': description,
                'source': tx_data.get('source', 'bank_of_anthos'),
                'ip_address': tx_data.get('ip_address', 'N/A'),
                'location': tx_data.get('location', 'N/A')
            }
            return normalized_tx
            
        except Exception as e:
            logger.error(f"Error normalizing transaction: {e} - Data: {tx_data}")
            return {}
    
    async def _enrich_transaction_context(self, tx_data: Dict[str, Any]):
        """Enrich transaction with additional context data."""
        try:
            # Extract user ID from account (simplified logic)
            from_account = tx_data.get('from_account', '')
            if from_account and len(from_account) >= 4:
                user_id = from_account[:4]  # Mock user ID from account
                
                # Try to get user details via MCP
                try:
                    result = await self.mcp_client.call_tool(
                        'get_user_details',
                        {'user_id': user_id}
                    )
                    if result:
                        tx_data['user_context'] = result
                    else:
                        tx_data['user_context'] = {"mock_user": user_id}
                except Exception as e:
                    logger.debug(f"Could not enrich user context: {e}")
                    tx_data['user_context'] = {"mock_user": user_id}
        except Exception as e:
            logger.debug(f"Error enriching context: {e}")


async def send_transactions_to_analyst(transactions: List[Dict[str, Any]]) -> None:
    """Send normalized transactions to the Analyst agent for fraud analysis."""
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            for tx in transactions:
                analysis_request = {
                    'request_type': 'transaction_analysis',
                    'transaction_data': tx,
                    'source': 'vigil_observer',
                    'timestamp': datetime.utcnow().isoformat()
                }
                
                logger.info(f"Sending transaction {tx['transaction_id']} to Analyst for analysis")
                
                try:
                    # Send to analyst agent
                    response = await client.post(
                        f"{ANALYST_AGENT_URL}/analyze",
                        json=analysis_request,
                        headers={"Content-Type": "application/json"}
                    )
                    
                    if response.status_code == 200:
                        logger.debug(f"Successfully sent transaction to Analyst")
                    else:
                        logger.warning(f"Analyst returned status {response.status_code}")
                        
                except Exception as e:
                    # Log but don't fail if analyst is not available
                    logger.debug(f"Could not send to Analyst (may not be deployed): {e}")
                    # Log what would be sent for debugging
                    logger.debug(f"A2A Request to Analyst: {json.dumps(analysis_request, indent=2)}")
            
    except Exception as e:
        logger.error(f"Error sending transactions to Analyst: {e}")


# --- MAIN EXECUTION LOOP ---
async def run_monitoring_loop(mcp_client: MCPStdioClient):
    """Continuously run the monitoring loop with intervals."""
    processor = TransactionProcessor(mcp_client)
    
    logger.info(f"Starting continuous monitoring with {POLLING_INTERVAL}s intervals")
    
    while True:
        try:
            # Fetch new transactions
            new_transactions = await processor.get_new_transactions()
            
            if new_transactions:
                logger.info(f"Processing {len(new_transactions)} new transactions")
                
                # Normalize each transaction
                normalized_transactions = []
                for tx in new_transactions:
                    normalized_tx = await processor.normalize_transaction(tx)
                    normalized_transactions.append(normalized_tx)
                
                # Send to Analyst agent
                await send_transactions_to_analyst(normalized_transactions)
            
        except Exception as e:
            logger.error(f"Error in monitoring iteration: {e}")
            health_status.errors_count += 1
        
        # Wait for next polling interval
        await asyncio.sleep(POLLING_INTERVAL)


async def main():
    """Enhanced main entry point with proper lifecycle management."""
    logger.info("="*60)
    logger.info("Starting Vigil Observer Agent (Refactored Version)")
    logger.info(f"Environment: POLLING_INTERVAL={POLLING_INTERVAL}s, BATCH_SIZE={BATCH_SIZE}")
    logger.info(f"MCP Server: {MCP_SERVER_PATH} (stdio)")
    logger.info(f"Monitoring: METRICS={ENABLE_METRICS}, TRACING={ENABLE_TRACING}")
    logger.info("="*60)
    
    health_runner = None
    mcp_client = None
    
    try:
        # Start health server first for Kubernetes probes
        health_runner = await start_health_server()
        logger.info("✓ Health server started successfully")
        
        # Create and connect MCP client
        mcp_client = MCPStdioClient("/app/vigil_mcp_stdio_server.py")
        logger.info("✓ MCP client created for stdio communication")
        
        # Connect to MCP server
        health_status.mcp_connected = await mcp_client.connect()
        if health_status.mcp_connected:
            logger.info("✓ Successfully connected to MCP server")
        else:
            logger.warning("⚠ Could not connect to MCP server via stdio")
        
        # Mark as ready for Kubernetes
        health_status.ready = True
        logger.info("✓ Observer agent marked as ready")
        
        # Start the continuous monitoring loop
        logger.info("Starting transaction monitoring loop...")
        await run_monitoring_loop(mcp_client)
        
    except KeyboardInterrupt:
        logger.info("Received shutdown signal, cleaning up...")
    except Exception as e:
        logger.error(f"Failed to start observer agent: {e}\n{traceback.format_exc()}")
        health_status.healthy = False
        health_status.ready = False
        raise
    finally:
        # Cleanup resources
        if mcp_client:
            await mcp_client.close()
        if health_runner:
            await health_runner.cleanup()
        logger.info("Observer agent shutdown complete")


if __name__ == "__main__":
    asyncio.run(main())