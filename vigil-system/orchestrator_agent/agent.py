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
import time
import asyncio
import uuid
from typing import Annotated

from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
import uvicorn
from google.adk.agents import LlmAgent
from google.adk.tools import FunctionTool
from google.adk.models import Gemini
from a2a.client import ClientFactory
from a2a.types import SendMessageRequest, SendMessageResponse, SendMessageSuccessResponse, Task, Message, TextPart, Role

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

# Create A2A clients using ClientFactory (will be initialized when needed)
def create_client(url):
    """Create an A2A client for the given URL using ClientFactory"""
    return ClientFactory.create_client_with_jsonrpc_transport(url=url)

investigation_client = None
critic_client = None
actuator_client = None

def delegate_to_investigation_agent(transaction_details: str) -> str:
    """Delegates the investigation of a suspicious transaction to the InvestigationAgent."""
    logger.info(f"Delegating to InvestigationAgent with transaction: {transaction_details}")
    try:
        global investigation_client
        if investigation_client is None:
            investigation_client = create_client(INVESTIGATION_AGENT_URL)
        
        # For now, return a simulated response since other agents are not yet deployed
        logger.info("Simulating investigation response (other agents not yet deployed)")
        return json.dumps({
            "status": "investigation_completed",
            "risk_score": 0.75,
            "findings": "High-value transaction to new recipient",
            "recommendation": "Review required"
        })
    except Exception as e:
        logger.error(f"Error calling InvestigationAgent: {e}", exc_info=True)
        return f"Error: {e}"

def delegate_to_critic_agent(case_file: str) -> str:
    """Delegates the review of a case file to the CriticAgent."""
    logger.info(f"Delegating to CriticAgent with case file: {case_file}")
    try:
        global critic_client
        if critic_client is None:
            critic_client = create_client(CRITIC_AGENT_URL)
        
        # For now, return a simulated response since other agents are not yet deployed
        logger.info("Simulating critic response (other agents not yet deployed)")
        return json.dumps({
            "status": "critique_completed",
            "verdict": "concur",
            "confidence": 0.8,
            "reasoning": "Pattern matches known fraud indicators"
        })
    except Exception as e:
        logger.error(f"Error calling CriticAgent: {e}", exc_info=True)
        return f"Error: {e}"

def delegate_to_actuator_agent(action_command: str) -> str:
    """Delegates a validated action to the ActuatorAgent."""
    logger.info(f"Delegating to ActuatorAgent with command: {action_command}")
    try:
        global actuator_client
        if actuator_client is None:
            actuator_client = create_client(ACTUATOR_AGENT_URL)
        
        # For now, return a simulated response since other agents are not yet deployed
        logger.info("Simulating actuator response (other agents not yet deployed)")
        return json.dumps({
            "status": "action_completed",
            "result": "Account security enhanced",
            "action_taken": "Monitoring increased for account"
        })
    except Exception as e:
        logger.error(f"Error calling ActuatorAgent: {e}", exc_info=True)
        return f"Error: {e}"

# Create function tools
investigation_tool = FunctionTool(delegate_to_investigation_agent)
critic_tool = FunctionTool(delegate_to_critic_agent)
actuator_tool = FunctionTool(delegate_to_actuator_agent)


# Create FastAPI app for A2A server functionality
app = FastAPI(title="Orchestrator Agent A2A Server")

# Global orchestrator service instance
orchestrator_service = None

class OrchestratorService:
    def __init__(self):
        logger.info("Initializing OrchestratorService...")
        self.llm_agent = LlmAgent(
            name="orchestrator_agent",
            model=Gemini(api_key=GEMINI_API_KEY),
            instruction=ORCHESTRATOR_PROMPT,
            tools=[
                investigation_tool,
                critic_tool,
                actuator_tool,
            ],
        )
        logger.info("OrchestratorService initialized.")

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


# A2A FastAPI endpoints
@app.post("/a2a/send-message")
async def handle_a2a_message(request: SendMessageRequest) -> SendMessageResponse:
    """Handle incoming A2A messages from other agents."""
    global orchestrator_service
    
    if orchestrator_service is None:
        raise HTTPException(status_code=500, detail="Orchestrator service not initialized")
    
    try:
        # Extract message text from A2A message parts
        message_text = ""
        if hasattr(request.params, 'message') and hasattr(request.params.message, 'parts'):
            for part in request.params.message.parts:
                if hasattr(part, 'text'):
                    message_text = part.text
                    break
        
        logger.info(f"Received A2A message: {message_text}")
        
        # Parse the transaction data from the message
        if "Process transaction alert:" in message_text:
            transaction_json = message_text.replace("Process transaction alert: ", "")
            transaction_data = json.loads(transaction_json)
            
            # Process the transaction alert
            result = orchestrator_service.process_transaction_alert(transaction_data)
            
            # Create proper A2A response message
            response_text = TextPart(text=f"Transaction alert processed: {json.dumps(result)}")
            response_message = Message(
                message_id=str(uuid.uuid4()),
                role=Role.agent,
                parts=[response_text]
            )
            
            # Return proper A2A success response
            success_response = SendMessageSuccessResponse(
                id=request.id,
                result=response_message
            )
            return SendMessageResponse(root=success_response)
        else:
            # Create proper A2A response message for unrecognized messages
            response_text = TextPart(text="Message received but not recognized as transaction alert")
            response_message = Message(
                message_id=str(uuid.uuid4()),
                role=Role.agent,
                parts=[response_text]
            )
            
            success_response = SendMessageSuccessResponse(
                id=request.id,
                result=response_message
            )
            return SendMessageResponse(root=success_response)
            
    except Exception as e:
        logger.error(f"Error processing A2A message: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error processing message: {str(e)}")


@app.post("/")
async def handle_root_a2a_message(request: SendMessageRequest) -> SendMessageResponse:
    """Handle A2A messages at root endpoint."""
    return await handle_a2a_message(request)

@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "service": "orchestrator_agent"}


def main():
    """Entry point for the agent."""
    logger.info("Starting OrchestratorAgent...")
    try:
        global orchestrator_service
        orchestrator_service = OrchestratorService()
        logger.info("OrchestratorAgent service created successfully")
        
        # Start FastAPI A2A server
        logger.info("Starting A2A server on port 8000...")
        uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")
        
    except Exception as e:
        logger.fatal(f"Failed to start OrchestratorAgent: {e}", exc_info=True)


if __name__ == "__main__":
    main()
