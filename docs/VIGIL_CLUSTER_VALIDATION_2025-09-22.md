# Vigil System Cluster Validation (2025-09-22)

## Environment
- **Cluster**: `gke_vigil-demo-hackathon_southamerica-east1_gke-vigil`
- **Namespace**: `default`
- **Agents Running**: investigation, critic, orchestrator, actuator, transaction monitor, genai-toolbox, Bank of Anthos services
- **Load**: Continuous via `loadgenerator`
- **Observability commands**: `kubectl get pods`, `kubectl logs`, `kubectl top pods`, in-cluster smoke tests via `kubectl exec`

## Findings

### 1. Transaction Monitor ↔️ Orchestrator Flow
- Command: `kubectl logs transaction-monitor-agent-5c9dddc69d-l22jz --since=10m`.
- Observation: 85 "Successfully sent alert" entries vs 325 "Failed to alert orchestrator" timeouts in the last 10 minutes.
- Cause: bursts of 10+ concurrent high-value alerts exceed the default JSON-RPC timeout (5s); orchestrator often returns after multi-hop LLM calls.
- Mitigation: extend A2A client timeout / enable connection pooling, or scale orchestrator (deferred due to Autopilot resource pressure).

### 2. Manual Orchestrator A2A Validation
- Command: `kubectl exec -i transaction-monitor-agent-... -- python` (sending `method="message/send"`).
- Result: HTTP 200 payload with full `tool_events`, confirming the Runner instrumentation works (`session_id 6741b714-aba1-4d99-8ce0-55e828dec105`).
- Insight: Response shows CriticAgent failure cascades block actuator hand-off (see next finding).

### 3. Critic Agent Regression
- Logs: `kubectl logs critic-agent-6db744bc8-qdq9k`.
- Error: `AttributeError: 'LlmAgent' object has no attribute 'send'` on every critique call.
- Impact: orchestrator summaries report "CriticAgent failed"; no actuator actions executed for high-risk cases.
- Action: deploy Runner-based critic service (mirroring orchestrator/investigation updates).

### 4. GenAI Toolbox Data Errors
- Logs: `kubectl logs investigation-agent-...` and `kubectl logs genal-toolbox-service-...`.
- Error: `ERROR: relation "accounts" does not exist` for `get_user_details_by_account` endpoint.
- Impact: investigation agent runs without user metadata, raising risk scores unnecessarily.
- Action: restore/seed `accounts` table or point toolbox at the correct database.

### 5. Resource Pressure
- `kubectl top pods` shows `userservice` at ~400m CPU, orchestrator at ~68m/360Mi.
- Attempted scratch pod (`kubectl run orchestrator-smoke ...`) failed scheduling: "Insufficient cpu" & "Too many pods".
- Decision: skip additional replicas/tests outside existing workloads until resources increase.

## Next Actions (agreed)
1. **Critic Agent Refactor** – Redeploy the Runner-based implementation to eliminate `llm_agent.send` and unblock actuator hand-offs.
2. **Increase Transaction Monitor A2A Timeout** – Raise the HTTP client timeout (e.g., 30s) and confirm timeout count drops under load.
3. **Fix GenAI Toolbox Schema** – Ensure `get_user_details_by_account` returns data; re-run synthetic alert once fixed.
4. *(Deferred)* Orchestrator scaling/HPA adjustments omitted due to Autopilot utilization constraints.

## Command Appendix
```
kubectl get pods
kubectl logs orchestrator-agent-677cd5cd58-27j8q --since=5m
kubectl logs transaction-monitor-agent-5c9dddc69d-l22jz --since=10m
kubectl logs investigation-agent-8c4c554f4-9qrfn --since=5m
kubectl logs genal-toolbox-service-676bb9ff48-7f6hc --since=5m
kubectl exec -i transaction-monitor-agent-... -- python - <<'PY' ...
kubectl top pods
```
