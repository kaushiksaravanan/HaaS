from typing import Dict, Any
from ..tools.hana_tools import execute_remote_command


class RecoveryAgent:
    def __init__(self):
        self.name = "RecoveryAgent"
        self.description = "Handles service recovery and restarts."

    def restart_service(self, service_name: str) -> str:
        """
        Restarts a HANA service using sapcontrol via remote exec server.
        """
        command = f"sapcontrol -nr 00 -function RestartService {service_name}"
        try:
            result = execute_remote_command(command, admin_override=True)
            output = result.get("stdout", "")
            if "RestartService OK" in output:
                return f"Service {service_name} restarted successfully."
            else:
                return f"Failed to restart service {service_name}. Output: {output}"
        except Exception as e:
            return f"Error executing restart command: {e}"
