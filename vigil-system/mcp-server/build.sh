#!/bin/bash

# Build script for Vigil MCP Server
set -euo pipefail

# Configuration
PROJECT_ID=${PROJECT_ID:-"your-project-id"}
IMAGE_NAME="vigil-mcp-server"
TAG=${TAG:-"latest"}
FULL_IMAGE_NAME="gcr.io/${PROJECT_ID}/${IMAGE_NAME}:${TAG}"

echo "Building Vigil MCP Server Docker image..."
echo "Project ID: $PROJECT_ID"
echo "Image: $FULL_IMAGE_NAME"

# Build the Docker image
docker build -t "$FULL_IMAGE_NAME" .

# Push to Google Container Registry
echo "Pushing image to GCR..."
docker push "$FULL_IMAGE_NAME"

echo "Build and push completed successfully!"
echo "Image: $FULL_IMAGE_NAME"

# Update the Kubernetes manifest with the new image
echo "Updating Kubernetes manifest..."
sed -i "s|gcr.io/your-project-id/vigil-mcp-server:latest|${FULL_IMAGE_NAME}|g" ../kubernetes-manifests/mcp-server.yaml

echo "Done! You can now deploy using:"
echo "kubectl apply -f ../kubernetes-manifests/"