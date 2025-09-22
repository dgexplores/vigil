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
from typing import Any, Optional

from fastapi import FastAPI, HTTPException
import uvicorn
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
from google.adk.agents import LlmAgent
from google.adk.models import Gemini
from google.adk.runners import Runner
from google.adk.sessions.in_memory_session_service import InMemorySessionService
from google.adk.tools import FunctionTool
from google.genai import types

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Get config from environment variables
INVESTIGATION_AGENT_URL = os.environ.get(
    "INVESTIGATION_AGENT_SERVICE_URL",
    "http://investigation-agent-service",
)
ACTUATOR_AGENT_URL = os.environ.get(
    "ACTUATOR_AGENT_SERVICE_URL",
    "http://actuator-agent-service",
)
RISK_SCORE_THRESHOLD = os.environ.get("RISK_SCORE_THRESHOLD", "7")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")

ORCHESTRATOR_PROMPT_TEMPLATE = """
You are Vigil Orchestrator, the command agent coordinating fraud investigations for Bank of Anthos.
Follow this doctrine for every transaction alert:
1. Always invoke the InvestigationAgent tool first, passing the raw transaction JSON so it can produce a case file with a risk score.
2. Review the investigation response. The escalation threshold for risky activity is {threshold}.
3. If the risk score is greater than or equal to {threshold}, call the ActuatorAgent tool exactly once with JSON of the form {{"action": "lock_account", "account_id": "<ACCOUNT_ID>", "ext_user_id": "<EXT_USER_ID>", "reason": "<SHORT_REASON>", "case_file": <CASE_FILE> }}. The GenAI toolbox expects the `account_id` field; include `ext_user_id` when available.
4. If the risk score is below the threshold, do not actuate; instead, summarize why no action was taken.
5. Conclude with a concise narrative summary that states the risk score, whether actuation occurred, and the supporting justification.
Do not send alternative keys such as "command". Avoid repeated actuator calls after a successful response.
"""

# Cache for downstream A2A clients keyed by agent label.
_client_registry: dict[str, A2AClient] = {}

_TOOL_LABELS = {
    "delegate_to_investigation_agent": "InvestigationAgent",
    "delegate_to_actuator_agent": "ActuatorAgent",
}


_latest_case_file: Any | None = None


def _human_tool_name(raw_name: str) -> str:
    return _TOOL_LABELS.get(raw_name, raw_name)


def _extract_tool_response(tool_events: list[dict[str, Any]], tool_label: str) -> Any:
    for event in reversed(tool_events):
        if event.get("tool") == tool_label and event.get("event") == "response":
            return event.get("response")
    return None


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


def _parse_float(value: Any) -> Optional[float]:
    """Attempt to convert a value to float, returning None on failure."""
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        candidate = value.strip().replace("%", "")
        if not candidate:
            return None
        try:
            return float(candidate)
        except ValueError:
            return None
    return None


def _extract_risk_score(case_file: Any) -> Optional[float]:
    """Extract a numeric risk score from the investigation case file."""
    if not isinstance(case_file, dict):
        return None

    fraud_analysis = case_file.get("fraud_analysis")
    if isinstance(fraud_analysis, dict):
        score = _parse_float(fraud_analysis.get("risk_score"))
        if score is not None:
            return score

    # Some responses may return risk_score at the top level
    return _parse_float(case_file.get("risk_score"))


def _extract_justification(case_file: Any) -> Optional[str]:
    """Retrieve a textual justification from the case file if available."""
    if not isinstance(case_file, dict):
        return None

    fraud_analysis = case_file.get("fraud_analysis")
    if isinstance(fraud_analysis, dict):
        justification = fraud_analysis.get("justification")
        if isinstance(justification, str):
            return justification

    justification = case_file.get("justification")
    if isinstance(justification, str):
        return justification

    return None


def _extract_ext_user_id(case_file: Any) -> Optional[str]:
    """Extract ext_user_id from the case file using multiple heuristics."""
    if not isinstance(case_file, dict):
        return None

    transaction_data = case_file.get("transaction_data")
    if isinstance(transaction_data, dict):
        for key in ("ext_user_id", "user_id", "from_account_id"):
            value = transaction_data.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()

    user_details = case_file.get("user_details")
    if isinstance(user_details, dict):
        candidate = user_details.get("ext_user_id")
        if isinstance(candidate, str) and candidate.strip():
            return candidate.strip()
    elif isinstance(user_details, list):
        for entry in user_details:
            if isinstance(entry, dict):
                candidate = entry.get("ext_user_id")
                if isinstance(candidate, str) and candidate.strip():
                    return candidate.strip()

    return None


