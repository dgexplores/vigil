#!/bin/bash

# Vigil Agent System - Build and Deployment Script
# This script builds the observer agent container and MCP server, then deploys them to GKE

set -e  # Exit on any error

# Configuration
PROJECT_ID="${PROJECT_ID:-your-gcp-project-id}"
REGION="${REGION:-us-central1}"
CLUSTER_NAME="${CLUSTER_NAME:-gke-vigil-cluster}"
REGISTRY="${REGISTRY:-gcr.io/$PROJECT_ID}"

# Image tags
TAG="${TAG:-latest}"
OBSERVER_IMAGE="$REGISTRY/vigil-observer:$TAG"
MCP_SERVER_IMAGE="$REGISTRY/vigil-mcp-server:$TAG"

echo "🚀 Vigil Agent System Deployment"
echo "================================="
echo "Project ID: $PROJECT_ID"
echo "Region: $REGION"
echo "Cluster: $CLUSTER_NAME"
echo "Registry: $REGISTRY"
echo "Tag: $TAG"
echo ""

# Function to print section headers
print_section() {
    echo ""
    echo "📋 $1"
    echo "$(printf '=%.0s' {1..50})"
}

# Function to check prerequisites
check_prerequisites() {
    print_section "Checking Prerequisites"
    
    # Check if required commands exist
    commands=("docker" "kubectl" "gcloud")
    for cmd in "${commands[@]}"; do
        if ! command -v $cmd &> /dev/null; then
            echo "❌ $cmd is required but not installed"
            exit 1
        else
            echo "✅ $cmd is available"
        fi
    done
    
    # Check if logged into gcloud
    if ! gcloud auth list --filter=status:ACTIVE --format="value(account)" | grep -q .; then
        echo "❌ Please login to gcloud: gcloud auth login"
        exit 1
    else
        echo "✅ Google Cloud authenticated"
    fi
    
    # Check if Docker is running
    if ! docker info &> /dev/null; then
        echo "❌ Docker is not running"
        exit 1
    else
        echo "✅ Docker is running"
    fi
}

# Function to build Docker images
build_images() {
    print_section "Building Docker Images"
    
    # Ensure we're in the right directory
    if [[ ! -d "observer-agent" || ! -d "mcp-server" ]]; then
        echo "❌ Required directories not found. Make sure you're in the vigil-system directory."
        exit 1
    fi
    
    # Build Observer Agent  
    echo "🔨 Building Observer Agent..."
    cd observer-agent
    docker build -t $OBSERVER_IMAGE .
    echo "✅ Observer Agent built successfully"
    cd ..
    
    # Build MCP Server
    echo "🔨 Building MCP Server..."
    cd mcp-server
    docker build -t $MCP_SERVER_IMAGE .
    echo "✅ MCP Server built successfully"
    cd ..
}

# Function to push images to registry
push_images() {
    print_section "Pushing Images to Registry"
    
    # Configure Docker to use gcloud as credential helper
    gcloud auth configure-docker --quiet
    
    echo "📤 Pushing Observer Agent..."
    docker push $OBSERVER_IMAGE
    echo "✅ Observer Agent pushed"
    
    echo "📤 Pushing MCP Server..."
    docker push $MCP_SERVER_IMAGE
    echo "✅ MCP Server pushed"
}

# Function to set up GKE cluster (if needed)
setup_cluster() {
    print_section "Setting up GKE Cluster"
    
    # Check if cluster exists
    if gcloud container clusters describe $CLUSTER_NAME --region=$REGION --project=$PROJECT_ID &> /dev/null; then
        echo "✅ Cluster $CLUSTER_NAME already exists"
        
        # Get credentials
        echo "🔑 Getting cluster credentials..."
        gcloud container clusters get-credentials $CLUSTER_NAME --region=$REGION --project=$PROJECT_ID
    else
        echo "🆕 Creating new GKE cluster..."
        gcloud container clusters create $CLUSTER_NAME \
            --project=$PROJECT_ID \
            --region=$REGION \
            --num-nodes=3 \
            --enable-autoscaling \
            --min-nodes=1 \
            --max-nodes=10 \
            --machine-type=e2-standard-4 \
            --disk-size=50GB \
            --enable-autorepair \
            --enable-autoupgrade \
            --enable-ip-alias \
            --network=default \
            --subnetwork=default
        
        echo "✅ Cluster created successfully"
        
        # Get credentials
        echo "🔑 Getting cluster credentials..."
        gcloud container clusters get-credentials $CLUSTER_NAME --region=$REGION --project=$PROJECT_ID
    fi
}

