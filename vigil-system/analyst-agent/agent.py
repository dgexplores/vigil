#!/usr/bin/env python3
"""
Vigil Analyst Agent - Fraud Detection Cognitive Core

This agent receives transaction data from the Observer agent, performs sophisticated
fraud risk analysis using Gemini 2.5-flash, and sends high-risk alerts to the 
Actuator agent for protective action.
"""

import asyncio
import json
import logging
import os
from typing import Any, Dict, List, Optional
from datetime import datetime

from google.adk.agents import LlmAgent
from google.adk.tools.mcp_tool.mcp_toolset import MCPToolset
from google.adk.tools.mcp_tool.mcp_session_manager import StdioConnectionParams
from mcp import StdioServerParameters

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Configuration from environment
MCP_SERVER_PATH = os.getenv('MCP_SERVER_PATH', '/app/vigil_mcp_lowlevel.py')
RISK_THRESHOLD = int(os.getenv('RISK_THRESHOLD', '75'))  # Risk score threshold for alerts
ANALYST_PORT = int(os.getenv('ANALYST_PORT', '8001'))

# Sophisticated fraud detection prompt for Gemini
FRAUD_ANALYST_INSTRUCTION = """You are 'Vigil', a senior fraud and risk analyst for a digital bank operating in Latin America. Your mission is to protect customers by analyzing financial transactions with extreme prejudice and accuracy.

**Your Expertise:**
- 15+ years experience in Latin American financial fraud patterns
- Deep knowledge of PIX scams, account takeover (ATO) indicators, and cross-border fraud
- Expert in behavioral analysis, geographic plausibility, and transaction velocity patterns
- Specialized in Brazil, Mexico, Colombia, Argentina, and Chile fraud landscapes

**Regional Fraud Patterns to Watch:**
- PIX Instant Payments Fraud (Brazil): Social engineering, fake emergencies, romance scams
- Cross-Border CNP Fraud: Card-not-present transactions from impossible locations
- Account Takeover: Rapid location changes, unusual transaction patterns, new recipients
- Velocity Fraud: Multiple transactions in rapid succession, unusual amounts
- Geographic Impossibility: Transactions from locations physically impossible to reach
- Merchant Category Fraud: High-risk categories (gambling, adult content, crypto)

**Analysis Protocol:**
For EVERY transaction you analyze, you must provide a JSON object with exactly these keys:
- "risk_score": integer from 0 to 100 (0=no risk, 100=definite fraud)
- "justification": clear, concise explanation for your score (max 200 words)
- "recommended_action": one of ["monitor", "alert", "lock_account", "block_transaction"]
- "confidence": your confidence in the assessment (0.0 to 1.0)

**Risk Score Guidelines:**
- 0-25: Normal transaction, no concerns
- 26-50: Low risk, some unusual patterns
- 51-75: Medium risk, multiple suspicious indicators
- 76-90: High risk, likely fraudulent activity
- 91-100: Extreme risk, definite fraud - immediate action required

**Context Integration:**
Use the user's historical data to establish baseline behavior. Consider:
- Typical transaction amounts and frequency
- Usual geographic patterns and login locations  
- Previous recipient patterns and new beneficiaries
- Time-of-day and day-of-week patterns
- Device and IP address consistency

Be thorough but decisive. Financial security depends on your analysis."""

def create_analyst_agent() -> LlmAgent:
    """Create the Vigil Analyst Agent with MCP tools and fraud detection capabilities."""
    
    # Ensure MCP server path exists
    if not os.path.exists(MCP_SERVER_PATH):
        logger.warning(f"MCP server not found at {MCP_SERVER_PATH}, using relative path")
        mcp_server_path = "./vigil_mcp_lowlevel.py"
    else:
        mcp_server_path = MCP_SERVER_PATH
    
    agent = LlmAgent(
        model='gemini-2.5-flash',
        name='vigil_analyst_agent',
        instruction=FRAUD_ANALYST_INSTRUCTION,
        tools=[
            MCPToolset(
                connection_params=StdioConnectionParams(
                    server_params=StdioServerParameters(
                        command='python3',
                        args=[mcp_server_path, '--transport', 'stdio']
                    )
                ),
                # Analyst only needs read access and account locking capability
                tool_filter=['get_transactions', 'get_user_details', 'lock_account']
            )
        ],
        # Enable A2A communication
        a2a_port=ANALYST_PORT
    )
    
    return agent