def _extract_account_id(case_file: Any) -> Optional[str]:
    """Extract an account identifier from the case file."""
    if not isinstance(case_file, dict):
        return None

    transaction_data = case_file.get("transaction_data")
    if isinstance(transaction_data, dict):
        for key in ("account_id", "from_account_id", "user_id"):
            value = transaction_data.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()

    user_details = case_file.get("user_details")
    if isinstance(user_details, dict):
        candidate = user_details.get("account_id") or user_details.get("ext_user_id")
        if isinstance(candidate, str) and candidate.strip():
            return candidate.strip()
    elif isinstance(user_details, list):
        for entry in user_details:
            if isinstance(entry, dict):
                candidate = entry.get("account_id") or entry.get("ext_user_id")
                if isinstance(candidate, str) and candidate.strip():
                    return candidate.strip()

    return None


def _prepare_actuator_payload(raw_command: Any) -> tuple[Optional[dict[str, Any]], Optional[str]]:
    """Normalize LLM-provided actuator command payload."""
    if isinstance(raw_command, dict):
        payload = dict(raw_command)
    elif isinstance(raw_command, str):
        try:
            payload = json.loads(raw_command)
        except json.JSONDecodeError:
            return None, "Actuator command must be valid JSON."
    else:
        return None, f"Unsupported actuator payload type: {type(raw_command)}"

    case_file = payload.get("case_file")
    if case_file is None and _latest_case_file is not None:
        case_file = _latest_case_file
    account_id = payload.get("account_id") or payload.get("from_account_id")
    ext_user_id = payload.get("ext_user_id") or payload.get("user_id")

    if account_id is None and isinstance(case_file, dict):
        account_id = _extract_account_id(case_file)
    if ext_user_id is None and isinstance(case_file, dict):
        ext_user_id = _extract_ext_user_id(case_file)
        account_id = _extract_account_id(case_file)
    if account_id is None and ext_user_id is not None:
        account_id = ext_user_id

    if not account_id:
        return None, (
            "Actuator command missing account_id. Include the originating account_id from the investigation results."
        )

    reason = payload.get("reason")
    if not isinstance(reason, str) or not reason.strip():
        reason = "Account locked due to investigation exceeding risk threshold."

    normalized: dict[str, Any] = {
        "action": "lock_account",
        "account_id": account_id,
        "reason": reason.strip(),
    }
    if ext_user_id:
        normalized["ext_user_id"] = ext_user_id
    if case_file is not None:
        normalized["case_file"] = case_file

    return normalized, None


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
    result = await _delegate_via_a2a(
        agent_label="InvestigationAgent",
        cache_key="investigation_agent",
        service_url=INVESTIGATION_AGENT_URL,
        payload_prefix="investigate_transaction:",
        payload=transaction_details,
    )
    if isinstance(result, dict) and result.get("data") is not None:
        global _latest_case_file
        _latest_case_file = result["data"]
    return result


async def delegate_to_actuator_agent(action_command: Any) -> dict[str, Any]:
    """Send a lock_account command to the ActuatorAgent via A2A.

    Expects JSON containing `action`, `account_id`, `ext_user_id` (optional), `reason`,
    and optionally `case_file`. The `account_id` field is required by the GenAI toolbox.
    """
    logger.info("Delegating to ActuatorAgent with command payload.")
    normalized_payload, error = _prepare_actuator_payload(action_command)
    if error:
        logger.error("Actuator command validation failed: %s", error)
        return {
            "agent": "ActuatorAgent",
            "error": error,
        }
    return await _delegate_via_a2a(
        agent_label="ActuatorAgent",
        cache_key="actuator_agent",
        service_url=ACTUATOR_AGENT_URL,
        payload_prefix="execute_action:",
        payload=normalized_payload,
    )


investigation_tool = FunctionTool(delegate_to_investigation_agent)
actuator_tool = FunctionTool(delegate_to_actuator_agent)

# Create FastAPI app for A2A server functionality
app = FastAPI(title="Orchestrator Agent A2A Server")

# Global orchestrator service instance
orchestrator_service = None

