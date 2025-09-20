# Copyright 2025 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import os
import logging
import json

from google.adk.rpc import A2AServer, rpc
from google.adk.tools import Toolbox

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Get config from environment variables
GENAL_TOOLBOX_URL = os.environ.get("GENAL_TOOLBOX_SERVICE_URL", "http://genal-toolbox-service")

class ActuatorService:
    def __init__(self):
        logger.info("Initializing ActuatorService...")
        self.toolbox = Toolbox(f"{GENAL_TOOLBOX_URL}")
        logger.info("ActuatorService initialized.")

    @rpc
    def execute_action(self, command_data: dict) -> dict:
        """
        Receives a command, executes the corresponding tool, and returns the status.
        """
        action = command_data.get("action")
        logger.info(f"Received request to execute action: {action}")

        if not action:
            logger.error("Missing 'action' in command data.")
            return {"status": "error", "message": "Missing 'action' in command"}

        if action == "lock_account":
            ext_user_id = command_data.get("ext_user_id")
            if not ext_user_id:
                logger.error("Missing 'ext_user_id' for lock_account action.")
                return {"status": "error", "message": "Missing 'ext_user_id' for lock_account action"}

            try:
                logger.info(f"Executing lock_account tool for ext_user_id: {ext_user_id}")
                response = self.toolbox.lock_account(ext_user_id=ext_user_id)

                # A more robust implementation would inspect the response for success.
                # For now, we assume success if no exception is thrown.
                logger.info(f"Successfully locked account for ext_user_id: {ext_user_id}")
                return {"status": "success", "details": f"Account locked for {ext_user_id}"}
            except Exception as e:
                logger.error(f"Error executing lock_account for ext_user_id {ext_user_id}: {e}", exc_info=True)
                return {"status": "error", "message": f"Failed to lock account: {e}"}
        else:
            logger.warning(f"Unknown action received: {action}")
            return {"status": "error", "message": f"Unknown action: {action}"}

def main():
    """Entry point for the agent."""
    logger.info("Starting ActuatorAgent...")
    try:
        service = ActuatorService()
        server = A2AServer(service)
        server.start()
    except Exception as e:
        logger.fatal(f"Failed to start ActuatorAgent: {e}", exc_info=True)

if __name__ == "__main__":
    main()
