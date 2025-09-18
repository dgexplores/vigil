#!/usr/bin/env python3
"""
Vigil Observer Agent - Continuous Transaction Monitoring

This agent continuously monitors bank transactions from Bank of Anthos microservices,
normalizes the data, and sends structured transaction data to the Analyst agent
for fraud detection via A2A communication.
"""

import asyncio
import json
import logging
import os
from typing import Any, Dict, List, Optional, Set
from datetime import datetime, timedelta
import hashlib
from aiohttp import web

# Correctly import the standard Agent class
from google.adk.agents import Agent
from google.adk.tools.mcp_tool.mcp_toolset import McpToolset
from google.adk.tools.mcp_tool.mcp_session_manager import StdioConnectionParams
from mcp import StdioServerParameters

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Configuration from environment
MCP_SERVER_PATH = os.getenv('MCP_SERVER_PATH', '/app/vigil_mcp_lowlevel.py')
OBSERVER_PORT = int(os.getenv('OBSERVER_PORT', '8000'))
ANALYST_AGENT_URL = os.getenv('ANALYST_AGENT_URL', 'http://vigil-analyst:8001')
POLLING_INTERVAL = int(os.getenv('POLLING_INTERVAL', '5'))  # seconds between checks
BATCH_SIZE = int(os.getenv('BATCH_SIZE', '100'))  # transactions to process per batch

# Bank of Anthos microservice endpoints (configurable for demo/production)
BANK_SERVICES = {
    'ledger_writer': os.getenv('LEDGER_WRITER_URL', 'http://ledgerwriter:8080'),
    'transaction_history': os.getenv('TRANSACTION_HISTORY_URL', 'http://transactionhistory:8080'),
    'balance_reader': os.getenv('BALANCE_READER_URL', 'http://balancereader:8080'),
    'contacts': os.getenv('CONTACTS_URL', 'http://contacts:8080'),
    'user_service': os.getenv('USER_SERVICE_URL', 'http://userservice:8080')
}

# Global variables for health status
app_ready = False
app_healthy = False


async def health_handler(request):
    """Health check endpoint."""
    if app_healthy:
        return web.json_response({"status": "healthy", "timestamp": datetime.utcnow().isoformat()})
    else:
        return web.json_response({"status": "unhealthy", "timestamp": datetime.utcnow().isoformat()}, status=503)


async def ready_handler(request):
    """Readiness check endpoint."""
    if app_ready:
        return web.json_response({"status": "ready", "timestamp": datetime.utcnow().isoformat()})
    else:
        return web.json_response({"status": "not ready", "timestamp": datetime.utcnow().isoformat()}, status=503)


async def start_health_server():
    """Start the health check HTTP server."""
    global app_healthy
    app = web.Application()
    app.router.add_get('/health', health_handler)
    app.router.add_get('/ready', ready_handler)
    
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', OBSERVER_PORT)
    await site.start()
    
    app_healthy = True
    logger.info(f"Health server started on port {OBSERVER_PORT}")
    return runner


def create_observer_agent() -> Agent:
    """Create the Vigil Observer Agent as a standard tool-providing agent."""
    
    # Ensure MCP server path exists
    if not os.path.exists(MCP_SERVER_PATH):
        logger.warning(f"MCP server not found at {MCP_SERVER_PATH}, using relative path")
        mcp_server_path = "./vigil_mcp_lowlevel.py"
    else:
        mcp_server_path = MCP_SERVER_PATH
    
    # This agent is a "doer" - it doesn't need a model or instructions
    agent = Agent(
        name='vigil_observer_agent',
        tools=[
            McpToolset(
                connection_params=StdioConnectionParams(
                    server_params=StdioServerParameters(
                        command='python3',
                        args=[mcp_server_path, '--transport', 'stdio']
                    )
                ),
                # Observer only needs read-access tools
                tool_filter=['get_transactions', 'get_user_details']
            )
        ]
    )
    
    return agent