class OrchestratorService:
    def __init__(self):
        logger.info("Initializing OrchestratorService...")

        if not GEMINI_API_KEY:
            raise ValueError(
                "GEMINI_API_KEY environment variable is required for the orchestrator agent."
            )

        threshold = _parse_float(RISK_SCORE_THRESHOLD)
        if threshold is None:
            logger.warning(
                "Invalid RISK_SCORE_THRESHOLD value '%s'; defaulting to 7.0",
                RISK_SCORE_THRESHOLD,
            )
            threshold = 7.0

        self.risk_threshold = threshold
        self.default_user_id = "transaction-monitor"

        instruction = ORCHESTRATOR_PROMPT_TEMPLATE.format(
            threshold=f"{self.risk_threshold:.2f}"
        )

        self.llm_agent = LlmAgent(
            name="orchestrator_agent",
            model=Gemini(api_key=GEMINI_API_KEY, model="gemini-2.5-flash"),
            instruction=instruction,
            tools=[
                investigation_tool,
                actuator_tool,
            ],
        )

        self.session_service = InMemorySessionService()
        self.runner = Runner(
            app_name="vigil_orchestrator_app",
            agent=self.llm_agent,
            session_service=self.session_service,
        )

        logger.info(
            "OrchestratorService initialized (risk threshold=%s).",
            self.risk_threshold,
        )

    async def process_transaction_alert(self, transaction_data: dict) -> dict:
        """Run the Gemini-backed orchestration flow for a transaction alert."""
        logger.info("Received transaction alert: %s", transaction_data)

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
        account_id: Optional[str] = None

        message_text = (
            "Transaction alert received.\n"
            f"Risk threshold: {self.risk_threshold:.2f}\n"
            "Analyze the details, call InvestigationAgent first, and escalate only when warranted.\n"
            "When invoking ActuatorAgent, use JSON of the form {\"action\": \"lock_account\", \"account_id\": \"...\", \"ext_user_id\": \"...\", \"reason\": \"...\"}.\n"
            "Do not use alternate field names such as 'command'.\n"
            f"Transaction JSON:\n{json.dumps(transaction_data, indent=2)}"
        )
        message_content = types.Content(
            role="user",
            parts=[types.Part(text=message_text)],
        )

        try:
            async for event in self.runner.run_async(
                user_id=user_id,
                session_id=session_id,
                new_message=message_content,
            ):
                for call in getattr(event, "get_function_calls", lambda: [])() or []:
                    tool_events.append(
                        {
                            "event": "call",
                            "tool": _human_tool_name(call.name),
                            "args": call.args,
                        }
                    )

                for response in getattr(event, "get_function_responses", lambda: [])() or []:
                    tool_events.append(
                        {
                            "event": "response",
                            "tool": _human_tool_name(response.name),
                            "response": response.response,
                        }
                    )

                if getattr(event, "content", None) and getattr(event.content, "parts", None):
                    text_segments = []
                    for part in event.content.parts:
                        if getattr(part, "text", None):
                            text_segments.append(part.text.strip())
                    if text_segments:
                        last_text = "\n".join(filter(None, text_segments))

                if getattr(event, "is_final_response", None) and event.is_final_response():
                    final_text = last_text

        except Exception as exc:  # pragma: no cover - defensive logging
            logger.error(
                "An error occurred during the orchestration flow: %s",
                exc,
                exc_info=True,
            )
            return {
                "status": "error",
                "summary": str(exc),
                "session_id": session_id,
                "user_id": user_id,
                "tool_events": tool_events,
            }

        summary = final_text or last_text or "No summary produced by orchestrator."

        investigation_result = _extract_tool_response(tool_events, "InvestigationAgent")
        actuator_result = _extract_tool_response(tool_events, "ActuatorAgent")

        case_file = None
        if isinstance(investigation_result, dict):
            case_file = investigation_result.get("data")

        risk_score = _extract_risk_score(case_file)
        justification = _extract_justification(case_file)
        ext_user_id = _extract_ext_user_id(case_file)
        if account_id is None:
            account_id = _extract_account_id(case_file)

        should_actuate = False
        if isinstance(actuator_result, dict):
            should_actuate = not actuator_result.get("error")

        if justification and justification not in summary:
            summary = f"{summary}\nJustification: {justification}"

        if risk_score is not None:
            threshold_met = risk_score >= self.risk_threshold
            if threshold_met and not should_actuate:
                logger.warning(
                    "Risk score %.2f meets threshold %.2f but no actuation was recorded.",
                    risk_score,
                    self.risk_threshold,
                )
            if should_actuate and not threshold_met:
                logger.warning(
                    "Actuation executed even though risk score %.2f is below threshold %.2f.",
                    risk_score,
                    self.risk_threshold,
                )

        logger.info(
            "Orchestration completed for session %s (user %s). should_actuate=%s",
            session_id,
            user_id,
            should_actuate,
        )

        response_payload: dict[str, Any] = {
            "status": "completed",
            "summary": summary,
            "session_id": session_id,
            "user_id": user_id,
            "risk_threshold": self.risk_threshold,
            "tool_events": tool_events,
        }

        if risk_score is not None:
            response_payload["risk_score"] = risk_score
        if justification:
            response_payload["justification"] = justification
        if account_id:
            response_payload["account_id"] = account_id
        if ext_user_id:
            response_payload["ext_user_id"] = ext_user_id
        if investigation_result is not None:
            response_payload["investigation_result"] = investigation_result
        if actuator_result is not None:
            response_payload["actuator_result"] = actuator_result
        response_payload["should_actuate"] = should_actuate

        return response_payload


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
