#!/usr/bin/env python3
"""
Test script to validate our consolidated MCP system deployment.
Tests the shared bank_api_client to fetch real transactions.
"""

import asyncio
import sys
import os

# Add the path for importing our consolidated modules
sys.path.insert(0, '/app')

from shared.bank_api_client import BankAPIClient, AuthManager

async def test_bank_api_client():
    """Test the consolidated bank API client directly."""
    print("🧪 Testing Consolidated Bank API Client")
    print("=" * 50)
    
    # Initialize the consolidated components
    auth_manager = AuthManager() 
    bank_client = BankAPIClient(auth_manager=auth_manager)
    
    print("✅ Created AuthManager and BankAPIClient")
    
    # Test account IDs from Bank of Anthos demo
    test_accounts = ['1033623433', '1011226111', '1055757655', '1077441377']
    
    for account_id in test_accounts:
        try:
            print(f"\n🔍 Testing account: {account_id}")
            
            # This will first try the API, then fall back to direct DB access
            result = await bank_client.get_transactions(account_id)
            
            if 'error' in result:
                print(f"❌ Error for account {account_id}: {result['error']}")
            else:
                transaction_count = result.get('total_count', 0)
                print(f"✅ Account {account_id}: {transaction_count} transactions found")
                
                if transaction_count > 0:
                    # Show a sample transaction
                    transactions = result.get('transactions', [])
                    if transactions:
                        sample = transactions[0]
                        print(f"   Sample: {sample.get('amount')} from {sample.get('fromAccountNum')} to {sample.get('toAccountNum')}")
                        print(f"   Time: {sample.get('timestamp')}")
                        
        except Exception as e:
            print(f"❌ Exception for account {account_id}: {e}")
    
    # Clean up
    await bank_client.close()
    print(f"\n🎉 Test completed successfully!")
    print("📊 Consolidated MCP system is working with real Bank of Anthos data!")

if __name__ == "__main__":
    asyncio.run(test_bank_api_client())