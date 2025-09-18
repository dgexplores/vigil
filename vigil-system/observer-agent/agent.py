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

from google.adk.agents import LoopAgent
from google.adk.tools.mcp_tool.mcp_toolset import MCPToolset
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


def create_observer_agent() -> LoopAgent:
    """Create the Vigil Observer Agent as a continuous monitoring loop."""
    
    # Ensure MCP server path exists
    if not os.path.exists(MCP_SERVER_PATH):
        logger.warning(f"MCP server not found at {MCP_SERVER_PATH}, using relative path")
        mcp_server_path = "./vigil_mcp_lowlevel.py"
    else:
        mcp_server_path = MCP_SERVER_PATH
    
    agent = LoopAgent(
        name='vigil_observer_agent',
        loop_function=transaction_monitoring_loop,
        interval_seconds=POLLING_INTERVAL,
        tools=[
            MCPToolset(
                connection_params=StdioConnectionParams(
                    server_params=StdioServerParameters(
                        command='python3',
                        args=[mcp_server_path, '--transport', 'stdio']
                    )
                ),
                # Observer needs read access to all transaction data
                tool_filter=['get_transactions', 'get_user_details', 'get_account_balance']
            )
        ],
        # Enable A2A communication for sending data to Analyst
        a2a_port=OBSERVER_PORT
    )
    
    return agent


class TransactionProcessor:
    """Processes and normalizes transaction data from Bank of Anthos."""
    
    def __init__(self, agent: LoopAgent):
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
            
            # Use MCP tools to get transaction data
            response = await self.agent.prompt_model(query_prompt)
            transactions = self._parse_transaction_response(response)
            
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
            
            logger.info(f"Found {len(new_transactions)} new transactions to process")
            return new_transactions
            
        except Exception as e:
            logger.error(f"Error fetching transactions: {e}")
            return []
    
    def _parse_transaction_response(self, response: str) -> List[Dict[str, Any]]:
        """Parse MCP response into structured transaction data."""
        transactions = []
        
        try:
            # Try to extract JSON array or objects from response
            if '[' in response and ']' in response:
                # Array format
                json_start = response.find('[')
                json_end = response.rfind(']') + 1
                json_str = response[json_start:json_end]
                parsed_data = json.loads(json_str)
                
                if isinstance(parsed_data, list):
                    transactions.extend(parsed_data)
                else:
                    transactions.append(parsed_data)
                    
            elif '{' in response and '}' in response:
                # Single object format
                json_start = response.find('{')
                json_end = response.rfind('}') + 1
                json_str = response[json_start:json_end]
                parsed_data = json.loads(json_str)
                
                if isinstance(parsed_data, dict):
                    transactions.append(parsed_data)
                    
            else:
                # Try to parse line-by-line for simple formats
                lines = response.strip().split('\n')
                for line in lines:
                    if line.strip() and ('transaction' in line.lower() or 'tx' in line.lower()):
                        # Basic parsing for demo data
                        tx_data = self._parse_transaction_line(line)
                        if tx_data:
                            transactions.append(tx_data)
                            
        except json.JSONDecodeError as e:
            logger.warning(f"Could not parse transaction JSON: {e}")
            # Fallback: try to extract basic info from text
            transactions = self._extract_transactions_from_text(response)
        except Exception as e:
            logger.error(f"Error parsing transaction response: {e}")
            
        return transactions
    
    def _parse_transaction_line(self, line: str) -> Optional[Dict[str, Any]]:
        """Parse a single transaction line into structured data."""
        try:
            # Simple pattern matching for demo purposes
            # In production, this would be more sophisticated based on actual API formats
            
            # Generate a simple transaction ID if not present
            tx_id = hashlib.md5(line.encode()).hexdigest()[:12]
            
            return {
                'transaction_id': f'tx_{tx_id}',
                'raw_data': line.strip(),
                'timestamp': datetime.utcnow().isoformat(),
                'amount': 0.0,  # Would be parsed from actual data
                'type': 'unknown',
                'source': 'observer_parsed'
            }
            
        except Exception:
            return None
    
    def _extract_transactions_from_text(self, text: str) -> List[Dict[str, Any]]:
        """Fallback method to extract transaction info from text response."""
        transactions = []
        
        lines = text.strip().split('\n')
        for i, line in enumerate(lines):
            if any(keyword in line.lower() for keyword in ['transfer', 'payment', 'debit', 'credit']):
                tx_id = f"tx_text_{i}_{hash(line) % 10000}"
                transactions.append({
                    'transaction_id': tx_id,
                    'raw_data': line.strip(),
                    'timestamp': datetime.utcnow().isoformat(),
                    'amount': 0.0,
                    'type': 'parsed_from_text',
                    'source': 'observer_text_extraction'
                })
        
        return transactions
    
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
                user_prompt = f"Get user details for user ID: {user_id}"
                user_response = await self.agent.prompt_model(user_prompt)
                tx_data['user_context'] = user_response
            
            # Get account balance if available
            if from_account:
                balance_prompt = f"Get account balance for account: {from_account}"
                balance_response = await self.agent.prompt_model(balance_prompt)
                tx_data['account_balance'] = balance_response
                
        except Exception as e:
            logger.warning(f"Could not enrich transaction context: {e}")
            tx_data['enrichment_error'] = str(e)


async def transaction_monitoring_loop(agent: LoopAgent) -> None:
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


# Main agent instance for synchronous deployment
root_agent = create_observer_agent()


# Async agent creation for development
async def get_agent_async():
    """Create agent for adk web development environment."""
    return create_observer_agent()


if __name__ == "__main__":
    # For testing purposes
    import asyncio
    
    async def test_monitoring():
        """Test the transaction monitoring functionality."""
        agent = create_observer_agent()
        processor = TransactionProcessor(agent)
        
        logger.info("Testing transaction monitoring...")
        
        # Simulate transaction monitoring loop
        await transaction_monitoring_loop(agent)
        
        print("\nObserver monitoring test completed")
    
    # Run test
    asyncio.run(test_monitoring())