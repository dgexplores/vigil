#!/bin/bash
# Build script for Observer Agent with Stdio MCP Support

set -e

echo "============================================"
echo "Building Vigil Observer Agent with Stdio MCP"
echo "============================================"

# Navigate to the vigil-system directory
cd "$(dirname "$0")"

# Check if required files exist
echo "Checking required files..."
required_files=(
    "observer-agent/agent.py"
    "observer-agent/mcp_stdio_client.py"
    "observer-agent/Dockerfile.stdio"
    "mcp-server/vigil_mcp_server.py"
    "mcp-server/vigil_mcp_stdio_server.py"
)

for file in "${required_files[@]}"; do
    if [ ! -f "$file" ]; then
        echo "❌ Missing required file: $file"
        exit 1
    fi
done
echo "✅ All required files present"

# Build the Docker image from the vigil-system directory
echo ""
echo "Building Docker image..."
docker build \
    -f observer-agent/Dockerfile.stdio \
    -t vigil-observer-stdio:latest \
    .

echo ""
echo "✅ Build complete!"
echo ""
echo "To test the image locally:"
echo "  docker run --rm -it vigil-observer-stdio:latest python test_stdio_integration.py"
echo ""
echo "To push to GCR:"
echo "  docker tag vigil-observer-stdio:latest gcr.io/vigil-demo-hackathon/vigil-observer-stdio:latest"
echo "  docker push gcr.io/vigil-demo-hackathon/vigil-observer-stdio:latest"