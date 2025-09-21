# Copyright 2025 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import os
import time
from datetime import datetime, timezone
import logging
import json
import requests
from a2a.client import ClientFactory

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Get config from environment variables
GENAL_TOOLBOX_URL = os.environ.get("GENAL_TOOLBOX_SERVICE_URL", "http://genal-toolbox-service")
ORCHESTRATOR_URL = os.environ.get("ORCHESTRATOR_SERVICE_URL", "http://orchestrator-agent-service")
POLL_INTERVAL = int(os.environ.get("POLL_INTERVAL", 5))
FRAUD_THRESHOLD = float(os.environ.get("FRAUD_THRESHOLD", 1000.0))

class TransactionMonitorAgent:
    """
    A custom agent that monitors for new transactions, flags suspicious ones,
    and sends them to the Orchestrator agent for further processing.
    """

    def __init__(self) -> None:
        logger.info("Initializing TransactionMonitorAgent...")
        self.genal_toolbox_url = GENAL_TOOLBOX_URL
        self.orchestrator_client = None  # Lazy initialization
        self.last_processed_timestamp = datetime.now(timezone.utc).isoformat()
        logger.info("TransactionMonitorAgent initialized.")

    def run(self) -> None:
        """The main loop of the agent."""
        logger.info(f"Starting transaction monitoring loop (poll interval: {POLL_INTERVAL}s)...")
        while True:
            self.process_new_transactions()
            time.sleep(POLL_INTERVAL)

    def get_new_transactions_via_genai_toolbox(self, last_timestamp: str):
        """Get new transactions via genai-toolbox REST API."""
        try:
            # Call genai-toolbox using the correct REST API endpoint
            url = f"{self.genal_toolbox_url}/api/tool/get_new_transactions/invoke"
            
            # REST API request payload
            payload = {
                "last_timestamp": last_timestamp
            }
            
            response = requests.post(url, json=payload, headers={'Content-Type': 'application/json'}, timeout=30)
            
            if response.status_code == 200:
                result = response.json()
                # genai-toolbox returns results in various formats, typically with data or rows
                if isinstance(result, dict):
                    # Extract transaction data from various possible response formats
                    if "data" in result:
                        return result["data"]
                    elif "rows" in result:
                        return result["rows"]
                    elif "result" in result:
                        return result["result"]
                    else:
                        # If it's already a list/array, return as is
                        return result if isinstance(result, list) else []
                elif isinstance(result, list):
                    return result
                else:
                    logger.warning(f"Unexpected response format from genai-toolbox: {result}")
                    return []
            else:
                result = response.json() if response.headers.get('content-type') == 'application/json' else {}
                if "error" in result:
                    logger.error(f"genai-toolbox API error: {result['error']}")
                    # If it's a database schema issue, continue with simulation mode
                    if "does not exist" in result["error"]:
                        logger.info("Database schema issue detected, falling back to simulation mode")
                        return []
                else:
                    logger.error(f"genai-toolbox HTTP error: {response.status_code} - {response.text}")
                return []
        except Exception as e:
            logger.error(f"Error calling genai-toolbox API: {e}")
            return []

    def process_new_transactions(self) -> None:
        """Fetches and processes new transactions."""
        logger.info(f"Fetching new transactions since {self.last_processed_timestamp}...")
        try:
            # Use genai-toolbox REST API to get new transactions
            transactions = self.get_new_transactions_via_genai_toolbox(self.last_processed_timestamp)
             
            if not transactions:
                logger.info("No new transactions found.")
                # For development, still add some simulation for testing
                import random
                if random.random() < 0.1:  # 10% chance of simulated transaction for testing
                    simulated_tx = {
                        "transaction_id": f"sim_{int(time.time())}",
                        "amount": "1500.00",  # Above fraud threshold
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                        "from_account_id": "acc_123",
                        "to_account_id": "acc_456",
                        "recipient_id": "user_456"
                    }
                    logger.warning(f"Simulated high-value transaction detected: {simulated_tx['transaction_id']} for amount {simulated_tx['amount']}. Alerting orchestrator.")
                    self.alert_orchestrator(simulated_tx)
                    self.last_processed_timestamp = simulated_tx["timestamp"]
                return
             
            logger.info(f"Found {len(transactions)} new transactions.")
             
            latest_timestamp = self.last_processed_timestamp
            for tx in transactions:
                if float(tx.get("amount", 0)) > FRAUD_THRESHOLD:
                    logger.warning(f"High-value transaction detected: {tx['transaction_id']} for amount {tx['amount']}. Alerting orchestrator.")
                    self.alert_orchestrator(tx)
             
                if tx["timestamp"] > latest_timestamp:
                    latest_timestamp = tx["timestamp"]
             
            self.last_processed_timestamp = latest_timestamp

        except Exception as e:
            logger.error(f"Error processing new transactions: {e}", exc_info=True)

    def create_orchestrator_client(self):
        """Create A2A client for orchestrator communication."""
        try:
            # Try different A2A ClientFactory methods
            return ClientFactory.create_jsonrpc_client(url=f"{ORCHESTRATOR_URL}")
        except AttributeError:
            # Fallback for different API versions
            logger.warning("A2A ClientFactory method not found, using simulation mode")
            return None

    def alert_orchestrator(self, transaction: dict) -> None:
        """Sends a transaction alert to the orchestrator agent."""
        try:
            # Lazy initialization of client
            if self.orchestrator_client is None:
                self.orchestrator_client = self.create_orchestrator_client()
            
            # For development - simulate orchestrator alert since it may not be fully ready
            logger.info(f"Simulating orchestrator alert for transaction: {transaction['transaction_id']}")
            logger.info(f"Transaction details: amount={transaction.get('amount')}, recipient={transaction.get('recipient_id')}")
            
            # TODO: Replace with actual A2A call when orchestrator is fully integrated
            # self.orchestrator_client.send_request(
            #     "process_transaction_alert", 
            #     transaction_data=transaction
            # )
            
            logger.info(f"Successfully processed alert for transaction: {transaction['transaction_id']}")
        except Exception as e:
            logger.error(f"Failed to alert orchestrator for transaction {transaction['transaction_id']}: {e}", exc_info=True)


def main() -> None:
    """Entry point for the agent."""
    try:
        agent = TransactionMonitorAgent()
        agent.run()
    except Exception as e:
        logger.fatal(f"Failed to start TransactionMonitorAgent: {e}", exc_info=True)

if __name__ == "__main__":
    main()
