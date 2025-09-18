#!/bin/bash

# Vigil Setup Script
# Quick setup for the Vigil fraud detection system

set -e

echo "🛡️ Vigil Setup Script"
echo "====================="
echo ""

# Function to print colored output
print_info() { echo -e "\033[0;36m$1\033[0m"; }
print_success() { echo -e "\033[0;32m✓ $1\033[0m"; }
print_error() { echo -e "\033[0;31m✗ $1\033[0m"; }

# Check prerequisites
print_info "Checking prerequisites..."

if ! command -v kubectl &> /dev/null; then
    print_error "kubectl not found. Please install kubectl."
    exit 1
fi
print_success "kubectl found"

if ! command -v gcloud &> /dev/null; then
    print_error "gcloud not found. Please install Google Cloud SDK."
    exit 1
fi
print_success "gcloud found"

if ! command -v python3 &> /dev/null; then
    print_error "python3 not found. Please install Python 3.8+."
    exit 1
fi
print_success "python3 found"

# Check if we're in the right directory
if [ ! -f "README.md" ] || [ ! -d "vigil-system" ]; then
    print_error "Please run this script from the project root directory"
    exit 1
fi

# Option to set up port forwarding
echo ""
print_info "Do you want to set up port forwarding for Bank of Anthos services? (y/n)"
read -r SETUP_PF

if [ "$SETUP_PF" = "y" ]; then
    print_info "Setting up port forwarding..."
    
    # Kill existing port-forwards
    pkill -f "kubectl port-forward" 2>/dev/null || true
    
    # Start port forwarding in background
    kubectl port-forward svc/userservice 8081:8080 > /dev/null 2>&1 &
    print_success "Userservice forwarding to localhost:8081"
    
    kubectl port-forward svc/transactionhistory 8082:8080 > /dev/null 2>&1 &
    print_success "Transaction History forwarding to localhost:8082"
    
    kubectl port-forward svc/ledgerwriter 8083:8080 > /dev/null 2>&1 &
    print_success "Ledger Writer forwarding to localhost:8083"
    
    echo ""
    print_info "Port forwarding established. PIDs:"
    jobs -l | grep kubectl
fi

# Option to set up MCP server environment
echo ""
print_info "Do you want to set up the MCP server Python environment? (y/n)"
read -r SETUP_MCP

if [ "$SETUP_MCP" = "y" ]; then
    print_info "Setting up MCP server environment..."
    
    cd vigil-system/mcp-server
    
    # Create virtual environment if it doesn't exist
    if [ ! -d "venv" ]; then
        python3 -m venv venv
        print_success "Virtual environment created"
    else
        print_info "Virtual environment already exists"
    fi
    
    # Activate and install dependencies
    source venv/bin/activate
    pip install -q --upgrade pip
    pip install -q -r requirements.txt
    print_success "Dependencies installed"
    
    cd ../..
fi

# Check cluster connection
echo ""
print_info "Checking Kubernetes cluster connection..."
if kubectl cluster-info &> /dev/null; then
    CONTEXT=$(kubectl config current-context)
    print_success "Connected to cluster: $CONTEXT"
else
    print_error "Not connected to a Kubernetes cluster"
    print_info "Please run: gcloud container clusters get-credentials <cluster-name> --region=<region>"
fi

# Check if Bank of Anthos is deployed
echo ""
print_info "Checking Bank of Anthos deployment..."
if kubectl get service frontend &> /dev/null; then
    print_success "Bank of Anthos is deployed"
else
    print_error "Bank of Anthos not found"
    print_info "Deploy with: kubectl apply -f bank-of-anthos/kubernetes-manifests"
fi

# Check if Vigil agents are deployed
echo ""
print_info "Checking Vigil agents deployment..."
AGENTS_FOUND=true
for agent in observer analyst actuator; do
    if kubectl get deployment vigil-$agent &> /dev/null; then
        print_success "vigil-$agent is deployed"
    else
        print_error "vigil-$agent not found"
        AGENTS_FOUND=false
    fi
done

if [ "$AGENTS_FOUND" = false ]; then
    print_info "Deploy Vigil with: cd vigil-system && ./deploy.sh all"
fi

echo ""
echo "================================"
print_success "Setup check complete!"
echo ""
echo "Next steps:"
echo "1. Ensure Bank of Anthos and Vigil are deployed"
echo "2. Set up port forwarding (if not done)"
echo "3. Configure Warp Terminal with config/vigil-warp-mcp-config.json"
echo "4. Test with: MCP get_transactions tool for account 1033623433 (Alice)"
echo ""
echo "For more information, see README.md"