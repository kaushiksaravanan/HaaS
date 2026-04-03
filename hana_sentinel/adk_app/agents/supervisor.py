from typing import Dict, Any, List
import logging
from .health_agent import HealthAgent
from .backup_agent import BackupAgent
from .recovery_agent import RecoveryAgent
from .sql_tuning_agent import SQLTuningAgent
from .capacity_agent import CapacityAgent
from .browser_agent import BrowserUseAgent
from ..tools.hana_client import HanaClient
from ...config.config import Config

# Configure logging
logging.basicConfig(level=logging.INFO)


class SupervisorAgent:
    def __init__(self):
        self.config = Config()

        # Initialize Tools
        self.hana_client = HanaClient(
            self.config.HANA_HOST,
            self.config.HANA_PORT,
            self.config.HANA_USER,
            self.config.HANA_PASSWORD,
        )
        # Initialize Agents
        self.health_agent = HealthAgent(self.hana_client)
        self.backup_agent = BackupAgent(self.hana_client)
        self.recovery_agent = RecoveryAgent()
        self.sql_tuning_agent = SQLTuningAgent(self.hana_client)
        self.capacity_agent = CapacityAgent(self.hana_client)
        self.browser_agent = BrowserUseAgent(headless=False)

    def process_request(self, intent: str, params: Dict[str, Any] = {}) -> str:
        """
        Routes requests to the appropriate agent based on intent.
        Simple intent matching for this implementation.
        """
        logging.info(f"Processing intent: {intent}")

        if intent == "check_health":
            return str(self.health_agent.check_system_health())

        elif intent == "check_backup":
            return str(self.backup_agent.check_backup_status())

        elif intent == "trigger_backup":
            return self.backup_agent.trigger_backup(
                params.get("prefix", "manual_backup")
            )

        elif intent == "tune_sql":
            return str(self.sql_tuning_agent.find_expensive_statements())

        elif intent == "check_capacity":
            return str(self.capacity_agent.check_capacity_trends())

        elif intent == "browser_task":
            return self.browser_agent.run_task(params.get("task", ""))

        else:
            return "Unknown intent."

    def run(self):
        print("HANA Sentinel Supervisor Started. Ready for commands.")
        # Simple loop for demonstration
        while True:
            user_input = input("Enter command (or 'exit'): ")
            if user_input == "exit":
                break

            # Very basic NLU mapping
            intent = "unknown"
            params = {}

            if "health" in user_input:
                intent = "check_health"
            elif "backup status" in user_input:
                intent = "check_backup"
            elif "trigger backup" in user_input:
                intent = "trigger_backup"
            elif "tune" in user_input:
                intent = "tune_sql"
            elif "capacity" in user_input:
                intent = "check_capacity"
            elif "security" in user_input:
                intent = "security_audit"
            elif "browse" in user_input:
                intent = "browser_task"
                params["task"] = user_input.replace("browse", "").strip()

            response = self.process_request(intent, params)
            print(f"Agent Response: {response}")


if __name__ == "__main__":
    agent = SupervisorAgent()
    agent.run()
