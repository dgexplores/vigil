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

import requests
from fastapi import FastAPI, HTTPException
import uvicorn
from a2a.types import (
    SendMessageRequest,
    SendMessageResponse,
    SendMessageSuccessResponse,
    Message,
    TextPart,
    Role,
)

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Get config from environment variables
GENAL_TOOLBOX_URL = os.environ.get("GENAL_TOOLBOX_SERVICE_URL", "http://genal-toolbox-service")

# Create FastAPI app for A2A server functionality
app = FastAPI(title="Actuator Agent A2A Server")

# Global actuator service instance
actuator_service = None


class ActuatorService:
    def __init__(self):
        logger.info("Initializing ActuatorService...")
        self.genal_toolbox_url = GENAL_TOOLBOX_URL
        logger.info("ActuatorService initialized.")

    def call_genai_toolbox_api(self, tool_name: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Invoke a GenAI Toolbox tool via its REST API."""
        url = f"{self.genal_toolbox_url}/api/tool/{tool_name}/invoke"
        try:
            response = requests.post(
                url,
                json=payload,
                headers={"Content-Type": "application/json"},
                timeout=30,
            )

            if response.status_code == 200:
                result = response.json()
                if isinstance(result, dict):
                    if "data" in result:
                        data = result["data"]
                    elif "rows" in result:
                        data = result["rows"]
                    elif "result" in result:
                        data = result["result"]
                    else:
                        data = result

                    if isinstance(data, str):
                        try:
                            data = json.loads(data)
                        except json.JSONDecodeError as error:
                            logger.error(
                                "Failed to parse JSON response from genai-toolbox: %s",
                                str(error),
                            )
                            return {"error": "invalid_response", "details": str(error)}

                    return data if isinstance(data, dict) else {"result": data}
                if isinstance(result, list):
                    return {"result": result}

                logger.warning("Unexpected response format from genai-toolbox: %s", result)
                return {"error": "unexpected_response", "details": result}

            logger.error(
                "genai-toolbox HTTP error: %s - %s",
                response.status_code,
                response.text,
            )
            try:
                error_body = response.json()
            except ValueError:
                error_body = {"message": response.text}
            return {"error": "http_error", "details": error_body}
        except requests.RequestException as error:
            logger.error("Error calling genai-toolbox API: %s", str(error))
            return {"error": "request_failed", "details": str(error)}

    async def execute_action(self, command_data: Dict[str, Any]) -> Dict[str, Any]:
        """Execute an action using GenAI Toolbox tools."""
        action = command_data.get("action")
        logger.info("Received request to execute action: %s", action)

        if not action:
            logger.error("Missing 'action' in command data.")
            return {"status": "error", "message": "Missing 'action' in command"}

        if action == "lock_account":
            ext_user_id = command_data.get("ext_user_id")
            if not ext_user_id:
                logger.error("Missing 'ext_user_id' for lock_account action.")
                return {
                    "status": "error",
                    "message": "Missing 'ext_user_id' for lock_account action",
                }

            logger.info("Executing lock_account tool for ext_user_id: %s", ext_user_id)
            response = await asyncio.to_thread(
                self.call_genai_toolbox_api,
                "lock_account",
                {"ext_user_id": ext_user_id},
            )

            if isinstance(response, dict) and response.get("error"):
                logger.error(
                    "Error executing lock_account for ext_user_id %s: %s",
                    ext_user_id,
                    response,
                )
                return {
                    "status": "error",
                    "message": "Failed to lock account",
                    "details": response,
                }

            logger.info("Successfully locked account for ext_user_id: %s", ext_user_id)
            return {
                "status": "success",
                "action": action,
                "ext_user_id": ext_user_id,
                "response": response,
            }

        logger.warning("Unknown action received: %s", action)
        return {"status": "error", "message": f"Unknown action: {action}"}


@app.post("/a2a/send-message")
async def handle_a2a_message(request: SendMessageRequest) -> SendMessageResponse:
    """Handle incoming A2A messages from other agents."""
    global actuator_service

    if actuator_service is None:
        raise HTTPException(status_code=500, detail="Actuator service not initialized")

    try:
        message_text = ""
        if hasattr(request, "params") and request.params:
            if hasattr(request.params, "message") and request.params.message:
                if hasattr(request.params.message, "parts") and request.params.message.parts:
                    for part in request.params.message.parts:
                        if hasattr(part, "root") and hasattr(part.root, "text"):
                            message_text = part.root.text
                            break

        logger.info("Received A2A message: %s", message_text)

        if "execute_action:" in message_text or "action" in message_text:
            try:
                if "execute_action:" in message_text:
                    command_json = message_text.replace("execute_action: ", "", 1)
                else:
                    command_json = message_text

                command_data = json.loads(command_json)
            except json.JSONDecodeError as error:
                logger.error("Failed to parse command data from message: %s", str(error))
                response_text = TextPart(text=f"Error: Failed to parse command data - {str(error)}")
                response_message = Message(
                    message_id=str(uuid.uuid4()),
                    role=Role.agent,
                    parts=[response_text],
                )
                success_response = SendMessageSuccessResponse(
                    id=request.id,
                    result=response_message,
                )
                return SendMessageResponse(root=success_response)

            result = await actuator_service.execute_action(command_data)
            response_text = TextPart(text=f"Action executed: {json.dumps(result)}")
            response_message = Message(
                message_id=str(uuid.uuid4()),
                role=Role.agent,
                parts=[response_text],
            )
            success_response = SendMessageSuccessResponse(
                id=request.id,
                result=response_message,
            )
            return SendMessageResponse(root=success_response)

        response_text = TextPart(text="Message received but not recognized as actuator command")
        response_message = Message(
            message_id=str(uuid.uuid4()),
            role=Role.agent,
            parts=[response_text],
        )
        success_response = SendMessageSuccessResponse(
            id=request.id,
            result=response_message,
        )
        return SendMessageResponse(root=success_response)

    except Exception as error:
        logger.error("Error processing A2A message: %s", str(error), exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error processing message: {str(error)}")


@app.post("/")
async def handle_root_a2a_message(request: SendMessageRequest) -> SendMessageResponse:
    """Handle A2A messages at root endpoint."""
    return await handle_a2a_message(request)


@app.post("/execute")
async def execute_endpoint(command_data: Dict[str, Any]) -> Dict[str, Any]:
    """Direct REST endpoint for execute requests."""
    global actuator_service

    if actuator_service is None:
        raise HTTPException(status_code=500, detail="Actuator service not initialized")

    try:
        result = await actuator_service.execute_action(command_data)
        return result
    except Exception as error:
        logger.error("Error in execute endpoint: %s", str(error), exc_info=True)
        raise HTTPException(status_code=500, detail=f"Execution failed: {str(error)}")


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "service": "actuator_agent"}


def main():
    """Entry point for the agent."""
    logger.info("Starting ActuatorAgent...")
    try:
        global actuator_service
        actuator_service = ActuatorService()
        logger.info("ActuatorAgent service created successfully")

        logger.info("Starting A2A server on port 8000...")
        uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")

    except Exception as error:
        logger.fatal("Failed to start ActuatorAgent: %s", str(error), exc_info=True)


if __name__ == "__main__":
    main()