class TransactionAnalyzer:
    """Enhanced transaction analysis with contextual data enrichment."""
    
    def __init__(self, agent: LlmAgent):
        self.agent = agent
        self.analysis_cache = {}  # Simple cache to avoid re-analyzing identical transactions
    
    async def analyze_transaction(self, transaction_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Perform comprehensive fraud analysis on a transaction.
        
        Args:
            transaction_data: Transaction details from Observer agent
            
        Returns:
            Risk assessment with score, justification, and recommended action
        """
        try:
            transaction_id = transaction_data.get('transaction_id', 'unknown')
            account_id = transaction_data.get('from_account', transaction_data.get('account_id'))
            user_id = transaction_data.get('user_id')
            
            logger.info(f"Starting analysis for transaction {transaction_id}")
            
            # Check cache first
            cache_key = self._generate_cache_key(transaction_data)
            if cache_key in self.analysis_cache:
                logger.info(f"Returning cached analysis for transaction {transaction_id}")
                return self.analysis_cache[cache_key]
            
            # Enrich transaction data with user context
            enriched_data = await self._enrich_transaction_data(transaction_data)
            
            # Prepare structured prompt for Gemini
            analysis_prompt = self._build_analysis_prompt(enriched_data)
            
            # Get fraud assessment from Gemini via ADK
            assessment_response = await self.agent.prompt_model(analysis_prompt)
            assessment = self._parse_assessment_response(assessment_response, transaction_id)
            
            # Cache the result
            self.analysis_cache[cache_key] = assessment
            
            # Add metadata
            assessment['transaction_id'] = transaction_id
            assessment['analysis_timestamp'] = datetime.utcnow().isoformat()
            assessment['analyst_version'] = 'vigil-1.0'
            
            logger.info(f"Analysis complete for transaction {transaction_id}: "
                       f"Risk Score {assessment['risk_score']}, "
                       f"Action: {assessment['recommended_action']}")
            
            return assessment
            
        except Exception as e:
            logger.error(f"Error analyzing transaction {transaction_id}: {e}")
            # Return safe fallback assessment
            return {
                'risk_score': 50,  # Medium risk when analysis fails
                'justification': f'Analysis failed: {str(e)}. Manual review required.',
                'recommended_action': 'alert',
                'confidence': 0.1,
                'error': str(e)
            }
    
    async def _enrich_transaction_data(self, transaction_data: Dict[str, Any]) -> Dict[str, Any]:
        """Enrich transaction with user historical data and context."""
        enriched = transaction_data.copy()
        
        try:
            account_id = transaction_data.get('from_account', transaction_data.get('account_id'))
            user_id = transaction_data.get('user_id')
            
            # Get user details if we have user_id
            if user_id:
                user_details_prompt = f"Get user details for user ID: {user_id}"
                user_response = await self.agent.prompt_model(user_details_prompt)
                enriched['user_context'] = user_response
            
            # Get recent transaction history if we have account_id
            if account_id:
                history_prompt = f"Get recent transactions for account: {account_id}"
                history_response = await self.agent.prompt_model(history_prompt)
                enriched['transaction_history'] = history_response
                
        except Exception as e:
            logger.warning(f"Could not enrich transaction data: {e}")
            enriched['enrichment_error'] = str(e)
        
        return enriched
    
    def _build_analysis_prompt(self, transaction_data: Dict[str, Any]) -> str:
        """Build a structured analysis prompt for Gemini."""
        
        # Extract key transaction details
        amount = transaction_data.get('amount', 0)
        from_account = transaction_data.get('from_account', 'unknown')
        to_account = transaction_data.get('to_account', 'unknown')
        timestamp = transaction_data.get('timestamp', datetime.utcnow().isoformat())
        transaction_type = transaction_data.get('type', 'transfer')
        
        # Build the analysis prompt
        prompt = f"""
FRAUD ANALYSIS REQUEST

Transaction Details:
- Amount: {amount} (currency units)
- From Account: {from_account}
- To Account: {to_account}
- Type: {transaction_type}
- Timestamp: {timestamp}

User Context:
{json.dumps(transaction_data.get('user_context', {}), indent=2)}

Recent Transaction History:
{json.dumps(transaction_data.get('transaction_history', {}), indent=2)}

ANALYSIS REQUIRED:
Please analyze this transaction for fraud risk considering all available context.
Return your assessment as a JSON object with the exact format specified in your instructions.

Focus particularly on:
1. Transaction amount vs. user's historical patterns
2. Geographic and temporal plausibility
3. Recipient patterns (new vs. known beneficiaries)
4. Transaction velocity and frequency patterns
5. Latin American regional fraud indicators

JSON Response Required:
"""
        
        return prompt
    
    def _parse_assessment_response(self, response: str, transaction_id: str) -> Dict[str, Any]:
        """Parse Gemini's assessment response into structured format."""
        try:
            # Try to extract JSON from the response
            if '{' in response and '}' in response:
                json_start = response.find('{')
                json_end = response.rfind('}') + 1
                json_str = response[json_start:json_end]
                assessment = json.loads(json_str)
                
                # Validate required fields
                required_fields = ['risk_score', 'justification', 'recommended_action', 'confidence']
                for field in required_fields:
                    if field not in assessment:
                        raise ValueError(f"Missing required field: {field}")
                
                # Validate risk score range
                risk_score = assessment['risk_score']
                if not isinstance(risk_score, int) or risk_score < 0 or risk_score > 100:
                    raise ValueError(f"Invalid risk_score: {risk_score}")
                
                # Validate confidence range
                confidence = assessment['confidence']
                if not isinstance(confidence, (int, float)) or confidence < 0 or confidence > 1:
                    raise ValueError(f"Invalid confidence: {confidence}")
                
                return assessment
            else:
                raise ValueError("No JSON found in response")
                
        except Exception as e:
            logger.error(f"Failed to parse assessment for transaction {transaction_id}: {e}")
            logger.error(f"Raw response: {response}")
            
            # Return fallback assessment
            return {
                'risk_score': 50,
                'justification': f'Unable to parse model response: {str(e)}. Manual review required.',
                'recommended_action': 'alert',
                'confidence': 0.1,
                'parse_error': str(e),
                'raw_response': response[:500]  # Truncated for logging
            }
    
    def _generate_cache_key(self, transaction_data: Dict[str, Any]) -> str:
        """Generate a cache key for identical transactions."""
        key_fields = ['from_account', 'to_account', 'amount', 'timestamp', 'type']
        key_parts = []
        
        for field in key_fields:
            value = transaction_data.get(field, '')
            key_parts.append(f"{field}:{value}")
        
        return "|".join(key_parts)


# A2A Communication Handler
async def handle_transaction_analysis_request(request_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    A2A endpoint handler for receiving transaction analysis requests from Observer agent.
    
    Args:
        request_data: Transaction data from Observer agent
        
    Returns:
        Analysis result, and forwards high-risk cases to Actuator agent
    """
    logger.info(f"Received transaction analysis request: {request_data.get('transaction_id', 'unknown')}")
    
    # Create analyzer instance
    agent = create_analyst_agent()
    analyzer = TransactionAnalyzer(agent)
    
    # Perform analysis
    assessment = await analyzer.analyze_transaction(request_data)
    
    # Check if we need to alert the Actuator agent
    risk_score = assessment.get('risk_score', 0)
    if risk_score >= RISK_THRESHOLD:
        logger.warning(f"HIGH RISK DETECTED: Score {risk_score} for transaction "
                      f"{request_data.get('transaction_id', 'unknown')}")
        
        # Forward to Actuator agent via A2A
        await forward_to_actuator(request_data, assessment)
    
    return assessment


async def forward_to_actuator(transaction_data: Dict[str, Any], assessment: Dict[str, Any]):
    """Forward high-risk assessment to Actuator agent for protective action."""
    try:
        actuator_payload = {
            'transaction_data': transaction_data,
            'assessment': assessment,
            'source': 'vigil_analyst',
            'timestamp': datetime.utcnow().isoformat()
        }
        
        # Send to Actuator agent (this would be implemented with actual A2A communication)
        logger.info(f"Forwarding high-risk alert to Actuator: {assessment['recommended_action']}")
        
        # For now, log the action that would be taken
        # In a real implementation, this would use ADK's A2A client
        
    except Exception as e:
        logger.error(f"Failed to forward alert to Actuator: {e}")


# Main agent instance for synchronous deployment
root_agent = create_analyst_agent()


# Async agent creation for development
async def get_agent_async():
    """Create agent for adk web development environment."""
    return create_analyst_agent()


if __name__ == "__main__":
    # For testing purposes
    import asyncio
    
    async def test_analysis():
        """Test the fraud analysis functionality."""
        agent = create_analyst_agent()
        analyzer = TransactionAnalyzer(agent)
        
        # Test transaction data
        test_transaction = {
            'transaction_id': 'tx_test_001',
            'from_account': '1234567890',
            'to_account': '0987654321',
            'amount': 1500.00,
            'type': 'pix_transfer',
            'timestamp': datetime.utcnow().isoformat(),
            'user_id': 'user_123',
            'location': 'São Paulo, BR'
        }
        
        logger.info("Testing fraud analysis...")
        result = await analyzer.analyze_transaction(test_transaction)
        
        print("\nFraud Analysis Result:")
        print(json.dumps(result, indent=2))
    
    # Run test
    asyncio.run(test_analysis())