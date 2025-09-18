# Vigil MCP Server - Available Tools

This document lists all available tools in the Vigil MCP Server for use with tool filtering in ADK agents.

## Complete Tool List

| Tool Name | Description | Use Case | Risk Level |
|-----------|-------------|----------|------------|
| `get_transactions` | Retrieve transaction history for an account | Fraud analysis, account monitoring | Low |
| `submit_transaction` | Submit new transactions to the banking system | Transaction processing | **HIGH** |
| `get_user_details` | Get detailed user information | User verification, account info | Medium |
| `lock_account` | Lock user account to prevent transactions | Fraud mitigation | **HIGH** |
| `authenticate_user` | Authenticate users and get JWT tokens | User authentication | Medium |

## ADK Tool Filtering Examples

### Conservative Filter (Read-Only Operations)
```python
tool_filter=['get_transactions', 'get_user_details']
```
Best for: Analysis agents, monitoring systems, reporting tools

### Fraud Detection Filter
```python
tool_filter=['get_transactions', 'get_user_details', 'lock_account']
```
Best for: Fraud detection agents that can block suspicious accounts

### Full Banking Operations
```python
# No tool_filter specified = all tools available
```
Best for: Administrative agents, customer service systems
**⚠️ HIGH RISK - Use only in secure environments**

### Custom Authentication Filter
```python
tool_filter=['authenticate_user', 'get_user_details']
```
Best for: Authentication services, user management systems

## Tool Usage Patterns

### Pattern 1: Fraud Detection Agent
```python
MCPToolset(
    connection_params=StdioConnectionParams(...),
    tool_filter=['get_transactions', 'get_user_details', 'lock_account']
)
```

### Pattern 2: Transaction Analysis Agent  
```python
MCPToolset(
    connection_params=StdioConnectionParams(...),
    tool_filter=['get_transactions', 'get_user_details']
)
```

### Pattern 3: Customer Service Agent
```python
MCPToolset(
    connection_params=StdioConnectionParams(...),
    tool_filter=['get_user_details', 'authenticate_user']
)
```

## Security Considerations

### High-Risk Tools
- `submit_transaction`: Can create financial transactions
- `lock_account`: Can prevent users from accessing their accounts

### Recommended Practices
1. **Always use tool filtering** in production environments
2. **Log all tool usage** for audit trails
3. **Implement additional authorization** for high-risk tools
4. **Test with limited tool sets** during development

## Tool Input Schemas

### get_transactions
```json
{
  "account_id": "string (required)"
}
```

### submit_transaction
```json
{
  "from_account": "string (required)",
  "to_account": "string (required)", 
  "amount": "integer (required, in cents)",
  "routing_number": "string (required)"
}
```

### get_user_details
```json
{
  "user_id": "string (required)"
}
```

### lock_account
```json
{
  "user_id": "string (required)",
  "reason": "string (required)"
}
```

### authenticate_user
```json
{
  "username": "string (required)",
  "password": "string (required)"
}
```

## Environment-Specific Configurations

### Development Environment
```python
# All tools available for testing
tool_filter=None  # or omit tool_filter parameter
```

### Staging Environment
```python
# Limited to read operations and account locking
tool_filter=['get_transactions', 'get_user_details', 'lock_account']
```

### Production Environment
```python
# Minimal tools based on specific agent role
tool_filter=['get_transactions', 'get_user_details']
```