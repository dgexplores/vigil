#!/usr/bin/env python3
"""
Vigil Actuator Agent - Protective Action Executor

This agent receives high-risk fraud alerts from the Analyst agent and takes
immediate protective actions like locking accounts, blocking transactions,
and notifying security teams.
"""

import asyncio
import json
import logging
import os
from typing import Any, Dict, List, Optional
from datetime import datetime
from enum import Enum

from google.adk.agents import Agent
from google.adk.tools.mcp_tool.mcp_toolset import MCPToolset
from google.adk.tools.mcp_tool.mcp_session_manager import StdioConnectionParams
from mcp import StdioServerParameters

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Configuration from environment
MCP_SERVER_PATH = os.getenv('MCP_SERVER_PATH', '/app/vigil_mcp_lowlevel.py')
ACTUATOR_PORT = int(os.getenv('ACTUATOR_PORT', '8002'))
AUTO_EXECUTE_ACTIONS = os.getenv('AUTO_EXECUTE_ACTIONS', 'false').lower() == 'true'

class ActionType(Enum):
    """Enumeration of available protective actions."""
    MONITOR = "monitor"
    ALERT = "alert"
    LOCK_ACCOUNT = "lock_account"
    BLOCK_TRANSACTION = "block_transaction"
    NOTIFY_SECURITY = "notify_security"
    TEMPORARY_HOLD = "temporary_hold"
    REQUEST_VERIFICATION = "request_verification"

class ActionStatus(Enum):
    """Status of action execution."""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"

def create_actuator_agent() -> Agent:
    """Create the Vigil Actuator Agent with protective action capabilities."""
    
    # Ensure MCP server path exists
    if not os.path.exists(MCP_SERVER_PATH):
        logger.warning(f"MCP server not found at {MCP_SERVER_PATH}, using relative path")
        mcp_server_path = "./vigil_mcp_lowlevel.py"
    else:
        mcp_server_path = MCP_SERVER_PATH
    
    agent = Agent(
        name='vigil_actuator_agent',
        tools=[
            MCPToolset(
                connection_params=StdioConnectionParams(
                    server_params=StdioServerParameters(
                        command='python3',
                        args=[mcp_server_path, '--transport', 'stdio']
                    )
                ),
                # Actuator needs full access to execute protective actions
                tool_filter=['lock_account', 'unlock_account', 'get_user_details', 'send_notification']
            )
        ],
        # Enable A2A communication to receive alerts from Analyst
        a2a_port=ACTUATOR_PORT
    )
    
    return agent


