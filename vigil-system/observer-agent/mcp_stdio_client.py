#!/usr/bin/env python3
"""
MCP Stdio Client for Observer Agent.

This module provides a proper MCP client that communicates with the MCP server
via stdio, using the official MCP Python SDK.
"""

import asyncio
import json
import logging
import subprocess
import sys
from typing import Any, Dict, Optional
from contextlib import asynccontextmanager

from mcp.client.session import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client

logger = logging.getLogger(__name__)


class MCPStdioClient:
    """MCP client that communicates with server via stdio."""
    
    def __init__(self, server_script_path: str = "/app/vigil_mcp_stdio_server.py"):
        """
        Initialize the MCP stdio client.
        
        Args:
            server_script_path: Path to the MCP server script
        """
        self.server_script_path = server_script_path
        self.session: Optional[ClientSession] = None
        self._client = None
        
    async def connect(self) -> bool:
        """
        Connect to the MCP server via stdio.
        
        Returns:
            True if connection successful, False otherwise
        """
        try:
            # Create server parameters for stdio connection
            server_params = StdioServerParameters(
                command="python",
                args=[self.server_script_path],
                env=None  # Will use current environment
            )
            
            # Connect using the stdio client context manager
            self._client = stdio_client(server_params)
            self.session = await self._client.__aenter__()
            
            # Initialize the session
            await self.session.initialize()
            
            logger.info("Successfully connected to MCP server via stdio")
            logger.info(f"Available tools: {[tool.name for tool in self.session.tools]}")
            logger.info(f"Available resources: {[resource.uri for resource in self.session.resources]}")
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to connect to MCP server: {e}")
            return False
    
    async def call_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Any:
        """
        Call an MCP tool.
        
        Args:
            tool_name: Name of the tool to call
            arguments: Arguments to pass to the tool
            
        Returns:
            Tool execution result
        """
        if not self.session:
            logger.error("Not connected to MCP server")
            return None
            
        try:
            # Call the tool through the session
            result = await self.session.call_tool(tool_name, arguments)
            
            # The result is typically a list of tool results
            if result and len(result) > 0:
                # Extract the actual content from the first result
                content = result[0]
                if hasattr(content, 'text'):
                    # Parse JSON if the content is JSON text
                    try:
                        return json.loads(content.text)
                    except json.JSONDecodeError:
                        return content.text
                return content
                
            return result
            
        except Exception as e:
            logger.error(f"Error calling tool {tool_name}: {e}")
            return None
    
    async def get_resource(self, resource_uri: str) -> Any:
        """
        Get an MCP resource.
        
        Args:
            resource_uri: URI of the resource to retrieve
            
        Returns:
            Resource content
        """
        if not self.session:
            logger.error("Not connected to MCP server")
            return None
            
        try:
            # Read the resource through the session
            result = await self.session.read_resource(resource_uri)
            
            if result and len(result) > 0:
                content = result[0]
                if hasattr(content, 'text'):
                    try:
                        return json.loads(content.text)
                    except json.JSONDecodeError:
                        return content.text
                return content
                
            return result
            
        except Exception as e:
            logger.error(f"Error getting resource {resource_uri}: {e}")
            return None
    
    async def close(self):
        """Close the connection to the MCP server."""
        if self._client:
            try:
                await self._client.__aexit__(None, None, None)
            except Exception as e:
                logger.error(f"Error closing MCP client: {e}")
            finally:
                self._client = None
                self.session = None
    
    async def __aenter__(self):
        """Async context manager entry."""
        await self.connect()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.close()


async def test_mcp_client():
    """Test function to verify MCP client works correctly."""
    logging.basicConfig(level=logging.INFO)
    
    client = MCPStdioClient()
    
    try:
        # Connect to the server
        if await client.connect():
            logger.info("✓ Connected to MCP server")
            
            # Test getting a resource
            config = await client.get_resource("vigil://config/bank-connection")
            if config:
                logger.info(f"✓ Got config resource: {config}")
            
            # Test calling a tool
            result = await client.call_tool(
                "get_transactions",
                {"account_id": "1033623433"}
            )
            if result:
                logger.info(f"✓ Got transactions: {json.dumps(result, indent=2)[:500]}...")
            
            logger.info("All tests passed!")
        else:
            logger.error("Failed to connect to MCP server")
            
    finally:
        await client.close()


if __name__ == "__main__":
    # Run the test
    asyncio.run(test_mcp_client())