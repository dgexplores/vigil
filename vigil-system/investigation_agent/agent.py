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
import logging
import json

from google.adk.agents import LlmAgent
from google.adk.rpc import A2AServer, rpc
from google.adk.tools import Toolbox
from google.adk.models import Gemini

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Get config from environment variables
GENAL_TOOLBOX_URL = os.environ.get("GENAL_TOOLBOX_SERVICE_URL", "http://genal-toolbox-service")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")

INVESTIGATION_PROMPT = """
You are a financial investigator. Your task is to analyze the provided transaction and user data to assess the risk of fraud.
Based on the information, provide a risk score from 0 (no risk) to 10 (high risk) and a detailed justification for your assessment.
Consider the transaction amount, user's transaction history, and any other relevant details.
Format your response as a JSON object with two keys: "risk_score" and "justification".
"""

class InvestigationService:
    def __init__(self):
        logger.info("Initializing InvestigationService...")
        self.toolbox = Toolbox(f"{GENAL_TOOLBOX_URL}")
        self.llm_agent = LlmAgent(
            model=Gemini(api_key=GEMINI_API_KEY),
            instruction=INVESTIGATION_PROMPT,
        )
        logger.info("InvestigationService initialized.")

    @rpc
    def investigate_transaction(self, transaction_data: dict) -> dict:
        """
        Receives a transaction, gathers context, uses an LLM to analyze it,
        and returns a structured case file.
        """
        logger.info(f"Received request to investigate transaction: {transaction_data.get('transaction_id')}")
        account_id = transaction_data.get("from_account_id")
        if not account_id:
            logger.error("Missing 'from_account_id' in transaction data.")
            return {"error": "Missing from_account_id in transaction data"}

        try:
            logger.info(f"Fetching details for account: {account_id}")
            user_details_resp = self.toolbox.get_user_details_by_account(account_id=account_id)
            logger.info(f"Fetching transaction history for account: {account_id}")
            transaction_history_resp = self.toolbox.get_user_transaction_history(account_id=account_id)

            user_details = user_details_resp.tool_output[0].get("result", [])
            transaction_history = transaction_history_resp.tool_output[0].get("result", [])
        except Exception as e:
            logger.error(f"Error calling GenAl Toolbox: {e}", exc_info=True)
            return {"error": f"Failed to gather context: {e}"}

        prompt = (
            "Please investigate the following transaction:\n"
            f"{json.dumps(transaction_data, indent=2)}\n\n"
            "Here is the user's profile:\n"
            f"{json.dumps(user_details, indent=2)}\n\n"
            "And here is the user's recent transaction history:\n"
            f"{json.dumps(transaction_history, indent=2)}\n\n"
            "Provide your risk assessment as a JSON object."
        )

        try:
            logger.info("Sending data to LLM for fraud analysis...")
            llm_response = self.llm_agent.send(prompt)
            # The response from the LLM is expected to be a JSON string.
            # We need to clean it up in case the LLM adds markdown backticks.
            cleaned_response = llm_response.strip().replace("```json", "").replace("```", "").strip()
            analysis = json.loads(cleaned_response)
            logger.info(f"Received analysis from LLM: {analysis}")
        except Exception as e:
            logger.error(f"Error processing LLM response: {e}", exc_info=True)
            return {"error": f"Failed to get analysis from LLM: {e}", "llm_response": llm_response}

        case_file = {
            "transaction_data": transaction_data,
            "user_details": user_details,
            "transaction_history": transaction_history,
            "fraud_analysis": analysis,
        }
        logger.info(f"Case file created for transaction: {transaction_data.get('transaction_id')}")
        return case_file

def main():
    """Entry point for the agent."""
    logger.info("Starting InvestigationAgent...")
    try:
        service = InvestigationService()
        server = A2AServer(service)
        server.start()
    except Exception as e:
        logger.fatal(f"Failed to start InvestigationAgent: {e}", exc_info=True)

if __name__ == "__main__":
    main()