# Function to deploy to Kubernetes
deploy_to_k8s() {
    print_section "Deploying to Kubernetes"
    
    # Update image references in deployment files
    echo "🔄 Updating image references in deployment manifests..."
    
    # Create temporary deployment files with correct image names
    sed "s|vigil/observer-agent:latest|$OBSERVER_IMAGE|g" k8s/observer-deployment.yaml > k8s/observer-deployment-temp.yaml
    sed "s|vigil/mcp-server:latest|$MCP_SERVER_IMAGE|g" kubernetes-manifests/mcp-server.yaml > kubernetes-manifests/mcp-server-temp.yaml
    
    # Deploy configuration to default namespace
    echo "🔧 Deploying configuration to default namespace..."
    kubectl apply -f k8s/namespace-and-config.yaml
    
    # Deploy the observer agent and MCP server
    echo "🚀 Deploying Vigil components..."
    kubectl apply -f k8s/observer-deployment-temp.yaml
    kubectl apply -f kubernetes-manifests/mcp-server-temp.yaml
    
    # Clean up temporary files
    rm -f k8s/*-temp.yaml kubernetes-manifests/*-temp.yaml
    
    echo "✅ Deployment manifests applied"
}

# Function to wait for deployment and verify
verify_deployment() {
    print_section "Verifying Deployment"
    
    echo "⏳ Waiting for deployments to be ready..."
    
    # Wait for deployments
    kubectl wait --for=condition=available --timeout=300s deployment/vigil-observer
    kubectl wait --for=condition=available --timeout=300s deployment/mcp-server
    
    echo "✅ All deployments are ready"
    
    # Show deployment status
    echo ""
    echo "📊 Deployment Status:"
    kubectl get deployments
    
    echo ""
    echo "🏃 Running Pods:"
    kubectl get pods
    
    echo ""
    echo "🔗 Services:"
    kubectl get services
}

# Function to show useful information
show_info() {
    print_section "Deployment Information"
    
    echo "🎉 Vigil Agent System deployed successfully!"
    echo ""
    echo "🔍 To monitor the system:"
    echo "  kubectl get pods -w"
    echo ""
    echo "📋 To view logs:"
    echo "  kubectl logs -f deployment/vigil-observer"  
    echo "  kubectl logs -f deployment/mcp-server"
    echo ""
    echo "🔧 To update configuration:"
    echo "  kubectl edit configmap vigil-config"
    echo ""
    echo "🗑️  To clean up:"
    echo "  kubectl delete deployment vigil-observer mcp-server"
    echo "  kubectl delete service vigil-observer mcp-server"
    echo "  kubectl delete configmap vigil-config"
    echo "  kubectl delete secret vigil-secrets"
    echo ""
    
    # Show external IP if LoadBalancer services exist
    external_ips=$(kubectl get services -o jsonpath='{.items[*].status.loadBalancer.ingress[0].ip}' 2>/dev/null || echo "")
    if [[ ! -z "$external_ips" && "$external_ips" != "null" ]]; then
        echo "🌐 External IPs: $external_ips"
        echo ""
    fi
    
    echo "📚 System Architecture:"
    echo "  Observer Agent (Port 8000) → monitors Bank of Anthos transactions"
    echo "  MCP Server (Port 8001) → provides MCP protocol interface for agent communication"
    echo ""
    echo "🔄 Communication Flow:"
    echo "  Observer → MCP Server → External MCP Clients (via port forwarding)"
}

# Main execution flow
main() {
    # Parse command line arguments
    case "${1:-all}" in
        "build")
            check_prerequisites
            build_images
            ;;
        "push")
            check_prerequisites
            push_images
            ;;
        "deploy")
            check_prerequisites
            setup_cluster
            deploy_to_k8s
            verify_deployment
            show_info
            ;;
        "all")
            check_prerequisites
            build_images
            push_images
            setup_cluster
            deploy_to_k8s
            verify_deployment
            show_info
            ;;
        "clean")
            print_section "Cleaning up Vigil system"
            kubectl delete deployment vigil-observer mcp-server --ignore-not-found=true
            kubectl delete service vigil-observer mcp-server --ignore-not-found=true
            kubectl delete configmap vigil-config --ignore-not-found=true
            kubectl delete secret vigil-secrets --ignore-not-found=true
            echo "✅ Vigil system cleaned up"
            ;;
        *)
            echo "Usage: $0 [build|push|deploy|all|clean]"
            echo ""
            echo "Commands:"
            echo "  build  - Build Docker images only"
            echo "  push   - Push images to registry only"  
            echo "  deploy - Deploy to GKE only"
            echo "  all    - Build, push, and deploy (default)"
            echo "  clean  - Remove Vigil system from cluster"
            exit 1
            ;;
    esac
}

# Run main function with all arguments
main "$@"

# Deployment script for Vigil System
set -euo pipefail

echo "Deploying Vigil System to Kubernetes..."

# Deploy to default namespace
echo "Deploying to default namespace..."

# Apply all manifests
echo "Deploying MCP Server..."
kubectl apply -f kubernetes-manifests/mcp-server.yaml

# Wait for deployment to be ready
echo "Waiting for MCP Server to be ready..."
kubectl wait --for=condition=available --timeout=300s deployment/mcp-server

# Check status
echo "Deployment status:"
kubectl get all

# Show service endpoint
echo ""
echo "MCP Server service:"
kubectl get service mcp-server

# Check logs
echo ""
echo "Recent logs from MCP Server:"
kubectl logs -l app=mcp-server --tail=20

echo ""
echo "Vigil System deployed successfully!"
echo "MCP Server is running at: mcp-server.default.svc.cluster.local:8000"
