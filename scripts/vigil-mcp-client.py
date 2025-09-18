#!/usr/bin/env python3
"""
Vigil MCP Client Wrapper for Warp Terminal Integration

This script acts as a local MCP client that connects to the Vigil MCP server
running in the GKE cluster through kubectl port-forwarding.
"""

import os
import sys
import subprocess
import json
import logging
from pathlib import Path

# Configure logging
logging.basicConfig(
    level=os.getenv('LOG_LEVEL', 'INFO'),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Configuration
# Since this script is in scripts/, go up one level to find vigil-system/
PROJECT_ROOT = Path(__file__).parent.parent
VIGIL_SYSTEM_PATH = PROJECT_ROOT / "vigil-system"
MCP_SERVER_PATH = VIGIL_SYSTEM_PATH / "mcp-server"
MCP_SERVER_SCRIPT = MCP_SERVER_PATH / "vigil_mcp_server.py"

# Use the virtual environment if available
VENV_PATH = MCP_SERVER_PATH / "venv"
VENV_PYTHON = VENV_PATH / "bin" / "python"

def check_port_forward(port: int, service_name: str) -> bool:
    """Check if kubectl port-forward is active for a given port."""
    try:
        result = subprocess.run(
            ["lsof", "-i", f":{port}"],
            capture_output=True,
            text=True,
            timeout=2
        )
        return result.returncode == 0
    except (subprocess.SubprocessError, FileNotFoundError):
        # If lsof is not available, try connecting
        import socket
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(1)
        try:
            result = sock.connect_ex(('localhost', port))
            return result == 0
        finally:
            sock.close()

def setup_port_forwards():
    """Ensure kubectl port-forwards are active for backend services the local MCP relies on."""
    services = [
        (8081, "userservice", "Userservice"),
        (8082, "transactionhistory", "Transaction History"),
        (8083, "ledgerwriter", "Ledger Writer"),
    ]
    
    missing_forwards = []
    for port, service, name in services:
        if not check_port_forward(port, name):
            missing_forwards.append((port, service, name))
    
    if missing_forwards:
        logger.warning("⚠️  Missing kubectl port-forwards detected!")
        logger.info("Please run the following commands in separate terminals:")
        for port, service, name in missing_forwards:
            logger.info(f"  kubectl port-forward svc/{service} {port}:8080")
        logger.info("\nThe MCP client will attempt to start anyway...")
        return False
    
    return True

def get_python_executable():
    """Get the appropriate Python executable to use."""
    # Check if virtual environment exists and is usable
    if VENV_PYTHON.exists():
        try:
            result = subprocess.run(
                [str(VENV_PYTHON), "--version"],
                capture_output=True,
                text=True,
                timeout=2
            )
            if result.returncode == 0:
                logger.debug(f"Using virtual environment Python: {VENV_PYTHON}")
                return str(VENV_PYTHON)
        except subprocess.SubprocessError:
            pass
    
    # Fall back to system Python
    logger.debug("Using system Python")
    return sys.executable

def main():
    """Main entry point for the MCP client wrapper."""
    
    logger.info("Starting Vigil MCP Client for Warp Terminal...")
    
    # Check port forwards
    forwards_ready = setup_port_forwards()
    if not forwards_ready:
        logger.warning("Port forwards not fully configured, some features may not work")
    
    # Prepare environment variables
    env = os.environ.copy()
    
    # Add Google Cloud SDK to PATH if it exists
    gcloud_sdk_path = "/home/zenkit/Hackathon/GKE Turns 10 Hackathon Devpost 2025/google-cloud-sdk/bin"
    if os.path.exists(gcloud_sdk_path):
        current_path = env.get('PATH', '')
        env['PATH'] = f"{gcloud_sdk_path}:{current_path}"
    
    # Set default environment variables if not already set
    defaults = {
        "BANK_BASE_URL": "http://localhost:8080",
        "MCP_SERVER_URL": "http://localhost:8000",
        "REQUEST_TIMEOUT": "30",
        "AUTH_USERNAME": "testuser",
        "AUTH_PASSWORD": "bankofanthos",
        "JWT_SECRET": "secret-key-change-in-production",
        "PYTHONPATH": str(MCP_SERVER_PATH),
        "USE_GKE_GCLOUD_AUTH_PLUGIN": "True"
    }
    
    for key, value in defaults.items():
        if key not in env:
            env[key] = value
    
    # Get Python executable
    python_exe = get_python_executable()
    
    # Check if MCP server script exists
    if not MCP_SERVER_SCRIPT.exists():
        logger.error(f"MCP server script not found: {MCP_SERVER_SCRIPT}")
        sys.exit(1)
    
    # Run the MCP server in STDIO mode for Warp
    cmd = [
        python_exe,
        str(MCP_SERVER_SCRIPT),
        "--transport", "stdio"
    ]
    
    logger.info(f"Launching MCP server: {' '.join(cmd)}")
    logger.debug(f"Environment: {json.dumps({k: v for k, v in env.items() if 'PASSWORD' not in k}, indent=2)}")
    
    try:
        # Run the server and pass through stdio
        process = subprocess.run(cmd, env=env)
        sys.exit(process.returncode)
    except KeyboardInterrupt:
        logger.info("MCP client interrupted by user")
        sys.exit(0)
    except Exception as e:
        logger.error(f"Failed to run MCP server: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()