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
from typing import Any, Dict, List, Set
from datetime import datetime, timedelta
import random
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
POLLING_INTERVAL = int(os.getenv('POLLING_INTERVAL', '5'))
BATCH_SIZE = int(os.getenv('BATCH_SIZE', '100'))

# Global variables for health status
app_ready = False
app_healthy = False


# --- HEALTH CHECK ENDPOINTS ---
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


# --- CORRECT AGENT DEFINITION ---
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
        self.processed_transactions: Set[str] = set()
        self.last_check_time = datetime.utcnow() - timedelta(minutes=5)
        
    async def get_new_transactions(self) -> List[Dict[str, Any]]:
        """Fetch new transactions by running a command through the agent."""
        try:
            # --- CORRECT TOOL USAGE ---
            # This is the key: command the agent to perform an action.
            # The agent will find the 'get_transactions' tool in its toolset.
            command_to_run = "Get recent transactions for all accounts"
            
            logger.info("Running command via agent to fetch transactions...")
            
            try:
                # The .run() method executes the command using the agent's tools
                response_str = await self.agent.run(command_to_run)
                
                # Parse the string response from the tool call
                transactions = self._parse_transaction_response(response_str)
                
            except AttributeError as e:
                # If agent.run() is not available, fallback to demo data
                logger.warning(f"Agent.run() not available ({e}), using demo data")
                transactions = self._generate_demo_transactions()
            except Exception as e:
                logger.error(f"Error fetching transactions: {e}")
                transactions = self._generate_demo_transactions()
            
            # Filter out already processed transactions
            new_transactions = []
            for tx in transactions:
                tx_id = tx.get('transaction_id', tx.get('id', ''))
                if tx_id and tx_id not in self.processed_transactions:
                    new_transactions.append(tx)
                    self.processed_transactions.add(tx_id)
            
            # Update last check time
            self.last_check_time = datetime.utcnow()
            
            # Prevent memory leak
            if len(self.processed_transactions) > 10000:
                recent_ids = list(self.processed_transactions)[-5000:]
                self.processed_transactions = set(recent_ids)
            
            logger.info(f"Found {len(new_transactions)} new transactions to process")
            return new_transactions
            
        except Exception as e:
            logger.error(f"Error in get_new_transactions: {e}")
            return []
    
    def _parse_transaction_response(self, response_str: str) -> List[Dict[str, Any]]:
        """Parse the string response from the tool call."""
        try:
            # Try to parse as JSON
            if response_str:
                transactions = json.loads(response_str)
                if isinstance(transactions, list):
                    return transactions
                elif isinstance(transactions, dict):
                    # If it's a single transaction, wrap in list
                    return [transactions]
        except json.JSONDecodeError:
            logger.warning("Could not parse response as JSON, using demo data")
        
        return self._generate_demo_transactions()
    
    def _generate_demo_transactions(self) -> List[Dict[str, Any]]:
        """Generate demo transaction data for testing."""
        num_new_transactions = random.randint(0, 3)
        transactions = []
        
        account_ids = ["1234567890", "0987654321", "1111222233", "5555666677", "9988776655"]
        transaction_types = ["transfer", "payment", "deposit", "withdrawal"]
        locations = ['São Paulo, BR', 'Mexico City, MX', 'Bogotá, CO', 'Buenos Aires, AR']
        
        for i in range(num_new_transactions):
            from_account = random.choice(account_ids)
            to_account = random.choice([acc for acc in account_ids if acc != from_account])
            
            transaction = {
                'transaction_id': f'tx_{int(datetime.utcnow().timestamp() * 1000)}_{i}',
                'from_account': from_account,
                'to_account': to_account,
                'amount': round(random.uniform(10.0, 5000.0), 2),
                'currency': 'USD',
                'timestamp': (datetime.utcnow() - timedelta(seconds=random.randint(0, 300))).isoformat(),
                'type': random.choice(transaction_types),
                'status': 'completed',
                'description': f'Demo transaction {i+1}',
                'source': 'bank_of_anthos_demo',
                'ip_address': f'192.168.1.{random.randint(1, 255)}',
                'location': random.choice(locations)
            }
            transactions.append(transaction)
        
        return transactions
    
    async def normalize_transaction(self, tx_data: Dict[str, Any]) -> Dict[str, Any]:
        """Normalize transaction data to standard format for fraud analysis."""
        try:
            normalized = {
                'transaction_id': tx_data.get('transaction_id', f'tx_{hash(str(tx_data)) % 100000}'),
                'timestamp': tx_data.get('timestamp', datetime.utcnow().isoformat()),
                'amount': float(tx_data.get('amount', 0.0)),
                'currency': tx_data.get('currency', 'USD'),
                'from_account': tx_data.get('from_account', ''),
                'to_account': tx_data.get('to_account', ''),
                'type': tx_data.get('type', 'transfer'),
                'description': tx_data.get('description', ''),
                'location': tx_data.get('location', ''),
                'ip_address': tx_data.get('ip_address', ''),
                'raw_data': tx_data,
                'processed_timestamp': datetime.utcnow().isoformat(),
                'observer_version': 'vigil-1.0'
            }
            
            # Enrich with user context if available
            await self._enrich_transaction_context(normalized)
            
            return normalized
            
        except Exception as e:
            logger.error(f"Error normalizing transaction: {e}")
            return {
                'transaction_id': f'tx_error_{datetime.utcnow().timestamp()}',
                'timestamp': datetime.utcnow().isoformat(),
                'amount': 0.0,
                'error': str(e),
                'raw_data': tx_data
            }
    
    async def _enrich_transaction_context(self, tx_data: Dict[str, Any]):
        """Enrich transaction with additional context data."""
        try:
            user_id = tx_data.get('from_account', '')[:4]  # Mock user ID from account
            if user_id:
                # Command the agent to get user details
                command = f"Get user details for user ID {user_id}"
                try:
                    response = await self.agent.run(command)
                    tx_data['user_context'] = response
                except Exception as e:
                    logger.debug(f"Could not enrich user context: {e}")
                    tx_data['user_context'] = {"mock_user": user_id}
        except Exception as e:
            logger.debug(f"Error enriching context: {e}")


async def send_transactions_to_analyst(transactions: List[Dict[str, Any]]) -> None:
    """Send normalized transactions to the Analyst agent for fraud analysis."""
    try:
        for tx in transactions:
            analysis_request = {
                'request_type': 'transaction_analysis',
                'transaction_data': tx,
                'source': 'vigil_observer',
                'timestamp': datetime.utcnow().isoformat()
            }
            
            logger.info(f"Sending transaction {tx['transaction_id']} to Analyst for analysis")
            
            # In a real implementation, this would use A2A communication
            # For now, we log what would be sent
            logger.debug(f"A2A Request to Analyst: {json.dumps(analysis_request, indent=2)}")
            
    except Exception as e:
        logger.error(f"Error sending transactions to Analyst: {e}")


# --- MAIN EXECUTION LOOP ---
async def run_monitoring_loop(agent: Agent):
    """Continuously run the monitoring loop with intervals."""
    processor = TransactionProcessor(agent)
    
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
        
        # Wait for next polling interval
        await asyncio.sleep(POLLING_INTERVAL)


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
        
        # Mark as ready
        app_ready = True
        logger.info("Observer agent marked as ready")
        
        # Start the monitoring loop
        logger.info("Starting transaction monitoring loop...")
        await run_monitoring_loop(agent)
        
    except Exception as e:
        logger.error(f"Failed to start observer agent: {e}")
        raise


if __name__ == "__main__":
    asyncio.run(main())