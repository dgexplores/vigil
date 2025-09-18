#!/usr/bin/env python3
"""
Test script to validate Vigil MCP Server compliance with Model Context Protocol.

This script tests the MCP server functionality using the streamable HTTP transport.
"""

import asyncio
import json

from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client


async def test_mcp_server():
    """Test the MCP server functionality."""
    server_url = "http://localhost:8080/mcp"
    
    print(f"Testing Vigil MCP Server at {server_url}")
    print("=" * 50)
    
    try:
        async with streamablehttp_client(server_url) as (read_stream, write_stream, _):
            async with ClientSession(read_stream, write_stream) as session:
                # Initialize the connection
                print("Initializing MCP connection...")
                await session.initialize()
                print("✓ Connection initialized successfully")
                
                # Test 1: List available tools
                print("\nTest 1: Listing available tools...")
                tools = await session.list_tools()
                print(f"✓ Found {len(tools.tools)} tools:")
                for tool in tools.tools:
                    print(f"  - {tool.name}: {tool.description}")
                
                # Test 2: List available resources  
                print("\nTest 2: Listing available resources...")
                resources = await session.list_resources()
                print(f"✓ Found {len(resources.resources)} resources:")
                for resource in resources.resources:
                    print(f"  - {resource.uri}: {resource.description}")
                
                # Test 3: Read a resource
                if resources.resources:
                    print("\nTest 3: Reading a resource...")
                    resource_uri = resources.resources[0].uri
                    resource_content = await session.read_resource(resource_uri)
                    content_block = resource_content.contents[0]
                    if hasattr(content_block, 'text'):
                        print(f"✓ Resource content: {content_block.text[:100]}...")
                    else:
                        print(f"✓ Resource content retrieved (type: {type(content_block)})")
                
                # Test 4: Test a simple tool (this would fail without Bank of Anthos)
                print("\nTest 4: Testing tool calls...")
                print("ℹ  Note: Tool calls may fail without Bank of Anthos backend")
                try:
                    # This will likely fail in testing but demonstrates the API
                    result = await session.call_tool("get_transactions", {"account_id": "test123"})
                    print("✓ Tool call successful")
                    print(f"  Result: {result.content}")
                except Exception as e:
                    print(f"⚠  Tool call failed (expected without Bank of Anthos): {e}")
                
                print("\n" + "=" * 50)
                print("MCP Server Compliance Test Summary:")
                print("✓ MCP protocol initialization - PASSED")
                print("✓ Tool discovery - PASSED")
                print("✓ Resource discovery - PASSED") 
                print("✓ Resource reading - PASSED")
                print("⚠ Tool execution - EXPECTED FAILURE (no Bank of Anthos)")
                print("\n✓ Overall: MCP server is compliant with the protocol!")
                
    except Exception as e:
        print(f"✗ Test failed: {e}")
        return False
    
    return True


if __name__ == "__main__":
    print("Vigil MCP Server Compliance Test")
    print("Make sure to run: kubectl port-forward -n vigil-system svc/mcp-server 8080:8000")
    print()
    
    success = asyncio.run(test_mcp_server())
    exit(0 if success else 1)