#!/usr/bin/env python3

import sys

def test_a2a_imports():
    """Test what's available in the a2a-sdk"""
    try:
        import a2a
        print(f"a2a package found, version: {getattr(a2a, '__version__', 'unknown')}")
        print(f"a2a package dir: {dir(a2a)}")
    except ImportError as e:
        print(f"Cannot import a2a: {e}")
        return
    
    # Test client imports
    try:
        from a2a.client import A2AClient
        print("✓ A2AClient import successful")
    except ImportError as e:
        print(f"✗ A2AClient import failed: {e}")
    
    try:
        from a2a.client import ClientFactory
        print("✓ ClientFactory import successful")
    except ImportError as e:
        print(f"✗ ClientFactory import failed: {e}")
    
    # Test server imports
    try:
        from a2a.server import A2AServer
        print("✓ A2AServer import successful")
    except ImportError as e:
        print(f"✗ A2AServer import failed: {e}")
    
    # Test types imports
    try:
        from a2a.types import TaskRequest
        print("✓ TaskRequest import successful")
    except ImportError as e:
        print(f"✗ TaskRequest import failed: {e}")
    
    try:
        from a2a.types import TaskResult
        print("✓ TaskResult import successful")
    except ImportError as e:
        print(f"✗ TaskResult import failed: {e}")
    
    try:
        from a2a.types import AgentCard
        print("✓ AgentCard import successful")
    except ImportError as e:
        print(f"✗ AgentCard import failed: {e}")
    
    # Check what's in types module
    try:
        import a2a.types
        print(f"a2a.types contents: {dir(a2a.types)}")
    except ImportError as e:
        print(f"Cannot import a2a.types: {e}")
    
    # Check what's in client module
    try:
        import a2a.client
        print(f"a2a.client contents: {dir(a2a.client)}")
    except ImportError as e:
        print(f"Cannot import a2a.client: {e}")

if __name__ == "__main__":
    test_a2a_imports()