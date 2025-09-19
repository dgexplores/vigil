#!/usr/bin/env python3
"""
MCP Client Bridge - Stdio to HTTP/SSE bridge for MCP protocol.

This script acts as a bridge between ADK agents (which expect stdio communication)
and MCP servers running with HTTP/SSE transport in the cluster.

It receives MCP messages via stdio from the ADK agent and forwards them to the
MCP server over HTTP/SSE, then relays responses back via stdio.
"""

import asyncio
import json
import logging
import os
import sys
from typing import AsyncIterator, Optional

import httpx

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class MCPClientBridge:
    """Bridge between stdio MCP client and HTTP/SSE MCP server."""
    
    def __init__(self, server_url: str):
        self.server_url = server_url
        self.sse_url = f"{server_url}/sse"
        self.http_client = httpx.AsyncClient(timeout=30.0)
        self.reader: Optional[asyncio.StreamReader] = None
        self.writer: Optional[asyncio.StreamWriter] = None
    
    async def start(self):
        """Start the bridge."""
        # Set up stdio streams
        loop = asyncio.get_event_loop()
        self.reader = asyncio.StreamReader(loop=loop)
        protocol = asyncio.StreamReaderProtocol(self.reader, loop=loop)
        await loop.connect_read_pipe(lambda: protocol, sys.stdin)
        
        w_transport, w_protocol = await loop.connect_write_pipe(
            asyncio.streams.FlowControlMixin, sys.stdout
        )
        self.writer = asyncio.StreamWriter(w_transport, w_protocol, None, loop)
        
        # Start handling messages
        await self.handle_messages()
    
    async def handle_messages(self):
        """Handle messages between stdio and HTTP/SSE."""
        # Start SSE connection
        sse_task = asyncio.create_task(self.handle_sse())
        
        try:
            # Read from stdin and forward to server
            while True:
                line = await self.reader.readline()
                if not line:
                    break
                
                try:
                    message = json.loads(line.decode())
                    logger.debug(f"Received from stdio: {message}")
                    
                    # Forward to HTTP endpoint based on message type
                    response = await self.forward_to_server(message)
                    
                    if response:
                        # Send response back via stdio
                        response_line = json.dumps(response) + '\n'
                        self.writer.write(response_line.encode())
                        await self.writer.drain()
                        logger.debug(f"Sent to stdio: {response}")
                
                except json.JSONDecodeError as e:
                    logger.error(f"Invalid JSON from stdio: {e}")
                except Exception as e:
                    logger.error(f"Error handling message: {e}")
        
        finally:
            sse_task.cancel()
            await self.http_client.aclose()
    
    async def handle_sse(self):
        """Handle Server-Sent Events from MCP server."""
        try:
            async with self.http_client.stream('GET', self.sse_url) as response:
                async for line in response.aiter_lines():
                    if line.startswith('data: '):
                        try:
                            data = json.loads(line[6:])
                            # Send SSE data to stdio
                            message_line = json.dumps(data) + '\n'
                            self.writer.write(message_line.encode())
                            await self.writer.drain()
                            logger.debug(f"SSE to stdio: {data}")
                        except json.JSONDecodeError:
                            pass
        except Exception as e:
            logger.error(f"SSE connection error: {e}")
    
    async def forward_to_server(self, message: dict) -> Optional[dict]:
        """Forward a message to the HTTP server and get response."""
        try:
            # Determine endpoint based on JSON-RPC method
            method = message.get('method', '')
            
            # Map JSON-RPC methods to HTTP endpoints
            if method == 'tools/list':
                response = await self.http_client.get(f"{self.server_url}/capabilities")
                if response.status_code == 200:
                    data = response.json()
                    return {
                        'jsonrpc': '2.0',
                        'id': message.get('id'),
                        'result': data.get('capabilities', {}).get('tools', [])
                    }
            
            elif method == 'tools/call':
                params = message.get('params', {})
                tool_name = params.get('name')
                arguments = params.get('arguments', {})
                
                # Call the tool endpoint
                response = await self.http_client.post(
                    f"{self.server_url}/tools/{tool_name}",
                    json=arguments
                )
                
                if response.status_code == 200:
                    return {
                        'jsonrpc': '2.0',
                        'id': message.get('id'),
                        'result': response.json()
                    }
                else:
                    return {
                        'jsonrpc': '2.0',
                        'id': message.get('id'),
                        'error': {
                            'code': response.status_code,
                            'message': response.text
                        }
                    }
            
            elif method == 'initialize':
                # Send initialization response
                return {
                    'jsonrpc': '2.0',
                    'id': message.get('id'),
                    'result': {
                        'protocolVersion': '1.0',
                        'capabilities': {
                            'tools': {},
                            'resources': {}
                        }
                    }
                }
            
            # For other methods, return empty result
            return {
                'jsonrpc': '2.0',
                'id': message.get('id'),
                'result': {}
            }
            
        except Exception as e:
            logger.error(f"Error forwarding to server: {e}")
            return {
                'jsonrpc': '2.0',
                'id': message.get('id'),
                'error': {
                    'code': -32603,
                    'message': str(e)
                }
            }

async def main():
    """Main entry point."""
    if len(sys.argv) < 2:
        logger.error("Usage: mcp_client_bridge.py <MCP_SERVER_URL>")
        sys.exit(1)
    
    server_url = sys.argv[1]
    logger.info(f"Starting MCP client bridge to {server_url}")
    
    bridge = MCPClientBridge(server_url)
    await bridge.start()

if __name__ == "__main__":
    asyncio.run(main())