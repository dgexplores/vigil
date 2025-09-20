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

from google.adk.agents import LlmAgent
from google.adk.rpc import A2AServer, rpc
from google.adk.models import Gemini

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Get config from environment variables
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")

CRITIC_PROMPT = """
You are a skeptical risk analyst. Your role is to challenge the findings in this case file.
Find evidence that contradicts the suspicion of fraud.
Identify legitimate alternative explanations for the observed behavior.
Conclude with a 'concur' or 'dissent' verdict.
Your final response must be a JSON object containing a single key "verdict" with a value of either "concur" or "dissent".
"""

class CriticService:
    def __init__(self):
        logger.info("Initializing CriticService...")
        self.llm_agent = LlmAgent(
            model=Gemini(api_key=GEMINI_API_KEY),
            instruction=CRITIC_PROMPT,
        )
        logger.info("CriticService initialized.")

    @rpc
    def critique_case(self, case_file_data: dict) -> dict:
        """
        Receives a case file, uses an LLM to critique it, and returns a verdict.
        """
        logger.info("Received request to critique case file.")

        prompt = (
            "Please critique the following fraud investigation case file:\n"
            f"{json.dumps(case_file_data, indent=2)}\n\n"
            "Based on your analysis, provide your verdict as a JSON object."
        )

        try:
            logger.info("Sending case file to LLM for critique...")
            llm_response = self.llm_agent.send(prompt)
            cleaned_response = llm_response.strip().replace("```json", "").replace("```", "").strip()
            verdict = json.loads(cleaned_response)
            logger.info(f"Received verdict from LLM: {verdict}")
        except Exception as e:
            logger.error(f"Error processing LLM response: {e}", exc_info=True)
            return {"error": f"Failed to get verdict from LLM: {e}", "llm_response": llm_response}

        return verdict

def main():
    """Entry point for the agent."""
    logger.info("Starting CriticAgent...")
    try:
        service = CriticService()
        server = A2AServer(service)
        server.start()
    except Exception as e:
        logger.fatal(f"Failed to start CriticAgent: {e}", exc_info=True)

if __name__ == "__main__":
    main()
