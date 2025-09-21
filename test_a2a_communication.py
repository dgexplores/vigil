#!/usr/bin/env python3
"""
Test script for A2A communication between Transaction Monitor and Orchestrator agents.
This script tests the proper implementation of the A2A protocol.
"""

import asyncio
import json
import logging
import time
from datetime import datetime, timezone

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

async def test_a2a_communication():
    """Test A2A communication by simulating the transaction monitor sending an alert."""
    
    try:
        # Import A2A SDK components
        from a2a.client import ClientFactory
        from a2a.types import SendMessageRequest
        
        logger.info("Testing A2A communication...")
        
        # Create a test transaction
        test_transaction = {
            "transaction_id": f"test_{int(time.time())}",
            "amount": "2500.00",  # Above fraud threshold
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "from_account_id": "acc_test_123",
            "to_account_id": "acc_test_456",
            "description": "High value test transaction"
        }
        
        logger.info(f"Created test transaction: {test_transaction}")
        
        # Create A2A client to connect to orchestrator
        orchestrator_url = "http://localhost:8000/a2a"  # Local test
        
        logger.info(f"Creating A2A client for {orchestrator_url}")
        client = ClientFactory.create_client_with_http_transport(url=orchestrator_url)
        
        # Create A2A message request
        message_request = SendMessageRequest(
            message=f"Process transaction alert: {json.dumps(test_transaction)}"
        )
        
        logger.info(f"Sending A2A message: {message_request.message[:100]}...")
        
        # Send A2A message to orchestrator
        result = await client.send_message(message_request)
        
        if result and hasattr(result, 'message'):
            logger.info(f"✅ A2A communication successful!")
            logger.info(f"Orchestrator response: {result.message}")
            return True
        else:
            logger.error(f"❌ No response from orchestrator")
            return False
            
    except ImportError as e:
        logger.error(f"❌ A2A SDK import error: {e}")
        logger.info("Make sure to install: pip install a2a-sdk[http-server]")
        return False
    except Exception as e:
        logger.error(f"❌ A2A communication test failed: {e}", exc_info=True)
        return False

async def test_health_check():
    """Test the orchestrator health endpoint."""
    try:
        import httpx
        
        logger.info("Testing orchestrator health endpoint...")
        
        async with httpx.AsyncClient() as client:
            response = await client.get("http://localhost:8000/health")
            
            if response.status_code == 200:
                health_data = response.json()
                logger.info(f"✅ Health check passed: {health_data}")
                return True
            else:
                logger.error(f"❌ Health check failed with status: {response.status_code}")
                return False
                
    except ImportError:
        logger.warning("httpx not available, skipping health check test")
        return True
    except Exception as e:
        logger.error(f"❌ Health check failed: {e}")
        return False

def run_in_container():
    """Run the test in a container environment with proper dependencies."""
    
    logger.info("Running A2A communication test in container...")
    
    # Docker command to run the test
    docker_cmd = '''
    docker run --rm --network host \
        -v "/home/zenkit/Hackathon/GKE Turns 10 Hackathon Devpost 2025/gke-turns10-hackathon-vigil":/workspace \
        -w /workspace \
        python:3.11 \
        bash -c "
            pip install a2a-sdk[http-server] httpx && 
            python test_a2a_communication.py --container
        "
    '''
    
    import subprocess
    import os
    
    try:
        result = subprocess.run(docker_cmd, shell=True, capture_output=True, text=True)
        
        if result.returncode == 0:
            logger.info("✅ Container test completed successfully")
            logger.info(f"Output: {result.stdout}")
        else:
            logger.error(f"❌ Container test failed with exit code: {result.returncode}")
            logger.error(f"Error: {result.stderr}")
            
        return result.returncode == 0
        
    except Exception as e:
        logger.error(f"❌ Failed to run container test: {e}")
        return False

async def main():
    """Main test runner."""
    
    import sys
    
    if "--container" in sys.argv:
        # Running inside container
        logger.info("🐳 Running A2A tests inside container")
        
        # Test health check first
        health_ok = await test_health_check()
        
        # Test A2A communication
        a2a_ok = await test_a2a_communication()
        
        if health_ok and a2a_ok:
            logger.info("🎉 All A2A tests passed!")
            sys.exit(0)
        else:
            logger.error("💥 Some A2A tests failed")
            sys.exit(1)
    else:
        # Running on host - use container
        logger.info("🔧 Starting A2A communication test...")
        logger.info("This will test the A2A protocol implementation between agents")
        logger.info("Note: Make sure the orchestrator agent is running on port 8000")
        
        success = run_in_container()
        
        if success:
            logger.info("🎉 A2A communication test completed successfully!")
        else:
            logger.error("💥 A2A communication test failed")

if __name__ == "__main__":
    asyncio.run(main())