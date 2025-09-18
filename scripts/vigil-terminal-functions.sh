#!/bin/bash
# Vigil MCP Server Helper Functions for Warp Terminal
# Add these to your ~/.zshrc for convenient access to the Vigil MCP server

echo "🔧 Installing Vigil MCP Helper Functions..."

# Add functions to zshrc
cat >> ~/.zshrc << 'EOF'

# ===== VIGIL MCP SERVER FUNCTIONS =====

# Health check
function vigil_health() {
    echo "🏥 Checking Vigil MCP Server health..."
    curl -s http://localhost:8080/health | jq '.' || curl -s http://localhost:8080/health
}

# Get transactions for an account
function vigil_get_transactions() {
    if [ -z "$1" ]; then
        echo "❌ Usage: vigil_get_transactions <account_id>"
        echo "   Example: vigil_get_transactions 1234567890"
        return 1
    fi
    echo "💳 Getting transactions for account: $1"
    curl -s -X POST http://localhost:8080/tools/get_transactions \
        -H "Content-Type: application/json" \
        -d "{\"account_id\":\"$1\"}" | jq '.' 2>/dev/null || echo "Response not in JSON format"
}

# Get user details
function vigil_get_user() {
    if [ -z "$1" ]; then
        echo "❌ Usage: vigil_get_user <user_id>"
        echo "   Example: vigil_get_user user123"
        return 1
    fi
    echo "👤 Getting user details for: $1"
    curl -s -X POST http://localhost:8080/tools/get_user_details \
        -H "Content-Type: application/json" \
        -d "{\"user_id\":\"$1\"}" | jq '.' 2>/dev/null || echo "Response not in JSON format"
}

# Lock a user account
function vigil_lock_account() {
    if [ -z "$1" ] || [ -z "$2" ]; then
        echo "❌ Usage: vigil_lock_account <user_id> <reason>"
        echo "   Example: vigil_lock_account user123 'Suspected fraud'"
        return 1
    fi
    echo "🔒 Locking account for user: $1"
    echo "   Reason: $2"
    curl -s -X POST http://localhost:8080/tools/lock_account \
        -H "Content-Type: application/json" \
        -d "{\"user_id\":\"$1\", \"reason\":\"$2\"}" | jq '.' 2>/dev/null || echo "Response not in JSON format"
}

# Authenticate user
function vigil_auth_user() {
    if [ -z "$1" ] || [ -z "$2" ]; then
        echo "❌ Usage: vigil_auth_user <username> <password>"
        echo "   Example: vigil_auth_user alice password123"
        return 1
    fi
    echo "🔐 Authenticating user: $1"
    curl -s -X POST http://localhost:8080/tools/authenticate_user \
        -H "Content-Type: application/json" \
        -d "{\"username\":\"$1\", \"password\":\"$2\"}" | jq '.' 2>/dev/null || echo "Response not in JSON format"
}

# Submit a new transaction
function vigil_submit_transaction() {
    if [ -z "$1" ] || [ -z "$2" ] || [ -z "$3" ] || [ -z "$4" ]; then
        echo "❌ Usage: vigil_submit_transaction <from_account> <to_account> <amount> <routing_number>"
        echo "   Example: vigil_submit_transaction 1234567890 0987654321 10000 123456789"
        return 1
    fi
    echo "💸 Submitting transaction:"
    echo "   From: $1 → To: $2"
    echo "   Amount: $3 cents"
    curl -s -X POST http://localhost:8080/tools/submit_transaction \
        -H "Content-Type: application/json" \
        -d "{\"from_account\":\"$1\", \"to_account\":\"$2\", \"amount\":$3, \"routing_number\":\"$4\"}" | jq '.' 2>/dev/null || echo "Response not in JSON format"
}

# Quick status check
function vigil_status() {
    echo "📊 Vigil System Status"
    echo "====================="
    
    # Check MCP server
    echo "🔗 MCP Server:"
    if curl -s http://localhost:8080/health > /dev/null 2>&1; then
        echo "   ✅ Connected (localhost:8080)"
        vigil_health
    else
        echo "   ❌ Not accessible"
        echo "   Run: kubectl port-forward svc/mcp-server 8080:8000"
    fi
    
    echo
    echo "🤖 Available Commands:"
    echo "   vigil_health           - Check server health"
    echo "   vigil_get_transactions - Get account transactions" 
    echo "   vigil_get_user        - Get user details"
    echo "   vigil_lock_account    - Lock user account"
    echo "   vigil_auth_user       - Authenticate user"
    echo "   vigil_submit_transaction - Submit new transaction"
    echo "   vigil_status          - Show this status"
}

# Alias for convenience
alias vigil='vigil_status'

# ===== END VIGIL FUNCTIONS =====
EOF

echo "✅ Vigil MCP functions added to ~/.zshrc"
echo
echo "🔄 To use them immediately, run: source ~/.zshrc"
echo "   Or restart your terminal"
echo
echo "📖 Available functions:"
echo "   • vigil                   - Show status and available commands"
echo "   • vigil_health           - Check MCP server health"
echo "   • vigil_get_transactions - Get transactions for an account"
echo "   • vigil_get_user         - Get user details"
echo "   • vigil_lock_account     - Lock a user account (fraud mitigation)"
echo "   • vigil_auth_user        - Authenticate a user"
echo "   • vigil_submit_transaction - Submit a new transaction"
echo
echo "🚀 Example usage:"
echo "   vigil_health"
echo "   vigil_get_transactions 1234567890"
echo "   vigil_lock_account user123 'Suspected fraud'"
echo

# Source the new functions immediately
source ~/.zshrc

echo "🎉 Ready to use! Type 'vigil' to get started."