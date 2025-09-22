# Vigil AI Fraud Shield: Developer's Guide

This document provides technical details, troubleshooting tips, and other useful information for developers working on the Vigil AI Fraud Shield project.

## Developer Notes

This section contains key learnings and best practices for working with the project's technology stack.

### Google ADK and A2A Protocol

*   **A2A is a separate protocol:** The Agent2Agent (A2A) protocol is not part of the Google ADK. It is a separate package (`a2a-sdk`) and should be imported accordingly.
*   **Use the ClientFactory:** The modern A2A API uses `ClientFactory.create_client_with_jsonrpc_transport()` to create clients. The legacy `A2AClient` constructor is deprecated.
*   **LlmAgent requires a name:** The `LlmAgent` constructor requires a `name` field, which must be a valid Python identifier (e.g., "orchestrator_agent").
*   **FunctionTool is minimal:** The `FunctionTool` constructor only accepts the function as an argument. It does not take `name` or `description` parameters.
*   **No decorators:** The current version of the ADK does not use `@tool` or `@rpc` decorators.

### FastAPI-based Architecture

*   The agents have been refactored to use a FastAPI-based architecture for handling A2A communication. This provides a more robust and modern approach than the legacy ADK RPC server.
*   The standard port for the FastAPI servers is `8000`.
*   A `/health` endpoint is available on each agent for Kubernetes readiness and liveness probes.

### Docker Best Practices

*   **Specify file paths:** When building Docker images from the root of the repository, be sure to specify the full path to the files you want to copy (e.g., `COPY vigil-system/orchestrator_agent/agent.py /app/`). Do not rely on copying the entire directory (`COPY . /app/`).
*   **Build context matters:** Always be aware of the build context when running `docker build` commands to ensure that the Dockerfile can find all the necessary files.

## Troubleshooting Guide

This section provides solutions to common issues that you may encounter when working with the Vigil System.

### `CrashLoopBackOff` in Orchestrator Agent

*   **Symptom:** The orchestrator agent pod is in a `CrashLoopBackOff` state with the error `ModuleNotFoundError: No module named 'google.adk.rpc'`.
*   **Cause:** This is due to incorrect A2A protocol imports and outdated ADK API usage.
*   **Solution:**
    1.  Ensure that the `a2a-sdk` package is included in `requirements.txt`.
    2.  Update the code to import from `a2a.client` instead of `google.adk.rpc`.
    3.  Update the code to use the modern ADK and A2A APIs as described in the "Developer Notes" section.

### Database Connection Errors

*   **Symptom:** The `genai-toolbox` service fails to connect to the Bank of Anthos databases with errors like `password authentication failed`.
*   **Cause:** Incorrect database credentials or database names in the `tools.yaml` configuration file.
*   **Solution:** Verify that the `user`, `password`, and `database` fields in `tools.yaml` match the actual credentials for the Bank of Anthos databases.

### Database Schema Mismatches

*   **Symptom:** SQL errors like `column "from_account_id" does not exist`.
*   **Cause:** The SQL queries in `tools.yaml` do not match the actual schema of the Bank of Anthos database.
*   **Solution:** Update the SQL queries in `tools.yaml` to use the correct column names. You can use aliases (e.g., `SELECT from_acct as from_account_id`) to map the database schema to the expected API schema.

### JSON Parsing Errors

*   **Symptom:** Errors like `'str' object has no attribute 'get'` when processing responses from the `genai-toolbox`.
*   **Cause:** The `genai-toolbox` may return JSON data as a string within a `result` field (e.g., `{"result": "[{...}]"}`).
*   **Solution:** Before processing the response, check if the data is a string. If it is, parse it using `json.loads()`.

## Known Issues and Future Improvements

This section lists the known issues in the system and potential areas for future improvement.

### Known Issues (as of 2025-09-22)

*   **A2A Timeouts:** The Transaction Monitor agent sometimes experiences timeouts when communicating with the Orchestrator agent, especially under heavy load.
*   **Risk Threshold Calibration:** With the orchestrator making direct actuation decisions, review the `RISK_SCORE_THRESHOLD` setting to balance sensitivity and false positives for your environment.
*   **GenAI Toolbox Data Errors:** The `get_user_details_by_account` tool is failing because the `accounts` table does not exist in the database it's connected to.

### Future Improvements

*   **Complete A2A Integration:** Implement full, robust A2A communication between all agents, including error handling and retry mechanisms.
*   **Enhanced Fraud Rules:** Implement more sophisticated fraud detection algorithms in the Transaction Monitor agent.
*   **Monitoring and Alerting:** Add production-grade monitoring and alerting for the entire system.
*   **Performance Optimization:** Optimize polling intervals, batch processing, and agent resource usage.
*   **Authentication and Authorization:** Add security measures to the A2A communication channels.
