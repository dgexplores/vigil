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
from typing import Annotated

from google.adk.agents import LlmAgent
from google.adk.rpc import A2AServer, A2AClient, rpc
from google.adk.tools import tool
from google.adk.models import Gemini

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Get config from environment variables
INVESTIGATION_AGENT_URL = os.environ.get("INVESTIGATION_AGENT_SERVICE_URL", "http://investigation-agent-service")
CRITIC_AGENT_URL = os.environ.get("CRITIC_AGENT_SERVICE_URL", "http://critic-agent-service")
ACTUATOR_AGENT_URL = os.environ.get("ACTUATOR_AGENT_SERVICE_URL", "http://actuator-agent-service")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")

ORCHESTRATOR_PROMPT = """
You are 'Vigil Control', a master orchestrator for a team of AI fraud detection agents. Your mission is to analyze high-level alerts and delegate tasks to the appropriate specialized agent using the available A2A tools. For a new transaction alert, you must first delegate to the 'InvestigationAgent'. If the investigation yields a high-risk score, you must then delegate to the 'CriticAgent' for verification. Only after the CriticAgent concurs should you delegate to the 'ActuatorAgent' to take protective action. Sequence your calls logically and precisely.
"""

investigation_client = A2AClient(INVESTIGATION_AGENT_URL)
critic_client = A2AClient(CRITIC_AGENT_URL)
actuator_client = A2AClient(ACTUATOR_AGENT_URL)

@tool
def delegate_to_investigation_agent(
    transaction_details: Annotated[str, "The details of the suspicious transaction in JSON format."]
) -> str:
    """Delegates the investigation of a suspicious transaction to the InvestigationAgent."""
    logger.info(f"Delegating to InvestigationAgent with transaction: {transaction_details}")
    try:
        response = investigation_client.send_request("investigate_transaction", transaction_data=json.loads(transaction_details))
        return json.dumps(response)
    except Exception as e:
        logger.error(f"Error calling InvestigationAgent: {e}", exc_info=True)
        return f"Error: {e}"

@tool
def delegate_to_critic_agent(
    case_file: Annotated[str, "The case file from the investigation in JSON format."]
) -> str:
    """Delegates the review of a case file to the CriticAgent."""
    logger.info(f"Delegating to CriticAgent with case file: {case_file}")
    try:
        response = critic_client.send_request("critique_case", case_file_data=json.loads(case_file))
        return json.dumps(response)
    except Exception as e:
        logger.error(f"Error calling CriticAgent: {e}", exc_info=True)
        return f"Error: {e}"

@tool
def delegate_to_actuator_agent(
    action_command: Annotated[str, "The action command in JSON format, e.g., {'action': 'lock_account', 'ext_user_id': '...'}. "]
) -> str:
    """Delegates a validated action to the ActuatorAgent."""
    logger.info(f"Delegating to ActuatorAgent with command: {action_command}")
    try:
        response = actuator_client.send_request("execute_action", command_data=json.loads(action_command))
        return json.dumps(response)
    except Exception as e:
        logger.error(f"Error calling ActuatorAgent: {e}", exc_info=True)
        return f"Error: {e}"


class OrchestratorService:
    def __init__(self):
        logger.info("Initializing OrchestratorService...")
        self.llm_agent = LlmAgent(
            model=Gemini(api_key=GEMINI_API_KEY),
            instruction=ORCHESTRATOR_PROMPT,
            tools=[
                delegate_to_investigation_agent,
                delegate_to_critic_agent,
                delegate_to_actuator_agent,
            ],
        )
        logger.info("OrchestratorService initialized.")

    @rpc
    def process_transaction_alert(self, transaction_data: dict) -> dict:
        """
        This method is called by the TransactionMonitorAgent.
        It triggers the LLM agent to start the orchestration flow.
        """
        logger.info(f"Received transaction alert: {transaction_data}")
        initial_prompt = (
            "A new potentially fraudulent transaction has been detected. "
            "Here are the details:\n"
            f"{json.dumps(transaction_data, indent=2)}\n"
            "Your task is to follow the standard procedure: "
            "1. Delegate to the InvestigationAgent. "
            "2. Analyze the result. "
            "3. If necessary, delegate to the CriticAgent. "
            "4. Analyze the result. "
            "5. If necessary, delegate to the ActuatorAgent to take action. "
            "Provide a summary of the outcome."
        )
        try:
            final_response = self.llm_agent.send(initial_prompt)
            logger.info(f"Orchestration flow completed. Final response: {final_response}")
            return {"status": "completed", "summary": final_response}
        except Exception as e:
            logger.error(f"An error occurred during the orchestration flow: {e}", exc_info=True)
            return {"status": "error", "message": str(e)}


def main():
    """Entry point for the agent."""
    logger.info("Starting OrchestratorAgent...")
    try:
        service = OrchestratorService()
        server = A2AServer(service)
        server.start()
    except Exception as e:
        logger.fatal(f"Failed to start OrchestratorAgent: {e}", exc_info=True)


if __name__ == "__main__":
    main()
