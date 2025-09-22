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
import uuid
import asyncio
from typing import Dict, Any

from fastapi import FastAPI, HTTPException
import uvicorn
from google.adk.agents import LlmAgent
from google.adk.models import Gemini
from a2a.types import SendMessageRequest, SendMessageResponse, SendMessageSuccessResponse, Message, TextPart, Role

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Get config from environment variables
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")

CRITIC_PROMPT = """
You are a skeptical risk analyst. Your role is to challenge the findings in this case file.
Find evidence that contradicts the suspicion of fraud.
Identify legitimate alternative explanations for the observed behavior.
Conclude with a 'concur' or 'dissent' verdict.
Your final response must be a JSON object containing a single key "verdict" with a value of either "concur" or "dissent".
"""

# Create FastAPI app for A2A server functionality
app = FastAPI(title="Critic Agent A2A Server")

# Global critic service instance
critic_service = None

class CriticService:
    def __init__(self):
        logger.info("Initializing CriticService...")
        self.llm_agent = LlmAgent(
            name="critic_agent",
            model=Gemini(api_key=GEMINI_API_KEY),
            instruction=CRITIC_PROMPT,
        )
        logger.info("CriticService initialized.")

    async def critique_case(self, case_file_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Receives a case file, uses an LLM to critique it, and returns a verdict.
        """
        logger.info("Received request to critique case file.")

        prompt = (
            "Please critique the following fraud investigation case file:\n"
            f"{json.dumps(case_file_data, indent=2)}\n\n"
            "Based on your analysis, provide your verdict as a JSON object."
        )

        try:
            logger.info("Sending case file to LLM for critique...")
            # Use async/await pattern for LLM processing
            llm_response = await asyncio.to_thread(self.llm_agent.send, prompt)
            # The response from the LLM is expected to be a JSON string.
            # We need to clean it up in case the LLM adds markdown backticks.
            cleaned_response = llm_response.strip().replace("```json", "").replace("```", "").strip()
            verdict = json.loads(cleaned_response)
            logger.info(f"Received verdict from LLM: {verdict}")
        except Exception as e:
            logger.error(f"Error processing LLM response: {e}", exc_info=True)
            return {"error": f"Failed to get verdict from LLM: {e}", "llm_response": str(e)}

        return verdict

# A2A FastAPI endpoints
@app.post("/a2a/send-message")
async def handle_a2a_message(request: SendMessageRequest) -> SendMessageResponse:
    """Handle incoming A2A messages from other agents."""
    global critic_service
    
    if critic_service is None:
        raise HTTPException(status_code=500, detail="Critic service not initialized")
    
    try:
        # Extract message text from A2A message parts
        message_text = ""
        if hasattr(request, 'params') and request.params:
            if hasattr(request.params, 'message') and request.params.message:
                if hasattr(request.params.message, 'parts') and request.params.message.parts:
                    for part in request.params.message.parts:
                        # Part has a 'root' attribute containing the TextPart
                        if hasattr(part, 'root') and hasattr(part.root, 'text'):
                            message_text = part.root.text
                            break
        
        logger.info(f"Received A2A message: {message_text}")
        
        # Parse the case file data from the message
        if "critique_case:" in message_text or "case_file" in message_text:
            # Try to extract JSON from the message
            try:
                if "critique_case:" in message_text:
                    case_file_json = message_text.replace("critique_case: ", "")
                else:
                    case_file_json = message_text
                    
                case_file_data = json.loads(case_file_json)
                
                # Process the case file critique
                result = await critic_service.critique_case(case_file_data)
                
                # Create proper A2A response message
                response_text = TextPart(text=f"Critique completed: {json.dumps(result)}")
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
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse case file data from message: {e}")
                # Create error response
                response_text = TextPart(text=f"Error: Failed to parse case file data - {str(e)}")
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
        else:
            # Create proper A2A response message for unrecognized messages
            response_text = TextPart(text="Message received but not recognized as critique request")
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


@app.post("/critique")
async def critique_endpoint(case_file_data: Dict[str, Any]) -> Dict[str, Any]:
    """Direct REST endpoint for critique requests."""
    global critic_service
    
    if critic_service is None:
        raise HTTPException(status_code=500, detail="Critic service not initialized")
    
    try:
        result = await critic_service.critique_case(case_file_data)
        return result
    except Exception as e:
        logger.error(f"Error in critique endpoint: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Critique failed: {str(e)}")


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "service": "critic_agent"}


def main():
    """Entry point for the agent."""
    logger.info("Starting CriticAgent...")
    try:
        global critic_service
        critic_service = CriticService()
        logger.info("CriticAgent service created successfully")
        
        # Start FastAPI A2A server
        logger.info("Starting A2A server on port 8000...")
        uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")
        
    except Exception as e:
        logger.fatal(f"Failed to start CriticAgent: {e}", exc_info=True)


if __name__ == "__main__":
    main()
