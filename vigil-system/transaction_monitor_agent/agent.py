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

from google.adk.agents import CustomAgent
from google.adk.tools import Toolbox
from google.adk.rpc import A2AClient

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Get config from environment variables
GENAL_TOOLBOX_URL = os.environ.get("GENAL_TOOLBOX_SERVICE_URL", "http://genal-toolbox-service")
ORCHESTRATOR_URL = os.environ.get("ORCHESTRATOR_SERVICE_URL", "http://orchestrator-agent-service")
POLL_INTERVAL = int(os.environ.get("POLL_INTERVAL", 5))
FRAUD_THRESHOLD = float(os.environ.get("FRAUD_THRESHOLD", 1000.0))

class TransactionMonitorAgent(CustomAgent):
    """
    A custom agent that monitors for new transactions, flags suspicious ones,
    and sends them to the Orchestrator agent for further processing.
    """

    def __init__(self) -> None:
        super().__init__()
        logger.info("Initializing TransactionMonitorAgent...")
        self.toolbox = Toolbox(f"{GENAL_TOOLBOX_URL}")
        self.orchestrator_client = A2AClient(f"{ORCHESTRATOR_URL}")
        self.last_processed_timestamp = datetime.now(timezone.utc).isoformat()
        logger.info("TransactionMonitorAgent initialized.")

    def run(self) -> None:
        """The main loop of the agent."""
        logger.info(f"Starting transaction monitoring loop (poll interval: {POLL_INTERVAL}s)...")
        while True:
            self.process_new_transactions()
            time.sleep(POLL_INTERVAL)

    def process_new_transactions(self) -> None:
        """Fetches and processes new transactions."""
        logger.info(f"Fetching new transactions since {self.last_processed_timestamp}...")
        try:
            response = self.toolbox.get_new_transactions(last_timestamp=self.last_processed_timestamp)

            if not response.tool_output:
                logger.info("No tool output received.")
                return

            transactions = response.tool_output[0].get("result", [])

            if not transactions:
                logger.info("No new transactions found.")
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

    def alert_orchestrator(self, transaction: dict) -> None:
        """Sends a transaction alert to the orchestrator agent."""
        try:
            self.orchestrator_client.send_request(
                "process_transaction_alert",
                transaction_data=transaction
            )
            logger.info(f"Successfully alerted orchestrator for transaction: {transaction['transaction_id']}")
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
