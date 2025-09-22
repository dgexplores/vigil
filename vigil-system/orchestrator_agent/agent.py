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
import asyncio
import uuid
from typing import Any

from fastapi import FastAPI, HTTPException
import uvicorn
from google.adk.agents import LlmAgent
from google.adk.tools import FunctionTool
from google.adk.models import Gemini
from google.genai import types
from google.adk.sessions.in_memory_session_service import InMemorySessionService
from google.adk.runners import Runner
import httpx
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

# Cache for downstream A2A clients keyed by agent label.
_client_registry: dict[str, A2AClient] = {}


def _get_or_create_client(cache_key: str, url: str) -> A2AClient | None:
    """Return a cached A2A client or create a new one for the target URL."""
    client = _client_registry.get(cache_key)
    if client is not None:
        return client

    try:
        httpx_client = httpx.AsyncClient(timeout=30.0)
        client = A2AClient(httpx_client=httpx_client, url=url)
        _client_registry[cache_key] = client
        logger.info("Created A2A client for %s at %s", cache_key, url)
        return client
    except Exception as exc:  # pragma: no cover - defensive logging
        logger.error(
            "Failed to create A2A client for %s at %s: %s",
            cache_key,
            url,
            exc,
            exc_info=True,
        )
        return None


def _extract_text_from_message(message: Message) -> str:
    """Combine all text parts from an A2A message into a single string."""
    texts: list[str] = []
    if message.parts:
        for part in message.parts:
            text_value = None
            if hasattr(part, "root") and hasattr(part.root, "text"):
                text_value = part.root.text
            elif hasattr(part, "text"):
                text_value = part.text
            if text_value:
                texts.append(text_value.strip())
    return "\n".join(filter(None, texts))


def _maybe_extract_json_payload(raw_text: str) -> Any | None:
    """Attempt to parse JSON content from an agent text response."""
    candidates: list[str] = []
    normalized = raw_text.strip()
    if normalized:
        candidates.append(normalized)
        colon_index = normalized.find(":")
        if colon_index != -1 and colon_index + 1 < len(normalized):
            candidates.append(normalized[colon_index + 1 :].strip())

    for candidate in candidates:
        if not candidate:
            continue
        try:
            return json.loads(candidate)
        except json.JSONDecodeError:
            continue
    return None


def _format_agent_result(agent_label: str, response: SendMessageResponse) -> dict[str, Any]:
    """Normalize SendMessageResponse into a JSON-serializable payload."""
    if response is None:
        return {"agent": agent_label, "error": "No response from agent"}

    root = response.root
    if isinstance(root, JSONRPCErrorResponse):
        error_payload = {"agent": agent_label, "error": "Remote agent returned an error"}
        if root.error:
            error_payload["code"] = root.error.code
            error_payload["message"] = root.error.message
            if root.error.data is not None:
                error_payload["data"] = root.error.data
        return error_payload

    result = root.result
    if isinstance(result, Message):
        text_content = _extract_text_from_message(result)
        payload: dict[str, Any] = {
            "agent": agent_label,
            "raw_message": text_content,
        }
        parsed = _maybe_extract_json_payload(text_content)
        if parsed is not None:
            payload["data"] = parsed
        return payload

    if isinstance(result, Task):
        return {
            "agent": agent_label,
            "task": result.model_dump(mode="json"),
        }

    return {"agent": agent_label, "result": result}


def _normalize_payload(payload: Any, agent_label: str) -> str | None:
    """Ensure payload is valid JSON and return it as a string."""
    if isinstance(payload, (dict, list, int, float, bool)) or payload is None:
        return json.dumps(payload)
    if isinstance(payload, str):
        candidate = payload.strip()
        if not candidate:
            return json.dumps({})
        try:
            parsed = json.loads(candidate)
        except json.JSONDecodeError:
            logger.warning(
                "Payload provided to %s delegate is not valid JSON: %s",
                agent_label,
                payload,
            )
            return None
        return json.dumps(parsed)

    logger.warning("Unsupported payload type %s for %s delegate", type(payload), agent_label)
    return None


async def _delegate_via_a2a(
    *,
    agent_label: str,
    cache_key: str,
    service_url: str,
    payload_prefix: str,
    payload: Any,
) -> dict[str, Any]:
    """Send a JSON-RPC message to a downstream agent and return normalized output."""
    client = _get_or_create_client(cache_key, service_url)
    if client is None:
        return {"agent": agent_label, "error": f"Unable to connect to {agent_label}"}

    payload_json = _normalize_payload(payload, agent_label)
    if payload_json is None:
        return {
            "agent": agent_label,
            "error": "Provided payload is not valid JSON",
        }

    message = Message(
        message_id=str(uuid.uuid4()),
        role=Role.user,
        parts=[TextPart(text=f"{payload_prefix} {payload_json}")],
    )
    request = SendMessageRequest(
        id=str(uuid.uuid4()),
        params=MessageSendParams(message=message),
    )

    try:
        response = await client.send_message(request)
    except Exception as exc:  # pragma: no cover - network failure path
        logger.error("Error while calling %s: %s", agent_label, exc, exc_info=True)
        return {"agent": agent_label, "error": str(exc)}

    return _format_agent_result(agent_label, response)


