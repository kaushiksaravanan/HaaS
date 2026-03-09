"""
Browser-Use Agent for SAP Web Interface Automation.
Uses GenAIHub (SAP AI Core) as the LLM backend.
"""

from browser_use import Agent as BrowserUseLibAgent, Controller
import asyncio
from typing import Dict, Any

# Import GenAIHub LangChain wrapper
from ..chat_genaihub import ChatGenAIHub, get_chat_model


class BrowserUseAgent:
    """Browser automation agent using GenAIHub as the LLM backend."""

    def __init__(self):
        self.name = "BrowserUseAgent"
        self.description = "Automates interaction with SAP web interfaces."
        # Initialize the model using GenAIHub
        self.llm = ChatGenAIHub()
        self.controller = Controller()

    async def navigate_and_extract(self, task: str) -> str:
        """
        Uses browser-use to perform a task.

        Args:
            task: Description of the browser task to perform

        Returns:
            Result text from the browser automation
        """
        agent = BrowserUseLibAgent(task=task, llm=self.llm, controller=self.controller)

        try:
            history = await agent.run()
            result = history.final_result()
            return result if result else "Task completed but no text returned."
        except Exception as e:
            return f"Browser task failed: {e}"

    def run_task(self, task_description: str) -> str:
        """
        Synchronous wrapper for async browser task.

        Args:
            task_description: Description of the browser task

        Returns:
            Result from the browser automation
        """
        return asyncio.run(self.navigate_and_extract(task_description))
