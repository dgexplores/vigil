# 🚀 Warp Terminal Native MCP Integration Setup

## 🎯 Overview
This guide configures Warp Terminal's native MCP functionality to connect directly to your Vigil MCP server, giving you seamless access to Bank of Anthos fraud detection tools.

## ✅ Prerequisites Complete
- ✅ Vigil MCP server running in GKE
- ✅ Local MCP wrapper script created (`vigil-mcp-local.py`)
- ✅ Dependencies installed in virtual environment
- ✅ Port forwarding configured

## 🛠️ Step-by-Step Warp Integration

### Step 1: Locate Warp MCP Configuration Directory

Warp typically stores MCP configurations in one of these locations:
```bash
~/.config/warp/mcp/
~/.warp/mcp/
~/Library/Application Support/dev.warp.Warp-Stable/mcp/  # macOS
```

Create the directory if it doesn't exist:
```bash
mkdir -p ~/.config/warp/mcp/
```

### Step 2: Copy MCP Configuration

Copy your MCP configuration to Warp's config directory:
```bash
cp mcp_config.json ~/.config/warp/mcp/vigil-bank-anthos.json
```

### Step 3: Restart Warp Terminal

Restart Warp to load the new MCP configuration.

### Step 4: Verify MCP Connection in Warp

In Warp, you should now be able to:

1. **Access MCP Tools via AI Chat:**
   ```
   @vigil-bank-anthos get transactions for account 1234567890
   ```

2. **Use MCP Commands directly:**
   ```
   /mcp vigil-bank-anthos get_transactions account_id=1234567890
   ```

3. **Browse available tools:**
   ```
   /mcp vigil-bank-anthos --help
   ```

## 🔧 Available MCP Tools

| Tool | Description | Example Usage |
|------|-------------|---------------|
| `get_transactions` | Get account transaction history | `account_id=1234567890` |
| `get_user_details` | Get user information | `user_id=user123` |
| `lock_account` | Lock user account (fraud mitigation) | `user_id=user123 reason="Suspected fraud"` |
| `authenticate_user` | Authenticate user credentials | `username=alice password=secret` |
| `submit_transaction` | Submit new transaction | `from_account=1111 to_account=2222 amount=10000 routing_number=123456` |

## 🚀 Advanced Usage Examples

### 1. Fraud Investigation Workflow
```
# In Warp AI chat:
@vigil-bank-anthos I need to investigate suspicious activity on account 1234567890. 
Please get the transaction history and user details.

# Or via direct commands:
/mcp vigil-bank-anthos get_transactions account_id=1234567890
/mcp vigil-bank-anthos get_user_details user_id=1234
```

### 2. Real-time Fraud Response
```
# Lock suspicious account immediately:
@vigil-bank-anthos Lock user account 1234 due to "High-risk transaction pattern detected"

# Or direct:
/mcp vigil-bank-anthos lock_account user_id=1234 reason="High-risk transaction pattern detected"
```

### 3. Testing Fraud Scenarios
```
# Generate test transactions:
@vigil-bank-anthos Submit a large transaction from account 1111222233 to 5555666677 for $500.00

# Monitor the result:
@vigil-bank-anthos Check recent transactions for account 1111222233
```

## 🎯 Integration Benefits

### **Native Warp AI Integration**
- Natural language fraud investigation
- Contextual banking data access
- AI-assisted fraud pattern detection

### **Enhanced Workflow**
- Type queries in plain English
- Get structured banking data
- Take immediate fraud mitigation actions

### **Professional Demo Capability**
- Show judges live fraud detection
- Demonstrate AI-powered investigation
- Real-time system interaction

## 🔧 Troubleshooting

### MCP Server Not Found
```bash
# Ensure port-forwards are running:
kubectl port-forward svc/frontend 8080:80 &
kubectl port-forward svc/mcp-server 8000:8000 &

# Test local wrapper:
python3 vigil-mcp-local.py --help
```

### Tools Not Available
```bash
# Check MCP server status:
vigil_health  # Using our custom functions

# Restart Warp Terminal
# Verify config file location
```

### Connection Issues
```bash
# Verify Bank of Anthos connectivity:
curl -s http://localhost:8080/health

# Check MCP server logs in cluster:
kubectl logs deployment/mcp-server -f
```

## 🎨 Demo Script for Judges

```
# Show in Warp AI chat:
"I need to demonstrate our fraud detection system. Let me investigate account 1234567890"

@vigil-bank-anthos Get transaction history for account 1234567890

"Now let me check the user details to assess risk"

@vigil-bank-anthos Get user details for user 1234

"Based on the pattern, I'm going to lock this account as a precaution"

@vigil-bank-anthos Lock account 1234 due to "Demo - suspicious transaction pattern"

"Our Observer agent will now see this locked account and update its fraud detection models accordingly"
```

## 🚨 Keep Running

For the MCP integration to work, ensure these remain active:

```bash
# Port forwards:
kubectl port-forward svc/frontend 8080:80 &
kubectl port-forward svc/mcp-server 8000:8000 &

# Verify services:
kubectl get pods -l component=vigil
```

## 🎉 Success!

Your Warp Terminal now has **native MCP integration** with your Vigil fraud detection system! You can:

- ✅ Investigate fraud using natural language
- ✅ Access real Bank of Anthos data through AI chat  
- ✅ Take immediate fraud mitigation actions
- ✅ Create impressive demos for judges
- ✅ Develop faster with context-aware assistance

Type `@vigil-bank-anthos` in Warp AI chat to start investigating! 🕵️‍♂️