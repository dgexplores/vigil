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
import asyncio
import logging
import json
import requests
from a2a.client.legacy import A2AClient
from a2a.types import (
    JSONRPCErrorResponse,
    Message,
    MessageSendParams,
    Role,
    SendMessageRequest,
    SendMessageResponse,
    SendMessageSuccessResponse,
    Task,
    TextPart,
)
import httpx
import uuid

from delivery_store import DeliveryStore

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
        self.delivery_store = DeliveryStore(
            os.environ.get("MONITOR_STATE_PATH", "data/monitor.sqlite3"),
            os.environ.get("MONITOR_START_TIMESTAMP", "1970-01-01T00:00:00+00:00"),
        )
        self.last_processed_timestamp = self.delivery_store.checkpoint
        logger.info("TransactionMonitorAgent initialized.")

    async def run(self) -> None:
        """The main loop of the agent."""
        logger.info(f"Starting transaction monitoring loop (poll interval: {POLL_INTERVAL}s)...")
        while True:
            await self.process_new_transactions()
            await asyncio.sleep(POLL_INTERVAL)

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
                        data = result["data"]
                    elif "rows" in result:
                        data = result["rows"]
                    elif "result" in result:
                        data = result["result"]
                    else:
                        # If it's already a list/array, return as is
                        data = result if isinstance(result, list) else []
                    
                    # If data is a string, parse it as JSON
                    if isinstance(data, str):
                        try:
                            data = json.loads(data)
                        except json.JSONDecodeError as e:
                            logger.error(f"Failed to parse JSON response from genai-toolbox: {e}")
                            return []
                    
                    return data if isinstance(data, list) else []
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

    async def process_new_transactions(self) -> None:
        """Persist fetched alerts before dispatch, and retry unacknowledged alerts."""
        try:
            transactions = await asyncio.to_thread(
                self.get_new_transactions_via_genai_toolbox,
                self.delivery_store.checkpoint,
            )
            self.delivery_store.ingest(transactions, FRAUD_THRESHOLD)
            self.last_processed_timestamp = self.delivery_store.checkpoint
        except Exception:
            logger.exception("Polling failed; checkpoint not advanced")

        # A polling failure must not prevent delivery of already persisted alerts.
        for tx in self.delivery_store.pending():
            try:
                success = await self.alert_orchestrator(tx)
                self.delivery_store.record_attempt(
                    tx["transaction_id"], success,
                    None if success else "No successful A2A acknowledgement",
                )
            except Exception as exc:
                self.delivery_store.record_attempt(tx["transaction_id"], False, str(exc))
                logger.exception("Alert dispatch failed")
        logger.info("Delivery summary: %s", self.delivery_store.summary())

    @staticmethod
    def _extract_message_text(message: Message) -> str:
        """Return concatenated text from the parts of a Message."""
        if not getattr(message, "parts", None):
            return ""

        texts = []
        for part in message.parts:
            text_value = None
            if hasattr(part, "root") and getattr(part.root, "text", None):
                text_value = part.root.text
            elif getattr(part, "text", None):
                text_value = part.text

            if text_value:
                texts.append(text_value.strip())

        return "\n".join(filter(None, texts))

    @staticmethod
    def _format_success_payload(result_payload):
        """Generate a human-readable summary for orchestrator responses."""
        if isinstance(result_payload, Message):
            text = TransactionMonitorAgent._extract_message_text(result_payload)
            return text or f"Message parts: {result_payload.parts}"

        if isinstance(result_payload, Task):
            return f"Task {result_payload.id} status={result_payload.status.state}"

        return repr(result_payload)

    def create_orchestrator_client(self):
        """Create A2A client for orchestrator communication."""
        try:
            # Create legacy A2A client with httpx
            httpx_client = httpx.AsyncClient(timeout=httpx.Timeout(60.0))
            client = A2AClient(
                httpx_client=httpx_client,
                url=f"{ORCHESTRATOR_URL}"
            )
            logger.info(f"Created A2A client for orchestrator at {ORCHESTRATOR_URL}/a2a")
            return client
        except Exception as e:
            logger.error(f"Failed to create A2A client: {e}")
            return None

    async def alert_orchestrator(self, transaction: dict) -> bool:
        """Sends a transaction alert to the orchestrator agent via A2A protocol."""
        try:
            # Lazy initialization of client
            if self.orchestrator_client is None:
                self.orchestrator_client = self.create_orchestrator_client()
            
            if self.orchestrator_client is None:
                logger.warning(f"No A2A client available, skipping alert for transaction: {transaction['transaction_id']}")
                return False
            
            logger.info(f"Sending A2A alert for transaction: {transaction['transaction_id']}")
            logger.info(f"Transaction details: amount={transaction.get('amount')}, to_account={transaction.get('to_account_id')}")
            
            # Create properly formatted A2A message request for the orchestrator
            text_part = TextPart(
                text=f"Process transaction alert: {json.dumps(transaction)}"
            )
            message_content = Message(
                message_id=str(uuid.uuid5(uuid.NAMESPACE_URL, "vigil:" + str(transaction["transaction_id"]))),
                role=Role.user,
                parts=[text_part]
            )
            message_params = MessageSendParams(message=message_content)
            message_request = SendMessageRequest(
                id=1,
                params=message_params
            )
            
            # Send A2A message to orchestrator
            response = await self.orchestrator_client.send_message(message_request)

            if not isinstance(response, SendMessageResponse):
                logger.error(
                    "Unexpected orchestrator response type for transaction %s: %s",
                    transaction["transaction_id"],
                    type(response),
                )
                return False

            root_payload = response.root
            if isinstance(root_payload, JSONRPCErrorResponse):
                logger.error(
                    "Orchestrator returned JSON-RPC error for transaction %s: %s",
                    transaction["transaction_id"],
                    root_payload.error,
                )
                return False

            if isinstance(root_payload, SendMessageSuccessResponse):
                payload = root_payload.result
            else:
                payload = getattr(root_payload, "result", None)

            if payload is None:
                logger.error(
                    "Orchestrator response missing result for transaction %s",
                    transaction["transaction_id"],
                )
                return False

            # A returned Task is not proof that processing completed.
            if isinstance(payload, Task) and payload.status.state.value != "completed":
                return False
            if isinstance(payload, Message):
                text = self._extract_message_text(payload)
                prefix = "Transaction alert processed:"
                if text.startswith(prefix):
                    text = text[len(prefix):].strip()
                # JSON-RPC transport success can carry an application error.
                try:
                    result = json.loads(text)
                except (ValueError, TypeError):
                    logger.error("Expected structured orchestration acknowledgement")
                    return False
                if not isinstance(result, dict) or result.get("status") != "completed":
                    return False
            summary = self._format_success_payload(payload)
            logger.info(
                "Successfully sent alert for transaction %s. Orchestrator response: %s",
                transaction["transaction_id"],
                summary,
            )

            return True

        except Exception as e:
            logger.error(f"Failed to alert orchestrator for transaction {transaction['transaction_id']}: {e}", exc_info=True)

            return False


async def main() -> None:
    """Entry point for the agent."""
    try:
        agent = TransactionMonitorAgent()
        await agent.run()
    except Exception as e:
        logger.fatal(f"Failed to start TransactionMonitorAgent: {e}", exc_info=True)

if __name__ == "__main__":
    asyncio.run(main())
