# Vigil System Change Log

## 2025-09-22

- **Orchestrator Agent**
  - Added robust sanitizer for LLM actuator payloads to extract valid JSON from Markdown/code-fenced or prose responses.
  - Implemented deterministic fallback: if investigation risk ≥ threshold and no Actuator call succeeded, synthesize and send a `lock_account` command through A2A.
  - Updated deployment to image `orchestrator-agent:v20250922-g30` after applying fixes.

- **Transaction Monitor Agent**
  - Disabled simulated high-value transactions to avoid synthetic alerts in shared environments.
  - Raised `POLL_INTERVAL` from 5s to 30s to reduce load and associated API costs.
  - Rebuilt and redeployed image `transaction-monitor-agent:v20250922-g03` reflecting these adjustments.

- **Actuator Agent**
  - Enhanced account ID extraction and toolbox invocation logging to support fallback operations (fetched via redeployed image `actuator-agent:v20250922-g05`).

- **Testing Notes**
  - Verified end-to-end flow by inserting high-value transactions directly into the ledger database; fallback path triggered successfully, locking mock user accounts via the GenAI toolbox.
  - Observed limitation: Bank of Anthos demo does not honor the `ACCOUNT_LOCKED_BY_VIGIL` flag, so transactions remain possible even after lock—documented as expected hackathon scope.