class ActionExecutor:
    """Executes protective actions based on fraud alerts."""
    
    def __init__(self, agent: Agent):
        self.agent = agent
        self.action_history = []  # Track executed actions
        self.pending_verifications = {}  # Track verification requests
    
    async def handle_fraud_alert(self, alert_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Main handler for fraud alerts from the Analyst agent.
        
        Args:
            alert_data: Complete alert data including transaction and assessment
            
        Returns:
            Execution result with actions taken
        """
        try:
            alert_id = f"alert_{datetime.utcnow().timestamp()}"
            logger.info(f"Processing fraud alert {alert_id}")
            
            # Extract key information
            transaction_data = alert_data.get('transaction_data', {})
            assessment = alert_data.get('assessment', {})
            
            transaction_id = transaction_data.get('transaction_id', 'unknown')
            risk_score = assessment.get('risk_score', 0)
            recommended_action = assessment.get('recommended_action', 'monitor')
            
            logger.warning(f"HIGH RISK ALERT: Transaction {transaction_id}, "
                          f"Risk Score: {risk_score}, "
                          f"Recommended Action: {recommended_action}")
            
            # Determine and execute appropriate actions
            actions_to_execute = self._determine_actions(assessment, transaction_data)
            execution_results = []
            
            for action in actions_to_execute:
                try:
                    result = await self._execute_action(action, transaction_data, assessment)
                    execution_results.append(result)
                    
                    # Log the action taken
                    self.action_history.append({
                        'alert_id': alert_id,
                        'transaction_id': transaction_id,
                        'action': action.value,
                        'result': result,
                        'timestamp': datetime.utcnow().isoformat()
                    })
                    
                except Exception as e:
                    logger.error(f"Failed to execute action {action.value}: {e}")
                    execution_results.append({
                        'action': action.value,
                        'status': ActionStatus.FAILED.value,
                        'error': str(e)
                    })
            
            # Prepare response
            response = {
                'alert_id': alert_id,
                'transaction_id': transaction_id,
                'risk_score': risk_score,
                'actions_executed': execution_results,
                'response_timestamp': datetime.utcnow().isoformat(),
                'actuator_version': 'vigil-1.0'
            }
            
            logger.info(f"Completed processing alert {alert_id} with {len(execution_results)} actions")
            return response
            
        except Exception as e:
            logger.error(f"Error handling fraud alert: {e}")
            return {
                'error': str(e),
                'status': 'failed',
                'timestamp': datetime.utcnow().isoformat()
            }
    
    def _determine_actions(self, assessment: Dict[str, Any], transaction_data: Dict[str, Any]) -> List[ActionType]:
        """
        Determine which protective actions to take based on risk assessment.
        
        Args:
            assessment: Risk assessment from Analyst
            transaction_data: Transaction details
            
        Returns:
            List of actions to execute
        """
        actions = []
        
        risk_score = assessment.get('risk_score', 0)
        recommended_action = assessment.get('recommended_action', 'monitor')
        confidence = assessment.get('confidence', 0.0)
        
        # Always start with alerting
        actions.append(ActionType.ALERT)
        
        # Determine additional actions based on risk level and confidence
        if risk_score >= 90 and confidence >= 0.8:
            # Extremely high risk with high confidence - immediate lockdown
            actions.extend([
                ActionType.LOCK_ACCOUNT,
                ActionType.BLOCK_TRANSACTION,
                ActionType.NOTIFY_SECURITY
            ])
            
        elif risk_score >= 75 and confidence >= 0.6:
            # High risk - protective measures
            if recommended_action == "lock_account":
                actions.append(ActionType.LOCK_ACCOUNT)
            elif recommended_action == "block_transaction":
                actions.append(ActionType.BLOCK_TRANSACTION)
            else:
                # Default high-risk action
                actions.append(ActionType.TEMPORARY_HOLD)
            
            actions.append(ActionType.NOTIFY_SECURITY)
            
        elif risk_score >= 60:
            # Medium-high risk - verification required
            actions.extend([
                ActionType.REQUEST_VERIFICATION,
                ActionType.TEMPORARY_HOLD
            ])
            
        elif risk_score >= 40:
            # Medium risk - enhanced monitoring
            actions.append(ActionType.MONITOR)
        
        # Remove duplicates while preserving order
        unique_actions = []
        for action in actions:
            if action not in unique_actions:
                unique_actions.append(action)
        
        return unique_actions
    
    async def _execute_action(self, action: ActionType, transaction_data: Dict[str, Any], 
                            assessment: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute a specific protective action.
        
        Args:
            action: The action to execute
            transaction_data: Transaction details
            assessment: Risk assessment
            
        Returns:
            Execution result
        """
        try:
            account_id = transaction_data.get('from_account', '')
            user_id = transaction_data.get('user_id', '')
            transaction_id = transaction_data.get('transaction_id', '')
            
            logger.info(f"Executing action: {action.value} for transaction {transaction_id}")
            
            if action == ActionType.ALERT:
                return await self._execute_alert_action(transaction_data, assessment)
                
            elif action == ActionType.LOCK_ACCOUNT:
                return await self._execute_lock_account(account_id, user_id, assessment)
                
            elif action == ActionType.BLOCK_TRANSACTION:
                return await self._execute_block_transaction(transaction_id, assessment)
                
            elif action == ActionType.NOTIFY_SECURITY:
                return await self._execute_notify_security(transaction_data, assessment)
                
            elif action == ActionType.TEMPORARY_HOLD:
                return await self._execute_temporary_hold(account_id, transaction_id, assessment)
                
            elif action == ActionType.REQUEST_VERIFICATION:
                return await self._execute_request_verification(user_id, transaction_data, assessment)
                
            elif action == ActionType.MONITOR:
                return await self._execute_enhanced_monitoring(account_id, user_id, assessment)
                
            else:
                raise ValueError(f"Unknown action type: {action}")
                
        except Exception as e:
            logger.error(f"Error executing action {action.value}: {e}")
            return {
                'action': action.value,
                'status': ActionStatus.FAILED.value,
                'error': str(e),
                'timestamp': datetime.utcnow().isoformat()
            }
    
    async def _execute_alert_action(self, transaction_data: Dict[str, Any], 
                                  assessment: Dict[str, Any]) -> Dict[str, Any]:
        """Execute general alerting action."""
        try:
            # Log the alert
            alert_message = f"FRAUD ALERT: Transaction {transaction_data.get('transaction_id')} " \
                          f"flagged with risk score {assessment.get('risk_score')}. " \
                          f"Reason: {assessment.get('justification', 'Unknown')}"
            
            logger.warning(alert_message)
            
            return {
                'action': ActionType.ALERT.value,
                'status': ActionStatus.COMPLETED.value,
                'message': alert_message,
                'timestamp': datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            raise Exception(f"Alert action failed: {e}")
    
    async def _execute_lock_account(self, account_id: str, user_id: str, 
                                  assessment: Dict[str, Any]) -> Dict[str, Any]:
        """Execute account locking action."""
        try:
            if not account_id and not user_id:
                raise ValueError("Account ID or User ID required for account locking")
            
            # Use MCP tool to lock the account
            lock_prompt = f"Lock account: {account_id or user_id} due to suspected fraud. " \
                         f"Risk score: {assessment.get('risk_score')}. " \
                         f"Justification: {assessment.get('justification')}"
            
            if AUTO_EXECUTE_ACTIONS:
                response = await self.agent.prompt_model(lock_prompt)
                logger.info(f"Account lock executed: {response}")
                
                return {
                    'action': ActionType.LOCK_ACCOUNT.value,
                    'status': ActionStatus.COMPLETED.value,
                    'account_id': account_id,
                    'user_id': user_id,
                    'mcp_response': response,
                    'timestamp': datetime.utcnow().isoformat()
                }
            else:
                # In demo mode, just log the action
                logger.info(f"DEMO MODE: Would lock account {account_id or user_id}")
                return {
                    'action': ActionType.LOCK_ACCOUNT.value,
                    'status': ActionStatus.COMPLETED.value,
                    'account_id': account_id,
                    'user_id': user_id,
                    'message': 'Demo mode - account lock simulated',
                    'timestamp': datetime.utcnow().isoformat()
                }
                
        except Exception as e:
            raise Exception(f"Account lock failed: {e}")
    
    async def _execute_block_transaction(self, transaction_id: str, 
                                       assessment: Dict[str, Any]) -> Dict[str, Any]:
        """Execute transaction blocking action."""
        try:
            if not transaction_id:
                raise ValueError("Transaction ID required for blocking")
            
            # In a real implementation, this would interface with the payment processor
            logger.warning(f"BLOCKING TRANSACTION: {transaction_id}")
            
            return {
                'action': ActionType.BLOCK_TRANSACTION.value,
                'status': ActionStatus.COMPLETED.value,
                'transaction_id': transaction_id,
                'message': f'Transaction {transaction_id} blocked due to fraud risk',
                'timestamp': datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            raise Exception(f"Transaction block failed: {e}")
    
    async def _execute_notify_security(self, transaction_data: Dict[str, Any], 
                                     assessment: Dict[str, Any]) -> Dict[str, Any]:
        """Execute security team notification action."""
        try:
            # Prepare security notification
            notification = {
                'alert_type': 'FRAUD_DETECTION',
                'severity': 'HIGH',
                'transaction_id': transaction_data.get('transaction_id'),
                'risk_score': assessment.get('risk_score'),
                'justification': assessment.get('justification'),
                'account_id': transaction_data.get('from_account'),
                'amount': transaction_data.get('amount'),
                'timestamp': datetime.utcnow().isoformat()
            }
            
            # Use MCP tool to send notification
            if AUTO_EXECUTE_ACTIONS:
                notify_prompt = f"Send security notification: {json.dumps(notification)}"
                response = await self.agent.prompt_model(notify_prompt)
                
                return {
                    'action': ActionType.NOTIFY_SECURITY.value,
                    'status': ActionStatus.COMPLETED.value,
                    'notification': notification,
                    'mcp_response': response,
                    'timestamp': datetime.utcnow().isoformat()
                }
            else:
                # Demo mode
                logger.info(f"DEMO MODE: Security notification would be sent: {notification}")
                return {
                    'action': ActionType.NOTIFY_SECURITY.value,
                    'status': ActionStatus.COMPLETED.value,
                    'notification': notification,
                    'message': 'Demo mode - security notification simulated',
                    'timestamp': datetime.utcnow().isoformat()
                }
                
        except Exception as e:
            raise Exception(f"Security notification failed: {e}")
    
    async def _execute_temporary_hold(self, account_id: str, transaction_id: str,
                                    assessment: Dict[str, Any]) -> Dict[str, Any]:
        """Execute temporary hold action."""
        try:
            hold_duration = "24 hours"  # Standard temporary hold duration
            
            logger.info(f"Placing {hold_duration} temporary hold on account {account_id}")
            
            return {
                'action': ActionType.TEMPORARY_HOLD.value,
                'status': ActionStatus.COMPLETED.value,
                'account_id': account_id,
                'transaction_id': transaction_id,
                'duration': hold_duration,
                'message': f'Temporary hold placed on account {account_id} for {hold_duration}',
                'timestamp': datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            raise Exception(f"Temporary hold failed: {e}")
    
    async def _execute_request_verification(self, user_id: str, transaction_data: Dict[str, Any],
                                          assessment: Dict[str, Any]) -> Dict[str, Any]:
        """Execute user verification request action."""
        try:
            verification_id = f"verify_{datetime.utcnow().timestamp()}"
            
            # Store pending verification
            self.pending_verifications[verification_id] = {
                'user_id': user_id,
                'transaction_data': transaction_data,
                'assessment': assessment,
                'created_at': datetime.utcnow().isoformat()
            }
            
            logger.info(f"Verification request {verification_id} created for user {user_id}")
            
            return {
                'action': ActionType.REQUEST_VERIFICATION.value,
                'status': ActionStatus.COMPLETED.value,
                'user_id': user_id,
                'verification_id': verification_id,
                'message': f'Verification requested for user {user_id}',
                'timestamp': datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            raise Exception(f"Verification request failed: {e}")
    
    async def _execute_enhanced_monitoring(self, account_id: str, user_id: str,
                                         assessment: Dict[str, Any]) -> Dict[str, Any]:
        """Execute enhanced monitoring action."""
        try:
            monitoring_duration = "7 days"  # Standard monitoring period
            
            logger.info(f"Enhanced monitoring activated for account {account_id} ({monitoring_duration})")
            
            return {
                'action': ActionType.MONITOR.value,
                'status': ActionStatus.COMPLETED.value,
                'account_id': account_id,
                'user_id': user_id,
                'duration': monitoring_duration,
                'message': f'Enhanced monitoring activated for {monitoring_duration}',
                'timestamp': datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            raise Exception(f"Enhanced monitoring failed: {e}")


# A2A Communication Handler
async def handle_fraud_alert(request_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    A2A endpoint handler for receiving fraud alerts from Analyst agent.
    
    Args:
        request_data: Alert data from Analyst agent
        
    Returns:
        Action execution results
    """
    logger.info("Received fraud alert from Analyst agent")
    
    # Create executor instance
    agent = create_actuator_agent()
    executor = ActionExecutor(agent)
    
    # Process the alert and execute actions
    result = await executor.handle_fraud_alert(request_data)
    
    return result


# Main agent instance for synchronous deployment
root_agent = create_actuator_agent()


# Async agent creation for development
async def get_agent_async():
    """Create agent for adk web development environment."""
    return create_actuator_agent()


if __name__ == "__main__":
    # For testing purposes
    import asyncio
    
    async def test_actuator():
        """Test the actuator functionality."""
        agent = create_actuator_agent()
        executor = ActionExecutor(agent)
        
        # Test alert data
        test_alert = {
            'transaction_data': {
                'transaction_id': 'tx_test_001',
                'from_account': '1234567890',
                'to_account': '0987654321',
                'amount': 1500.00,
                'user_id': 'user_123'
            },
            'assessment': {
                'risk_score': 85,
                'justification': 'High velocity transactions from unusual location',
                'recommended_action': 'lock_account',
                'confidence': 0.9
            },
            'source': 'vigil_analyst',
            'timestamp': datetime.utcnow().isoformat()
        }
        
        logger.info("Testing fraud alert handling...")
        result = await executor.handle_fraud_alert(test_alert)
        
        print("\nActuator Test Result:")
        print(json.dumps(result, indent=2))
    
    # Run test
    asyncio.run(test_actuator())