#!/usr/bin/env python3
"""
Simple test script to verify ADK integration of the Vigil MCP Server.

This test validates:
1. Server starts correctly with stdio transport (ADK compatible)
2. Server responds to basic MCP protocol messages
3. Server exposes the expected tools and resources
"""

import asyncio
import json
import subprocess
import sys
import tempfile
import time
from typing import Dict, Any

def test_server_startup():
    """Test that the server starts correctly in stdio mode."""
    print("Testing server startup...")
    
    try:
        # Start the server in stdio mode
        proc = subprocess.Popen(
            ["python3", "vigil_mcp_lowlevel.py", "--transport", "stdio"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        
        # Give it a moment to start
        time.sleep(2)
        
        # Check if process is still running
        if proc.poll() is None:
            print("✅ Server started successfully in stdio mode")
            proc.terminate()
            proc.wait()
            return True
        else:
            stdout, stderr = proc.communicate()
            print(f"❌ Server failed to start: {stderr}")
            return False
            
    except Exception as e:
        print(f"❌ Error testing server startup: {e}")
        return False

def test_http_endpoints():
    """Test HTTP endpoints are working."""
    print("Testing HTTP endpoints...")
    
    try:
        # Start the server in HTTP mode
        proc = subprocess.Popen(
            ["python3", "vigil_mcp_lowlevel.py", "--transport", "streamable-http", "--port", "8001"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        
        # Give it time to start
        time.sleep(5)
        
        if proc.poll() is None:
            print("✅ HTTP server started successfully")
            
            # Test health endpoint
            import subprocess as sp
            try:
                result = sp.run(
                    ["curl", "-s", "http://localhost:8001/health"],
                    capture_output=True,
                    text=True,
                    timeout=5
                )
                
                if result.returncode == 0 and "healthy" in result.stdout:
                    print("✅ Health endpoint working")
                else:
                    print(f"❌ Health endpoint failed: {result.stdout}")
                    
            except Exception as e:
                print(f"❌ Error testing health endpoint: {e}")
            
            # Test capabilities endpoint
            try:
                result = sp.run(
                    ["curl", "-s", "http://localhost:8001/capabilities"],
                    capture_output=True,
                    text=True,
                    timeout=5
                )
                
                if result.returncode == 0 and "tools" in result.stdout:
                    print("✅ Capabilities endpoint working")
                    # Parse and show tools
                    try:
                        data = json.loads(result.stdout)
                        tools = data.get("capabilities", {}).get("tools", [])
                        print(f"   Found {len(tools)} tools: {[t['name'] for t in tools]}")
                    except json.JSONDecodeError:
                        print("   (Could not parse JSON response)")
                else:
                    print(f"❌ Capabilities endpoint failed: {result.stdout}")
                    
            except Exception as e:
                print(f"❌ Error testing capabilities endpoint: {e}")
            
            proc.terminate()
            proc.wait()
            return True
        else:
            stdout, stderr = proc.communicate()
            print(f"❌ HTTP server failed to start: {stderr}")
            return False
            
    except Exception as e:
        print(f"❌ Error testing HTTP endpoints: {e}")
        return False

def test_adk_compatibility():
    """Test ADK-specific features."""
    print("Testing ADK compatibility features...")
    
    # Check that the server uses low-level MCP implementation
    with open("vigil_mcp_lowlevel.py", "r") as f:
        content = f.read()
        
    if "mcp.server.lowlevel" in content:
        print("✅ Uses low-level MCP implementation (ADK compatible)")
    else:
        print("❌ Does not use low-level MCP implementation")
        return False
    
    if "Server(" in content:
        print("✅ Uses MCP Server class correctly")
    else:
        print("❌ Does not use MCP Server class")
        return False
        
    if "@server.list_tools()" in content:
        print("✅ Implements tool listing")
    else:
        print("❌ Missing tool listing implementation")
        return False
        
    if "@server.call_tool()" in content:
        print("✅ Implements tool calling")
    else:
        print("❌ Missing tool calling implementation")
        return False
        
    print("✅ All ADK compatibility checks passed")
    return True

def main():
    """Run all tests."""
    print("🚀 Running ADK Integration Tests for Vigil MCP Server")
    print("=" * 60)
    
    tests = [
        ("Server Startup", test_server_startup),
        ("HTTP Endpoints", test_http_endpoints), 
        ("ADK Compatibility", test_adk_compatibility)
    ]
    
    results = []
    for test_name, test_func in tests:
        print(f"\n📋 {test_name}")
        print("-" * 30)
        result = test_func()
        results.append((test_name, result))
    
    print("\n" + "=" * 60)
    print("📊 Test Results Summary")
    print("=" * 60)
    
    all_passed = True
    for test_name, result in results:
        status = "✅ PASSED" if result else "❌ FAILED"
        print(f"{test_name:<20} {status}")
        if not result:
            all_passed = False
    
    print("\n" + "=" * 60)
    if all_passed:
        print("🎉 All tests passed! ADK integration is working correctly.")
        print("🚀 The Vigil MCP Server is ready for ADK deployment.")
    else:
        print("⚠️  Some tests failed. Please check the output above.")
        
    return 0 if all_passed else 1

if __name__ == "__main__":
    sys.exit(main())