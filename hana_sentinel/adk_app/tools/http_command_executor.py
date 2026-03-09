"""
HTTP Command Execution Client
==============================

Alternative connection method for executing commands on remote instances
when SSH/gcloud access is not available.

Connects to remote_exec_server.py running on the target instance.
"""

import os
import logging
import requests
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


class HTTPCommandExecutor:
    """Execute commands via HTTP API instead of SSH"""

    def __init__(
        self,
        base_url: str = None,
        api_key: str = None,
        timeout: int = 60
    ):
        """
        Initialize HTTP command executor.

        Args:
            base_url: Base URL of remote exec server (e.g., http://10.238.36.146:9999)
            api_key: API key for authentication
            timeout: Request timeout in seconds
        """
        self.base_url = base_url or os.getenv("REMOTE_EXEC_URL", "")
        self.api_key = api_key or os.getenv("REMOTE_EXEC_API_KEY", "")
        self.timeout = timeout

        if not self.base_url:
            logger.warning("REMOTE_EXEC_URL not configured")
        if not self.api_key:
            logger.warning("REMOTE_EXEC_API_KEY not configured")

    def is_configured(self) -> bool:
        """Check if HTTP executor is properly configured"""
        return bool(self.base_url and self.api_key)

    def health_check(self) -> Dict[str, Any]:
        """Test connection to remote server"""
        if not self.is_configured():
            return {
                "status": "error",
                "error": "HTTP executor not configured"
            }

        try:
            response = requests.get(
                f"{self.base_url}/health",
                headers={"X-API-Key": self.api_key},
                timeout=10
            )

            if response.status_code == 200:
                return {
                    "status": "success",
                    "data": response.json()
                }
            else:
                return {
                    "status": "error",
                    "error": f"HTTP {response.status_code}: {response.text}"
                }

        except requests.exceptions.ConnectionError:
            return {
                "status": "error",
                "error": "Connection refused - is remote server running?"
            }
        except Exception as e:
            return {
                "status": "error",
                "error": str(e)
            }

    def get_node_info(self) -> Dict[str, Any]:
        """Get complete node architecture information"""
        if not self.is_configured():
            return {"status": "error", "error": "Not configured"}

        try:
            response = requests.get(
                f"{self.base_url}/node/info",
                headers={"X-API-Key": self.api_key},
                timeout=30
            )

            if response.status_code == 200:
                return {"status": "success", "data": response.json()}
            else:
                return {"status": "error", "error": f"HTTP {response.status_code}"}
        except Exception as e:
            return {"status": "error", "error": str(e)}

    def get_node_capabilities(self) -> Dict[str, Any]:
        """Get node capabilities"""
        if not self.is_configured():
            return {"status": "error", "error": "Not configured"}

        try:
            response = requests.get(
                f"{self.base_url}/node/capabilities",
                headers={"X-API-Key": self.api_key},
                timeout=10
            )

            if response.status_code == 200:
                return {"status": "success", "data": response.json()}
            else:
                return {"status": "error", "error": f"HTTP {response.status_code}"}
        except Exception as e:
            return {"status": "error", "error": str(e)}

    def get_system_health(self) -> Dict[str, Any]:
        """Get real-time system health (observability)"""
        if not self.is_configured():
            return {"status": "error", "error": "Not configured"}

        try:
            response = requests.get(
                f"{self.base_url}/observability/system-health",
                headers={"X-API-Key": self.api_key},
                timeout=30
            )

            if response.status_code == 200:
                return {"status": "success", "data": response.json()}
            else:
                return {"status": "error", "error": f"HTTP {response.status_code}"}
        except Exception as e:
            return {"status": "error", "error": str(e)}

    def get_resource_utilization(self) -> Dict[str, Any]:
        """Get resource utilization analysis"""
        if not self.is_configured():
            return {"status": "error", "error": "Not configured"}

        try:
            response = requests.get(
                f"{self.base_url}/observability/resource-utilization",
                headers={"X-API-Key": self.api_key},
                timeout=30
            )

            if response.status_code == 200:
                return {"status": "success", "data": response.json()}
            else:
                return {"status": "error", "error": f"HTTP {response.status_code}"}
        except Exception as e:
            return {"status": "error", "error": str(e)}

    def run_diagnostics(self) -> Dict[str, Any]:
        """Run all diagnostic checks on the remote node"""
        if not self.is_configured():
            return {"status": "error", "error": "Not configured"}

        try:
            response = requests.get(
                f"{self.base_url}/diagnostics",
                headers={"X-API-Key": self.api_key},
                timeout=60
            )

            if response.status_code == 200:
                return {"status": "success", "data": response.json()}
            else:
                return {"status": "error", "error": f"HTTP {response.status_code}"}
        except Exception as e:
            return {"status": "error", "error": str(e)}

    def get_diagnostics_summary(self) -> Dict[str, Any]:
        """Get quick diagnostic summary"""
        if not self.is_configured():
            return {"status": "error", "error": "Not configured"}

        try:
            response = requests.get(
                f"{self.base_url}/diagnostics/summary",
                headers={"X-API-Key": self.api_key},
                timeout=30
            )

            if response.status_code == 200:
                return {"status": "success", "data": response.json()}
            else:
                return {"status": "error", "error": f"HTTP {response.status_code}"}
        except Exception as e:
            return {"status": "error", "error": str(e)}

    def get_capacity_analysis(self) -> Dict[str, Any]:
        """Get capacity and growth analysis"""
        if not self.is_configured():
            return {"status": "error", "error": "Not configured"}

        try:
            response = requests.get(
                f"{self.base_url}/capacity/growth-analysis",
                headers={"X-API-Key": self.api_key},
                timeout=30
            )

            if response.status_code == 200:
                return {"status": "success", "data": response.json()}
            else:
                return {"status": "error", "error": f"HTTP {response.status_code}"}
        except Exception as e:
            return {"status": "error", "error": str(e)}

    def get_backup_status(self) -> Dict[str, Any]:
        """Get backup status"""
        if not self.is_configured():
            return {"status": "error", "error": "Not configured"}

        try:
            response = requests.get(
                f"{self.base_url}/operational/backup-status",
                headers={"X-API-Key": self.api_key},
                timeout=10
            )

            if response.status_code == 200:
                return {"status": "success", "data": response.json()}
            else:
                return {"status": "error", "error": f"HTTP {response.status_code}"}
        except Exception as e:
            return {"status": "error", "error": str(e)}

    def get_version_info(self) -> Dict[str, Any]:
        """Get database version and configuration"""
        if not self.is_configured():
            return {"status": "error", "error": "Not configured"}

        try:
            response = requests.get(
                f"{self.base_url}/operational/version-info",
                headers={"X-API-Key": self.api_key},
                timeout=30
            )

            if response.status_code == 200:
                return {"status": "success", "data": response.json()}
            else:
                return {"status": "error", "error": f"HTTP {response.status_code}"}
        except Exception as e:
            return {"status": "error", "error": str(e)}

    def list_healing_options(self) -> Dict[str, Any]:
        """List available healing operations"""
        if not self.is_configured():
            return {"status": "error", "error": "Not configured"}

        try:
            response = requests.get(
                f"{self.base_url}/healing/options",
                headers={"X-API-Key": self.api_key},
                timeout=10
            )

            if response.status_code == 200:
                return {"status": "success", "data": response.json()}
            else:
                return {"status": "error", "error": f"HTTP {response.status_code}"}
        except Exception as e:
            return {"status": "error", "error": str(e)}

    def execute_healing(
        self,
        operation: str,
        dry_run: bool = True
    ) -> Dict[str, Any]:
        """Execute a healing operation"""
        if not self.is_configured():
            return {"status": "error", "error": "Not configured"}

        try:
            response = requests.post(
                f"{self.base_url}/healing/execute/{operation}",
                headers={"X-API-Key": self.api_key},
                params={"dry_run": dry_run},
                timeout=120
            )

            if response.status_code == 200:
                return {"status": "success", "data": response.json()}
            else:
                return {"status": "error", "error": f"HTTP {response.status_code}: {response.text}"}
        except Exception as e:
            return {"status": "error", "error": str(e)}

    def execute_command(
        self,
        command: str,
        timeout: Optional[int] = None,
        working_dir: Optional[str] = None,
        admin_override: bool = False,
    ) -> Dict[str, Any]:
        """
        Execute a command on the remote server.

        Args:
            command: Shell command to execute
            timeout: Command timeout (overrides default)
            working_dir: Working directory for command

        Returns:
            dict: {
                "status": "success" | "error",
                "exit_code": int,
                "output": str (stdout),
                "error": str (stderr),
                "execution_time": float
            }
        """
        if not self.is_configured():
            return {
                "status": "error",
                "exit_code": -1,
                "output": "",
                "error": "HTTP executor not configured (REMOTE_EXEC_URL and REMOTE_EXEC_API_KEY required)"
            }

        logger.info(f"Executing command via HTTP: {command[:100]}")

        try:
            payload = {
                "command": command,
                "timeout": timeout or self.timeout,
                "admin_override": admin_override,
            }

            if working_dir:
                payload["working_dir"] = working_dir

            response = requests.post(
                f"{self.base_url}/execute",
                json=payload,
                headers={"X-API-Key": self.api_key},
                timeout=(timeout or self.timeout) + 5  # Add buffer for HTTP timeout
            )

            if response.status_code == 200:
                result = response.json()
                return {
                    "status": result.get("status", "success"),
                    "exit_code": result.get("exit_code", 0),
                    "output": result.get("stdout", ""),
                    "error": result.get("stderr", ""),
                    "execution_time": result.get("execution_time", 0)
                }
            elif response.status_code == 403:
                return {
                    "status": "error",
                    "exit_code": -1,
                    "output": "",
                    "error": f"Authentication failed or command not allowed: {response.text}"
                }
            else:
                return {
                    "status": "error",
                    "exit_code": -1,
                    "output": "",
                    "error": f"HTTP {response.status_code}: {response.text}"
                }

        except requests.exceptions.Timeout:
            return {
                "status": "error",
                "exit_code": -1,
                "output": "",
                "error": f"Command timeout after {timeout or self.timeout}s"
            }
        except requests.exceptions.ConnectionError:
            return {
                "status": "error",
                "exit_code": -1,
                "output": "",
                "error": "Connection refused - check if remote server is running"
            }
        except Exception as e:
            logger.error(f"HTTP command execution failed: {e}")
            return {
                "status": "error",
                "exit_code": -1,
                "output": "",
                "error": str(e)
            }

    def execute_as_user(
        self,
        command: str,
        user: str = "",
        timeout: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Execute command as specific user (requires sudo on remote server).

        Args:
            command: Shell command to execute
            user: User to execute as
            timeout: Command timeout

        Returns:
            dict: Same format as execute_command()
        """
        user = user or os.getenv("GCP_TOOLKIT_HANA_USER", "")

        if not self.is_configured():
            return {
                "status": "error",
                "exit_code": -1,
                "output": "",
                "error": "HTTP executor not configured"
            }

        logger.info(f"Executing command as {user} via HTTP: {command[:100]}")

        try:
            payload = {
                "command": command,
                "timeout": timeout or self.timeout
            }

            response = requests.post(
                f"{self.base_url}/execute-as-user",
                json=payload,
                headers={"X-API-Key": self.api_key},
                params={"user": user},
                timeout=(timeout or self.timeout) + 5
            )

            if response.status_code == 200:
                result = response.json()
                return {
                    "status": result.get("status", "success"),
                    "exit_code": result.get("exit_code", 0),
                    "output": result.get("stdout", ""),
                    "error": result.get("stderr", ""),
                    "execution_time": result.get("execution_time", 0)
                }
            else:
                return {
                    "status": "error",
                    "exit_code": -1,
                    "output": "",
                    "error": f"HTTP {response.status_code}: {response.text}"
                }

        except Exception as e:
            logger.error(f"HTTP command execution failed: {e}")
            return {
                "status": "error",
                "exit_code": -1,
                "output": "",
                "error": str(e)
            }


# Global instance
_http_executor = None


def get_http_executor() -> HTTPCommandExecutor:
    """Get or create global HTTP executor instance"""
    global _http_executor
    if _http_executor is None:
        _http_executor = HTTPCommandExecutor()
    return _http_executor


def execute_http_command(command: str, timeout: int = 60, user: str = None) -> dict:
    """
    Execute command via HTTP (convenience function).

    Args:
        command: Shell command to execute
        timeout: Command timeout in seconds
        user: User to execute as (default: None uses server default)

    Returns dict compatible with ssh_execute format:
    {
        "output": str,
        "error": str,
        "exit_code": int,
        "status": str
    }
    """
    executor = get_http_executor()

    if not executor.is_configured():
        return {
            "output": "",
            "error": "HTTP command execution not configured",
            "exit_code": -1,
            "status": "not_configured"
        }

    if user:
        result = executor.execute_as_user(command, user=user, timeout=timeout)
    else:
        result = executor.execute_command(command, timeout=timeout)

    # Convert to ssh_execute compatible format
    return {
        "output": result.get("output", ""),
        "error": result.get("error", ""),
        "exit_code": result.get("exit_code", -1),
        "status": "success" if result.get("exit_code") == 0 else "error"
    }


def execute_hana_command(command: str, timeout: int = 60) -> dict:
    """
    Execute HANA command as zo3adm user.

    HANA commands (sapcontrol, HDB, hdbsql, etc.) require execution as the
    zo3adm user because:
    - HANA binaries are in zo3adm's PATH
    - Environment variables (HANA_HOME, etc.) are set in zo3adm's profile

    Args:
        command: HANA command to execute (e.g., 'sapcontrol -nr 00 -function GetProcessList')
        timeout: Command timeout in seconds

    Returns:
        dict: ssh_execute compatible format
    """
    executor = get_http_executor()
    hana_user = os.getenv("GCP_TOOLKIT_HANA_USER", "")

    if not executor.is_configured():
        return {
            "output": "",
            "error": "HTTP command execution not configured",
            "exit_code": -1,
            "status": "not_configured"
        }

    # Wrap command to source HANA environment
    # This ensures PATH and environment variables are set correctly
    wrapped_command = f"source ~/.bashrc 2>/dev/null; source ~/.profile 2>/dev/null; {command}"

    result = executor.execute_as_user(wrapped_command, user=hana_user, timeout=timeout)

    return {
        "output": result.get("output", ""),
        "error": result.get("error", ""),
        "exit_code": result.get("exit_code", -1),
        "status": "success" if result.get("exit_code") == 0 else "error"
    }
