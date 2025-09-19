#!/usr/bin/env python3
"""
Vigil MCP Stdio Server - Wrapper for stdio-based MCP communication.

This server runs the MCP server in stdio mode for sidecar deployment,
handling proper MCP protocol communication over stdin/stdout.
"""

import asyncio
import json
import logging
import os
import sys
from typing import Any, Dict

# Configure logging to stderr to avoid polluting stdout
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stderr)]
)
logger = logging.getLogger(__name__)

# Import the main MCP server module
from vigil_mcp_server import mcp

async def run_stdio_server():
    """Run the MCP server in stdio mode."""
    logger.info("Starting Vigil MCP Server in stdio mode")
    
    # Set environment variables if not already set
    if 'BANK_BASE_URL' not in os.environ:
        os.environ['BANK_BASE_URL'] = 'http://userservice:8080'
    if 'REQUEST_TIMEOUT' not in os.environ:
        os.environ['REQUEST_TIMEOUT'] = '30'
    if 'AUTH_USERNAME' not in os.environ:
        os.environ['AUTH_USERNAME'] = 'testuser'
    if 'AUTH_PASSWORD' not in os.environ:
        os.environ['AUTH_PASSWORD'] = 'bankofanthos'
    if 'JWT_SECRET' not in os.environ:
        os.environ['JWT_SECRET'] = 'secret-key-change-in-production'
    
    logger.info(f"Bank base URL: {os.environ['BANK_BASE_URL']}")
    
    # Run the MCP server with stdio transport
    await mcp.run(transport="stdio")

def main():
    """Main entry point for stdio server."""
    try:
        # Run the async server
        asyncio.run(run_stdio_server())
    except KeyboardInterrupt:
        logger.info("Server interrupted by user")
    except Exception as e:
        logger.error(f"Server error: {e}", exc_info=True)
        sys.exit(1)

if __name__ == "__main__":
    main()