class TransactionProcessor:
    """Processes and normalizes transaction data from Bank of Anthos."""
    
    def __init__(self, agent: Agent):
        self.agent = agent
        self.processed_transactions: Set[str] = set()  # Track processed transactions
        self.last_check_time = datetime.utcnow() - timedelta(minutes=5)  # Start 5 minutes back
        
    async def get_new_transactions(self) -> List[Dict[str, Any]]:
        """
        Fetch new transactions from Bank of Anthos microservices.
        
        Returns:
            List of new transaction dictionaries
        """
        try:
            current_time = datetime.utcnow()
            
            # Query for transactions since last check
            query_prompt = f"""
            Get all transactions from the last {POLLING_INTERVAL + 1} seconds.
            Include transaction details: ID, amount, from_account, to_account, timestamp, type.
            Focus on transactions after {self.last_check_time.isoformat()}.
            """
            
            logger.info(f"Querying transactions since {self.last_check_time.isoformat()}")
            
            # Use MCP tools to get transaction data directly
            try:
                # Get all available account IDs first (simulated for demo)
                account_ids = ["1234567890", "0987654321", "1111222233"]  # Demo account IDs
                
                all_transactions = []
                for account_id in account_ids:
                    try:
                        # Use agent to call MCP tool
                        prompt = f"Use the get_transactions tool to get transactions for account_id: {account_id}"
                        result = await self.agent.run(prompt)
                        
                        # Since we're getting text response, we'll create mock transaction data
                        # In a real system, this would parse the actual response
                        if "error" not in str(result).lower():
                            # Create a mock transaction for demo purposes
                            mock_transaction = {
                                'transaction_id': f'tx_{account_id}_{datetime.utcnow().timestamp()}',
                                'from_account': account_id,
                                'to_account': 'unknown',
                                'amount': 100.0,  # Mock amount
                                'timestamp': datetime.utcnow().isoformat(),
                                'type': 'transfer',
                                'status': 'completed',
                                'source': 'bank_of_anthos'
                            }
                            all_transactions.append(mock_transaction)
                                
                    except Exception as e:
                        logger.warning(f"Could not fetch transactions for account {account_id}: {e}")
                        continue
                
                transactions = all_transactions
                
            except Exception as e:
                logger.error(f"Error calling MCP tools: {e}")
                transactions = []
            
            # Filter out already processed transactions
            new_transactions = []
            for tx in transactions:
                tx_id = tx.get('transaction_id', tx.get('id', ''))
                if tx_id and tx_id not in self.processed_transactions:
                    new_transactions.append(tx)
                    self.processed_transactions.add(tx_id)
            
            # Update last check time
            self.last_check_time = current_time
            
            # Prevent memory leak - keep only recent transaction IDs
            if len(self.processed_transactions) > 10000:
                # Keep only the most recent 5000
                recent_ids = list(self.processed_transactions)[-5000:]
                self.processed_transactions = set(recent_ids)
            
            logger.info(f"Found {len(transactions)} new transactions to process")
            return transactions
            
        except Exception as e:
            logger.error(f"Error fetching transactions: {e}")
            return []
    
    async def normalize_transaction(self, tx_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Normalize transaction data to standard format for fraud analysis.
        
        Args:
            tx_data: Raw transaction data from Bank of Anthos
            
        Returns:
            Normalized transaction data ready for Analyst agent
        """
        try:
            # Ensure required fields with defaults
            normalized = {
                'transaction_id': tx_data.get('transaction_id', tx_data.get('id', f'tx_{hash(str(tx_data)) % 100000}')),
                'timestamp': tx_data.get('timestamp', datetime.utcnow().isoformat()),
                'amount': float(tx_data.get('amount', 0.0)),
                'currency': tx_data.get('currency', 'USD'),
                'from_account': tx_data.get('from_account', tx_data.get('fromAccountNum', '')),
                'to_account': tx_data.get('to_account', tx_data.get('toAccountNum', '')),
                'type': tx_data.get('type', tx_data.get('transactionType', 'transfer')),
                'description': tx_data.get('description', ''),
                'user_id': tx_data.get('user_id', tx_data.get('userId', '')),
                'location': tx_data.get('location', ''),
                'ip_address': tx_data.get('ip_address', ''),
                'device_info': tx_data.get('device_info', {}),
                'raw_data': tx_data,
                'processed_timestamp': datetime.utcnow().isoformat(),
                'observer_version': 'vigil-1.0'
            }
            
            # Enrich with additional context if available
            await self._enrich_transaction_context(normalized)
            
            return normalized
            
        except Exception as e:
            logger.error(f"Error normalizing transaction {tx_data.get('id', 'unknown')}: {e}")
            # Return minimal valid structure
            return {
                'transaction_id': f'tx_error_{datetime.utcnow().timestamp()}',
                'timestamp': datetime.utcnow().isoformat(),
                'amount': 0.0,
                'currency': 'USD',
                'from_account': '',
                'to_account': '',
                'type': 'error',
                'error': str(e),
                'raw_data': tx_data
            }
    
    async def _enrich_transaction_context(self, tx_data: Dict[str, Any]):
        """Enrich transaction with additional context data."""
        try:
            user_id = tx_data.get('user_id')
            from_account = tx_data.get('from_account')
            
            # Get user details if available
            if user_id:
                try:
                    prompt = f"Use the get_user_details tool to get user details for user_id: {user_id}"
                    user_response = await self.agent.run(prompt)
                    tx_data['user_context'] = {"response": str(user_response)}
                except Exception as e:
                    logger.warning(f"Could not get user details for {user_id}: {e}")
                    tx_data['user_context'] = {"error": str(e)}
            
            # Get account balance if available (using transaction history as proxy)
            if from_account:
                try:
                    prompt = f"Use the get_transactions tool to get transactions for account_id: {from_account}"
                    balance_response = await self.agent.run(prompt)
                    tx_data['account_balance'] = {"account_id": from_account, "response": str(balance_response)}
                except Exception as e:
                    logger.warning(f"Could not get account balance for {from_account}: {e}")
                    tx_data['account_balance'] = {"error": str(e)}
                
        except Exception as e:
            logger.warning(f"Could not enrich transaction context: {e}")
            tx_data['enrichment_error'] = str(e)


async def transaction_monitoring_loop(agent: Agent) -> None:
    """
    Main monitoring loop function for the Observer agent.
    
    This function runs continuously, fetching new transactions and sending them
    to the Analyst agent for fraud detection.
    """
    logger.info("Starting transaction monitoring loop...")
    
    processor = TransactionProcessor(agent)
    
    try:
        # Fetch new transactions
        new_transactions = await processor.get_new_transactions()
        
        if not new_transactions:
            logger.debug("No new transactions found")
            return
        
        logger.info(f"Processing {len(new_transactions)} new transactions")
        
        # Process transactions in batches
        batch_count = 0
        for i in range(0, len(new_transactions), BATCH_SIZE):
            batch = new_transactions[i:i + BATCH_SIZE]
            batch_count += 1
            
            logger.info(f"Processing batch {batch_count} ({len(batch)} transactions)")
            
            # Normalize each transaction
            normalized_transactions = []
            for tx in batch:
                normalized_tx = await processor.normalize_transaction(tx)
                normalized_transactions.append(normalized_tx)
            
            # Send batch to Analyst agent via A2A
            await send_transactions_to_analyst(normalized_transactions)
            
            # Small delay between batches to avoid overwhelming the Analyst
            if len(new_transactions) > BATCH_SIZE:
                await asyncio.sleep(1)
    
    except Exception as e:
        logger.error(f"Error in monitoring loop: {e}")


async def run_monitoring_loop(agent: Agent):
    """Continuously run the monitoring loop with intervals."""
    logger.info(f"Starting continuous monitoring with {POLLING_INTERVAL}s intervals")
    
    while True:
        try:
            await transaction_monitoring_loop(agent)
        except Exception as e:
            logger.error(f"Error in monitoring iteration: {e}")
        
        # Wait for next polling interval
        await asyncio.sleep(POLLING_INTERVAL)


async def send_transactions_to_analyst(transactions: List[Dict[str, Any]]) -> None:
    """
    Send normalized transactions to the Analyst agent for fraud analysis.
    
    Args:
        transactions: List of normalized transaction dictionaries
    """
    try:
        for tx in transactions:
            # Prepare payload for Analyst agent
            analysis_request = {
                'request_type': 'transaction_analysis',
                'transaction_data': tx,
                'source': 'vigil_observer',
                'timestamp': datetime.utcnow().isoformat()
            }
            
            logger.info(f"Sending transaction {tx['transaction_id']} to Analyst for analysis")
            
            # Send via A2A communication (this would be implemented with actual ADK A2A client)
            # For now, we'll log what would be sent
            logger.debug(f"A2A Request to Analyst: {analysis_request}")
            
            # In a real implementation, this would be something like:
            # await agent.send_a2a_message(ANALYST_AGENT_URL, analysis_request)
            
    except Exception as e:
        logger.error(f"Error sending transactions to Analyst: {e}")


# Async agent creation for development
async def get_agent_async():
    """Create agent for adk web development environment."""
    return create_observer_agent()


async def main():
    """Main entry point for the observer agent."""
    global app_ready
    
    logger.info("Starting Vigil Observer Agent...")
    
    try:
        # Start health server first
        health_runner = await start_health_server()
        logger.info("Health server started")
        
        # Create the observer agent
        agent = create_observer_agent()
        logger.info("Observer agent created")
        
        # Mark as ready after agent is created
        app_ready = True
        logger.info("Observer agent marked as ready")
        
        # Start the monitoring loop
        logger.info("Starting transaction monitoring loop...")
        await run_monitoring_loop(agent)
        
    except Exception as e:
        logger.error(f"Failed to start observer agent: {e}")
        raise


if __name__ == "__main__":
    # Run the main async function
    asyncio.run(main())
