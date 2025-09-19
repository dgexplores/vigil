#!/usr/bin/env python3
"""
Test script to verify stdio communication between Observer Agent and MCP Server.

This script tests the refactored stdio-based MCP communication to ensure
proper integration between the observer agent and the sidecar MCP server.
"""

import asyncio
import json
import logging
import os
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).parent / "observer-agent"))
sys.path.insert(0, str(Path(__file__).parent / "mcp-server"))

from observer_agent.mcp_stdio_client import MCPStdioClient

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def test_stdio_communication():
    """Test the stdio-based MCP communication."""
    
    logger.info("="*60)
    logger.info("Testing Stdio-based MCP Communication")
    logger.info("="*60)
    
    # Set up environment variables for the test
    os.environ['BANK_BASE_URL'] = 'http://localhost:8080'
    os.environ['AUTH_USERNAME'] = 'testuser'
    os.environ['AUTH_PASSWORD'] = 'bankofanthos'
    
    # Path to the MCP server script
    server_script = str(Path(__file__).parent / "mcp-server" / "vigil_mcp_stdio_server.py")
    
    logger.info(f"Using MCP server script: {server_script}")
    
    # Create the MCP client
    client = MCPStdioClient(server_script)
    
    test_results = {
        "connection": False,
        "resource_access": False,
        "tool_execution": False,
        "transaction_fetch": False
    }
    
    try:
        # Test 1: Connection
        logger.info("\n📡 Test 1: Connecting to MCP server via stdio...")
        if await client.connect():
            logger.info("✅ Successfully connected to MCP server")
            test_results["connection"] = True
            
            # Display available tools and resources
            if client.session:
                logger.info(f"Available tools: {[tool.name for tool in client.session.tools]}")
                logger.info(f"Available resources: {[resource.uri for resource in client.session.resources]}")
        else:
            logger.error("❌ Failed to connect to MCP server")
            return test_results
        
        # Test 2: Resource Access
        logger.info("\n📚 Test 2: Accessing MCP resources...")
        try:
            config = await client.get_resource("vigil://config/bank-connection")
            if config:
                logger.info(f"✅ Successfully retrieved config resource:")
                logger.info(f"   {json.dumps(config, indent=2)}")
                test_results["resource_access"] = True
            else:
                logger.error("❌ Failed to retrieve config resource")
        except Exception as e:
            logger.error(f"❌ Error accessing resource: {e}")
        
        # Test 3: Tool Execution (Health Check)
        logger.info("\n🔧 Test 3: Testing tool execution...")
        try:
            # Try to get user details (simple tool test)
            result = await client.call_tool(
                "get_user_details",
                {"user_id": "test_user"}
            )
            if result:
                logger.info(f"✅ Tool execution successful")
                logger.info(f"   Result: {json.dumps(result, indent=2)[:200]}...")
                test_results["tool_execution"] = True
            else:
                logger.warning("⚠️ Tool executed but returned no result")
        except Exception as e:
            logger.error(f"❌ Error executing tool: {e}")
        
        # Test 4: Transaction Fetching
        logger.info("\n💰 Test 4: Fetching transactions...")
        try:
            # Test with a known Bank of Anthos account
            test_accounts = ["1033623433", "1011226111"]
            
            for account_id in test_accounts:
                logger.info(f"   Testing account {account_id}...")
                result = await client.call_tool(
                    "get_transactions",
                    {"account_id": account_id}
                )
                
                if result:
                    if isinstance(result, dict):
                        if "transactions" in result:
                            tx_count = len(result.get("transactions", []))
                            logger.info(f"   ✅ Retrieved {tx_count} transactions for account {account_id}")
                            test_results["transaction_fetch"] = True
                            
                            # Show sample transaction
                            if tx_count > 0:
                                sample_tx = result["transactions"][0]
                                logger.info(f"   Sample transaction: {json.dumps(sample_tx, indent=2)}")
                            break
                        elif "error" in result:
                            logger.warning(f"   ⚠️ API returned error: {result['error']}")
                    else:
                        logger.warning(f"   ⚠️ Unexpected result format: {type(result)}")
                else:
                    logger.warning(f"   ⚠️ No result for account {account_id}")
                    
        except Exception as e:
            logger.error(f"❌ Error fetching transactions: {e}")
        
    except Exception as e:
        logger.error(f"❌ Test failed with error: {e}", exc_info=True)
    
    finally:
        # Clean up
        logger.info("\n🧹 Cleaning up...")
        await client.close()
        logger.info("✅ MCP client closed")
    
    # Summary
    logger.info("\n" + "="*60)
    logger.info("TEST RESULTS SUMMARY")
    logger.info("="*60)
    
    total_tests = len(test_results)
    passed_tests = sum(1 for v in test_results.values() if v)
    
    for test_name, passed in test_results.items():
        status = "✅ PASSED" if passed else "❌ FAILED"
        logger.info(f"{test_name.replace('_', ' ').title()}: {status}")
    
    logger.info(f"\nTotal: {passed_tests}/{total_tests} tests passed")
    
    if passed_tests == total_tests:
        logger.info("\n🎉 All tests passed! The stdio integration is working correctly.")
    else:
        logger.warning(f"\n⚠️ {total_tests - passed_tests} test(s) failed. Please review the logs.")
    
    return test_results


async def test_observer_agent_integration():
    """Test the full observer agent with MCP stdio integration."""
    
    logger.info("\n" + "="*60)
    logger.info("Testing Observer Agent with Stdio MCP Integration")
    logger.info("="*60)
    
    # Import the observer agent components
    from observer_agent.agent import TransactionProcessor, health_status
    
    # Create MCP client
    server_script = str(Path(__file__).parent / "mcp-server" / "vigil_mcp_stdio_server.py")
    mcp_client = MCPStdioClient(server_script)
    
    try:
        # Connect to MCP server
        logger.info("\n🔌 Connecting to MCP server...")
        if await mcp_client.connect():
            logger.info("✅ Connected to MCP server")
            health_status.mcp_connected = True
        else:
            logger.error("❌ Failed to connect to MCP server")
            return False
        
        # Create transaction processor
        processor = TransactionProcessor(mcp_client)
        
        # Test fetching new transactions
        logger.info("\n📊 Testing transaction processing...")
        new_transactions = await processor.get_new_transactions()
        
        if new_transactions:
            logger.info(f"✅ Found {len(new_transactions)} new transactions")
            
            # Normalize transactions
            normalized = []
            for tx in new_transactions[:3]:  # Process first 3 for testing
                normalized_tx = await processor.normalize_transaction(tx)
                normalized.append(normalized_tx)
                logger.info(f"   Normalized transaction: {normalized_tx['transaction_id']}")
            
            logger.info(f"✅ Successfully normalized {len(normalized)} transactions")
            return True
        else:
            logger.info("ℹ️ No transactions found (this is normal if no recent activity)")
            return True
            
    except Exception as e:
        logger.error(f"❌ Integration test failed: {e}", exc_info=True)
        return False
        
    finally:
        await mcp_client.close()
        logger.info("✅ Cleanup complete")


async def main():
    """Main test entry point."""
    
    # Run basic stdio communication tests
    basic_results = await test_stdio_communication()
    
    # If basic tests pass, run integration test
    if basic_results["connection"]:
        logger.info("\n" + "="*60)
        await test_observer_agent_integration()
    
    logger.info("\n" + "="*60)
    logger.info("All tests completed!")
    logger.info("="*60)


if __name__ == "__main__":
    asyncio.run(main())