async def delegate_to_investigation_agent(transaction_details: Any) -> dict[str, Any]:
    """Delegates the investigation of a suspicious transaction to the InvestigationAgent."""
    logger.info("Delegating to InvestigationAgent with transaction payload.")
    return await _delegate_via_a2a(
        agent_label="InvestigationAgent",
        cache_key="investigation_agent",
        service_url=INVESTIGATION_AGENT_URL,
        payload_prefix="investigate_transaction:",
        payload=transaction_details,
    )


async def delegate_to_critic_agent(case_file: Any) -> dict[str, Any]:
    """Delegates the review of a case file to the CriticAgent."""
    logger.info("Delegating to CriticAgent with case file payload.")
    return await _delegate_via_a2a(
        agent_label="CriticAgent",
        cache_key="critic_agent",
        service_url=CRITIC_AGENT_URL,
        payload_prefix="critique_case:",
        payload=case_file,
    )


async def delegate_to_actuator_agent(action_command: Any) -> dict[str, Any]:
    """Delegates a validated action to the ActuatorAgent."""
    logger.info("Delegating to ActuatorAgent with command payload.")
    return await _delegate_via_a2a(
        agent_label="ActuatorAgent",
        cache_key="actuator_agent",
        service_url=ACTUATOR_AGENT_URL,
        payload_prefix="execute_action:",
        payload=action_command,
    )

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
        self.session_service = InMemorySessionService()
        self.runner = Runner(
            app_name="vigil_orchestrator_app",
            agent=self.llm_agent,
            session_service=self.session_service,
        )
        self.default_user_id = "transaction-monitor"
        logger.info("OrchestratorService initialized.")

    async def process_transaction_alert(self, transaction_data: dict) -> dict:
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
            message_content = types.Content(
                role="user",
                parts=[types.Part(text=initial_prompt)],
            )

            user_id = (
                transaction_data.get("from_account_id")
                or transaction_data.get("user_id")
                or self.default_user_id
            )
            session_id = str(uuid.uuid4())
            await self.session_service.create_session(
                app_name=self.runner.app_name,
                user_id=user_id,
                session_id=session_id,
            )

            tool_events: list[dict[str, Any]] = []
            final_text = ""
            last_text = ""

            async for event in self.runner.run_async(
                user_id=user_id,
                session_id=session_id,
                new_message=message_content,
            ):
                try:
                    function_calls = event.get_function_calls()
                except AttributeError:
                    function_calls = []
                for call in function_calls or []:
                    tool_events.append(
                        {
                            "event": "call",
                            "tool": call.name,
                            "args": call.args,
                        }
                    )

                try:
                    function_responses = event.get_function_responses()
                except AttributeError:
                    function_responses = []
                for response in function_responses or []:
                    tool_events.append(
                        {
                            "event": "response",
                            "tool": response.name,
                            "response": response.response,
                        }
                    )

                text_segments: list[str] = []
                if getattr(event, "content", None) and getattr(event.content, "parts", None):
                    for part in event.content.parts:
                        if getattr(part, "text", None):
                            text_segments.append(part.text.strip())

                if text_segments:
                    last_text = "\n".join(filter(None, text_segments))

                if getattr(event, "is_final_response", None) and event.is_final_response():
                    final_text = last_text

            summary = final_text or last_text or "No summary produced by orchestrator."
            logger.info(
                "Orchestration flow completed for session %s (user %s).",
                session_id,
                user_id,
            )
            return {
                "status": "completed",
                "summary": summary,
                "session_id": session_id,
                "user_id": user_id,
                "tool_events": tool_events,
            }
        except Exception as e:  # pragma: no cover - defensive logging
            logger.error(
                "An error occurred during the orchestration flow: %s",
                e,
                exc_info=True,
            )
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
        if hasattr(request, 'params') and request.params:
            if hasattr(request.params, 'message') and request.params.message:
                if hasattr(request.params.message, 'parts') and request.params.message.parts:
                    for part in request.params.message.parts:
                        # Part has a 'root' attribute containing the TextPart
                        if hasattr(part, 'root') and hasattr(part.root, 'text'):
                            message_text = part.root.text
                            break
        
        logger.info(f"Received A2A message: {message_text}")
        
        # Parse the transaction data from the message
        if "Process transaction alert:" in message_text:
            transaction_json = message_text.replace("Process transaction alert: ", "")
            transaction_data = json.loads(transaction_json)
            
            # Process the transaction alert
            result = await orchestrator_service.process_transaction_alert(transaction_data)
            
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
