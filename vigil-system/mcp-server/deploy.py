#!/usr/bin/env python3
"""
Deployment script for Vigil MCP Server.

Supports deploying both FastMCP and low-level implementations to various environments.
"""

import argparse
import os
import subprocess
import sys
from typing import Optional


def build_image(project_id: str, implementation: str = "fastmcp", tag: str = "latest"):
    """Build Docker image for the specified implementation."""
    print(f"Building {implementation} image...")
    
    # Select the correct main file
    if implementation == "lowlevel":
        main_file = "vigil_mcp_lowlevel.py"
        image_name = f"gcr.io/{project_id}/vigil-mcp-server-lowlevel:{tag}"
    else:
        main_file = "vigil_mcp_server.py" 
        image_name = f"gcr.io/{project_id}/vigil-mcp-server:{tag}"
    
    # Create temporary Dockerfile
    dockerfile_content = f"""FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \\
    gcc \\
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY {main_file} ./main.py

# Create non-root user for security
RUN useradd --create-home --shell /bin/bash vigil
USER vigil

# Expose the port
EXPOSE 8000

# Run the application
CMD ["python", "main.py", "--transport", "streamable-http"]
"""
    
    with open("Dockerfile.tmp", "w") as f:
        f.write(dockerfile_content)
    
    try:
        # Build image
        subprocess.run([
            "docker", "build", 
            "-f", "Dockerfile.tmp",
            "-t", image_name, 
            "."
        ], check=True)
        
        # Push image
        subprocess.run(["docker", "push", image_name], check=True)
        
        print(f"Successfully built and pushed {image_name}")
        return image_name
    
    finally:
        # Cleanup
        if os.path.exists("Dockerfile.tmp"):
            os.remove("Dockerfile.tmp")


def deploy_to_gke(project_id: str, implementation: str = "fastmcp"):
    """Deploy to Google Kubernetes Engine."""
    image_name = f"gcr.io/{project_id}/vigil-mcp-server"
    if implementation == "lowlevel":
        image_name += "-lowlevel"
    
    print(f"Deploying {implementation} implementation to GKE...")
    
    # Update manifest with correct image
    subprocess.run([
        "sed", "-i", 
        f"s|gcr.io/vigil-demo-hackathon/vigil-mcp-server:latest|{image_name}:latest|g",
        "../kubernetes-manifests/mcp-server.yaml"
    ])
    
    # Apply manifests
    subprocess.run(["kubectl", "apply", "-f", "../kubernetes-manifests/"], check=True)
    
    print("Deployment completed!")


def deploy_to_cloud_run(project_id: str, implementation: str = "fastmcp"):
    """Deploy to Cloud Run."""
    image_name = f"gcr.io/{project_id}/vigil-mcp-server"
    if implementation == "lowlevel":
        image_name += "-lowlevel"
    
    print(f"Deploying {implementation} implementation to Cloud Run...")
    
    # Update Cloud Run manifest
    subprocess.run([
        "sed", "-i",
        f"s|gcr.io/PROJECT_ID/vigil-mcp-server:latest|{image_name}:latest|g",
        "deployment/cloud-run.yaml"
    ])
    
    # Deploy to Cloud Run
    subprocess.run([
        "gcloud", "run", "services", "replace", 
        "deployment/cloud-run.yaml",
        "--region", "us-central1",
        "--project", project_id
    ], check=True)
    
    print("Cloud Run deployment completed!")


def test_deployment(endpoint: str, transport: str = "streamable-http"):
    """Test the deployed MCP server."""
    if transport == "streamable-http":
        import asyncio
        from test_mcp_compliance import test_mcp_server
        
        # Update the test to use the provided endpoint
        # This is a simplified version - in practice you'd modify the test script
        print(f"Testing MCP server at {endpoint}")
        print("Use test_mcp_compliance.py with appropriate endpoint configuration")
    else:
        print(f"Stdio testing not supported for remote endpoints")


def main():
    parser = argparse.ArgumentParser(description="Deploy Vigil MCP Server")
    parser.add_argument("--project-id", required=True, help="Google Cloud project ID")
    parser.add_argument("--implementation", choices=["fastmcp", "lowlevel"], 
                       default="fastmcp", help="MCP server implementation to deploy")
    parser.add_argument("--target", choices=["gke", "cloud-run"], 
                       default="gke", help="Deployment target")
    parser.add_argument("--build-only", action="store_true", 
                       help="Only build the image, don't deploy")
    parser.add_argument("--tag", default="latest", help="Docker image tag")
    
    args = parser.parse_args()
    
    try:
        # Build the image
        image_name = build_image(args.project_id, args.implementation, args.tag)
        
        if not args.build_only:
            # Deploy to the target
            if args.target == "gke":
                deploy_to_gke(args.project_id, args.implementation)
            elif args.target == "cloud-run":
                deploy_to_cloud_run(args.project_id, args.implementation)
            
            print(f"\nDeployment Summary:")
            print(f"  Implementation: {args.implementation}")
            print(f"  Target: {args.target}")
            print(f"  Image: {image_name}")
            print(f"  ADK Compatible: {'Yes' if args.implementation == 'lowlevel' else 'FastMCP'}")
        
    except subprocess.CalledProcessError as e:
        print(f"Deployment failed: {e}", file=sys.stderr)
        sys.exit(1)
    except KeyboardInterrupt:
        print("Deployment cancelled")
        sys.exit(1)


if __name__ == "__main__":
    main()