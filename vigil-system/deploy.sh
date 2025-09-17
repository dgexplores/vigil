#!/bin/bash

# Deployment script for Vigil System
set -euo pipefail

echo "Deploying Vigil System to Kubernetes..."

# Create namespace first
echo "Creating vigil-system namespace..."
kubectl apply -f kubernetes-manifests/namespace.yaml

# Wait a moment for namespace to be created
sleep 2

# Apply all manifests
echo "Deploying MCP Server..."
kubectl apply -f kubernetes-manifests/mcp-server.yaml

# Wait for deployment to be ready
echo "Waiting for MCP Server to be ready..."
kubectl wait --for=condition=available --timeout=300s deployment/mcp-server -n vigil-system

# Check status
echo "Deployment status:"
kubectl get all -n vigil-system

# Show service endpoint
echo ""
echo "MCP Server service:"
kubectl get service mcp-server -n vigil-system

# Check logs
echo ""
echo "Recent logs from MCP Server:"
kubectl logs -l app=mcp-server -n vigil-system --tail=20

echo ""
echo "Vigil System deployed successfully!"
echo "MCP Server is running at: mcp-server.vigil-system.svc.cluster.local:8000"