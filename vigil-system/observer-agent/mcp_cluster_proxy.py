#!/usr/bin/env python3
"""
MCP Cluster Proxy - Lightweight stdio-to-HTTP proxy for in-cluster MCP communication.

This script acts as an MCP server from the ADK agent's perspective (communicating via stdio),
but actually proxies requests to the real MCP server in the cluster via HTTP.
"""

import asyncio
import json
import logging
import os
import sys
from typing import Any, Dict, List, Optional
import httpx
from datetime import datetime

# Configure logging to stderr to not interfere with stdio protocol
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stderr)]
)
logger = logging.getLogger(__name__)

# Configuration
MCP_SERVER_URL = os.getenv('MCP_SERVER_URL', 'http://mcp-server:8000')


class MCPClusterProxy:
    """Proxy that translates stdio MCP protocol to HTTP calls."""
    
    def __init__(self):
        self.server_url = MCP_SERVER_URL
        self.http_client = httpx.Client(timeout=30.0)
        
    async def handle_stdio(self):
        """Handle stdio communication with the ADK agent."""
        logger.info(f"MCP Cluster Proxy starting, connected to {self.server_url}")
        
        # Read from stdin and process messages
        for line in sys.stdin:
            try:
                if not line.strip():
                    continue
                    
                message = json.loads(line)
                logger.debug(f"Received message: {message}")
                
                response = await self.handle_message(message)
                if response:
                    # Write response to stdout
                    sys.stdout.write(json.dumps(response) + '\n')
                    sys.stdout.flush()
                    logger.debug(f"Sent response: {response}")
                    
            except json.JSONDecodeError as e:
                logger.error(f"Invalid JSON: {e}")
                error_response = {
                    "jsonrpc": "2.0",
                    "error": {
                        "code": -32700,
                        "message": "Parse error"
                    }
                }
                sys.stdout.write(json.dumps(error_response) + '\n')
                sys.stdout.flush()
            except Exception as e:
                logger.error(f"Error processing message: {e}")
    
    async def handle_message(self, message: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Handle an individual MCP message."""
        method = message.get('method', '')
        params = message.get('params', {})
        msg_id = message.get('id')
        
        try:
            # Handle different MCP methods
            if method == 'initialize':
                return {
                    "jsonrpc": "2.0",
                    "id": msg_id,
                    "result": {
                        "protocolVersion": "2024-11-05",
                        "serverInfo": {
                            "name": "vigil-mcp-proxy",
                            "version": "1.0.0"
                        },
                        "capabilities": {
                            "tools": {},
                            "resources": {}
                        }
                    }
                }
            
            elif method == 'tools/list':
                # Get capabilities from the real MCP server
                response = self.http_client.get(f"{self.server_url}/capabilities")
                if response.status_code == 200:
                    data = response.json()
                    tools = data.get('capabilities', {}).get('tools', [])
                    return {
                        "jsonrpc": "2.0",
                        "id": msg_id,
                        "result": {
                            "tools": tools
                        }
                    }
            
            elif method == 'tools/call':
                tool_name = params.get('name')
                arguments = params.get('arguments', {})
                
                # Call the appropriate tool endpoint
                if tool_name == 'get_transactions':
                    response = self.http_client.post(
                        f"{self.server_url}/tools/get_transactions",
                        json=arguments
                    )
                elif tool_name == 'authenticate_user':
                    response = self.http_client.post(
                        f"{self.server_url}/tools/authenticate_user",
                        json=arguments
                    )
                elif tool_name == 'get_user_details':
                    response = self.http_client.post(
                        f"{self.server_url}/tools/get_user_details",
                        json={"user_id": arguments.get('user_id')}
                    )
                else:
                    return {
                        "jsonrpc": "2.0",
                        "id": msg_id,
                        "error": {
                            "code": -32601,
                            "message": f"Unknown tool: {tool_name}"
                        }
                    }
                
                if response.status_code == 200:
                    result = response.json()
                    return {
                        "jsonrpc": "2.0",
                        "id": msg_id,
                        "result": [
                            {
                                "type": "text",
                                "text": json.dumps(result, indent=2)
                            }
                        ]
                    }
                else:
                    return {
                        "jsonrpc": "2.0",
                        "id": msg_id,
                        "error": {
                            "code": response.status_code,
                            "message": response.text
                        }
                    }
            
            elif method == 'resources/list':
                return {
                    "jsonrpc": "2.0",
                    "id": msg_id,
                    "result": {
                        "resources": []
                    }
                }
            
            elif method == 'ping':
                return {
                    "jsonrpc": "2.0",
                    "id": msg_id,
                    "result": {}
                }
            
            else:
                logger.warning(f"Unhandled method: {method}")
                return {
                    "jsonrpc": "2.0",
                    "id": msg_id,
                    "result": {}
                }
                
        except Exception as e:
            logger.error(f"Error handling method {method}: {e}")
            return {
                "jsonrpc": "2.0",
                "id": msg_id,
                "error": {
                    "code": -32603,
                    "message": str(e)
                }
            }
    
    def cleanup(self):
        """Clean up resources."""
        self.http_client.close()


async def main():
    """Main entry point."""
    proxy = MCPClusterProxy()
    try:
        await proxy.handle_stdio()
    finally:
        proxy.cleanup()


if __name__ == "__main__":
    # Run the proxy
    asyncio.run(main())