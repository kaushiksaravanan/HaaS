"""
Instance Logger — Centralized logging for instance operations.
Follows toolkit logging conventions from START_HERE.txt.
"""

import os
import logging
from datetime import datetime
from typing import Dict, Any
from pathlib import Path

logger = logging.getLogger(__name__)


class InstanceLogger:
    """Centralized logger for instance monitoring and healing operations."""

    def __init__(self, log_dir: str = None):
        """Initialize instance logger.

        Args:
            log_dir: Directory for log files (defaults to logs/instance)
        """
        if log_dir is None:
            base_dir = Path(__file__).parent.parent.parent
            log_dir = base_dir / "logs" / "instance"

        self.log_dir = Path(log_dir)
        self.ensure_log_directory()

    def ensure_log_directory(self):
        """Ensure log directory exists."""
        try:
            self.log_dir.mkdir(parents=True, exist_ok=True)
            logger.info(f"Log directory ensured: {self.log_dir}")
        except Exception as e:
            logger.error(f"Failed to create log directory: {e}")

    def _get_log_file_path(self, log_type: str, identifier: str = None) -> Path:
        """Get log file path with timestamp.

        Args:
            log_type: Type of log (diagnostic, healing, verification, agent_actions)
            identifier: Optional identifier (SID, script name, etc.)

        Returns:
            Path object for log file
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        if identifier:
            filename = f"{log_type}_{identifier}_{timestamp}.log"
        else:
            filename = f"{log_type}_{timestamp}.log"

        return self.log_dir / filename

    def log_diagnostic(
        self,
        diagnostic_data: Dict[str, Any],
        sid: str = None
    ) -> str:
        """Log diagnostic results to file.

        Args:
            diagnostic_data: Diagnostic results dictionary
            sid: System ID (extracted from data if not provided)

        Returns:
            Path to log file
        """
        try:
            sid = sid or diagnostic_data.get('sid', 'UNKNOWN')
            log_file = self._get_log_file_path('diagnostic', sid)

            with open(log_file, 'w', encoding='utf-8') as f:
                f.write("=" * 80 + "\n")
                f.write("HANA INSTANCE DIAGNOSTIC REPORT\n")
                f.write("=" * 80 + "\n")
                f.write(f"Diagnostic ID: {diagnostic_data.get('diagnostic_id', 'N/A')}\n")
                f.write(f"Timestamp: {diagnostic_data.get('timestamp', 'N/A')}\n")
                f.write(f"Instance: {diagnostic_data.get('instance_name', 'N/A')}\n")
                f.write(f"SID: {sid}\n")
                f.write(f"Instance Number: {diagnostic_data.get('instance_number', 'N/A')}\n")
                f.write("=" * 80 + "\n\n")

                # Overall status
                f.write(f"Overall Status: {diagnostic_data.get('overall_status', 'UNKNOWN').upper()}\n")
                f.write(f"Issues Detected: {diagnostic_data.get('issue_count', 0)}\n\n")

                if diagnostic_data.get('issues_detected'):
                    f.write("ISSUES:\n")
                    for issue in diagnostic_data['issues_detected']:
                        f.write(f"  - {issue}\n")
                    f.write("\n")

                # Individual check results
                f.write("=" * 80 + "\n")
                f.write("DIAGNOSTIC CHECKS\n")
                f.write("=" * 80 + "\n\n")

                checks = diagnostic_data.get('checks', {})
                for check_name, check_result in checks.items():
                    f.write(f"\n{'─' * 80}\n")
                    f.write(f"CHECK: {check_name.upper()}\n")
                    f.write(f"{'─' * 80}\n")
                    f.write(f"Status: {check_result.get('status', 'unknown')}\n")
                    f.write(f"Severity: {check_result.get('severity', 'info')}\n")

                    # Write check-specific details
                    for key, value in check_result.items():
                        if key not in ['status', 'severity', 'check']:
                            f.write(f"{key}: {value}\n")

                f.write("\n" + "=" * 80 + "\n")
                f.write(f"Diagnostic completed: {datetime.now().isoformat()}\n")
                f.write(f"Log file: {log_file}\n")
                f.write("=" * 80 + "\n")

            logger.info(f"Diagnostic log written: {log_file}")
            return str(log_file)

        except Exception as e:
            logger.error(f"Failed to write diagnostic log: {e}")
            return ""

    def log_healing(
        self,
        healing_data: Dict[str, Any],
        script_name: str = None
    ) -> str:
        """Log healing execution to file.

        Args:
            healing_data: Healing execution results
            script_name: Name of healing script

        Returns:
            Path to log file
        """
        try:
            script_name = script_name or healing_data.get('script', 'UNKNOWN')
            log_file = self._get_log_file_path('healing', script_name)

            with open(log_file, 'w', encoding='utf-8') as f:
                f.write("=" * 80 + "\n")
                f.write("HANA INSTANCE HEALING EXECUTION LOG\n")
                f.write("=" * 80 + "\n")
                f.write(f"Script: {script_name}\n")
                f.write(f"Status: {healing_data.get('status', 'UNKNOWN').upper()}\n")
                f.write(f"Risk Level: {healing_data.get('risk_level', 'MEDIUM')}\n")
                f.write(f"Start Time: {healing_data.get('timestamp', 'N/A')}\n")
                f.write(f"Completion Time: {healing_data.get('completion_time', 'N/A')}\n")
                f.write("=" * 80 + "\n\n")

                # Execution steps
                if healing_data.get('steps'):
                    f.write("EXECUTION STEPS:\n")
                    f.write("─" * 80 + "\n")
                    for idx, step in enumerate(healing_data['steps'], 1):
                        f.write(f"{idx}. {step}\n")
                    f.write("\n")

                # Fixes applied
                if healing_data.get('fixes_applied') or healing_data.get('keys_fixed'):
                    f.write("FIXES APPLIED:\n")
                    f.write("─" * 80 + "\n")
                    fixes = healing_data.get('fixes_applied', []) + healing_data.get('keys_fixed', [])
                    for fix in fixes:
                        f.write(f"  ✓ {fix}\n")
                    f.write("\n")

                # Failures
                if healing_data.get('fixes_failed') or healing_data.get('keys_failed'):
                    f.write("FAILURES:\n")
                    f.write("─" * 80 + "\n")
                    failures = healing_data.get('fixes_failed', []) + healing_data.get('keys_failed', [])
                    for failure in failures:
                        if isinstance(failure, dict):
                            f.write(f"  ✗ {failure.get('fix', failure.get('key', 'Unknown'))}: {failure.get('error', failure.get('reason', 'Unknown error'))}\n")
                        else:
                            f.write(f"  ✗ {failure}\n")
                    f.write("\n")

                # Error
                if healing_data.get('error'):
                    f.write(f"ERROR: {healing_data['error']}\n\n")

                f.write("=" * 80 + "\n")
                f.write(f"Healing log completed: {datetime.now().isoformat()}\n")
                f.write(f"Log file: {log_file}\n")
                f.write("=" * 80 + "\n")

            logger.info(f"Healing log written: {log_file}")
            return str(log_file)

        except Exception as e:
            logger.error(f"Failed to write healing log: {e}")
            return ""

    def log_verification(
        self,
        verification_data: Dict[str, Any],
        script_name: str = None
    ) -> str:
        """Log verification results to file.

        Args:
            verification_data: Verification results
            script_name: Name of healing script that was verified

        Returns:
            Path to log file
        """
        try:
            script_name = script_name or verification_data.get('script', 'UNKNOWN')
            log_file = self._get_log_file_path('verification', script_name)

            with open(log_file, 'w', encoding='utf-8') as f:
                f.write("=" * 80 + "\n")
                f.write("HANA INSTANCE HEALING VERIFICATION LOG\n")
                f.write("=" * 80 + "\n")
                f.write(f"Script: {script_name}\n")
                f.write(f"Verification Status: {verification_data.get('overall_status', 'UNKNOWN').upper()}\n")
                f.write(f"Timestamp: {verification_data.get('timestamp', 'N/A')}\n")
                f.write(f"Checks Passed: {verification_data.get('checks_passed', 0)}\n")
                f.write(f"Checks Failed: {verification_data.get('checks_failed', 0)}\n")
                f.write("=" * 80 + "\n\n")

                # Verification checks
                if verification_data.get('verification_checks'):
                    f.write("VERIFICATION CHECKS:\n")
                    f.write("─" * 80 + "\n")
                    for check in verification_data['verification_checks']:
                        status_icon = "✓" if check['status'] == 'pass' else "✗"
                        f.write(f"{status_icon} {check['check']}: {check['status'].upper()}\n")
                        if check.get('value'):
                            f.write(f"  Value: {check['value']}\n")
                    f.write("\n")

                # Error
                if verification_data.get('error'):
                    f.write(f"ERROR: {verification_data['error']}\n\n")

                f.write("=" * 80 + "\n")
                f.write(f"Verification log completed: {datetime.now().isoformat()}\n")
                f.write(f"Log file: {log_file}\n")
                f.write("=" * 80 + "\n")

            logger.info(f"Verification log written: {log_file}")
            return str(log_file)

        except Exception as e:
            logger.error(f"Failed to write verification log: {e}")
            return ""

    def log_agent_action(
        self,
        action_type: str,
        details: str,
        severity: str = "INFO",
        agent_name: str = None
    ) -> str:
        """Log agent action following toolkit format.

        Format: [TIMESTAMP] [SEVERITY] [ACTION_TYPE] [DETAILS]

        Args:
            action_type: Type of action (DETECTION, APPROVAL_REQUEST, EXECUTION, etc.)
            details: Action details
            severity: Log severity (INFO, WARNING, ERROR)
            agent_name: Name of agent performing action

        Returns:
            Path to log file
        """
        try:
            # Use daily log file for agent actions
            date_str = datetime.now().strftime("%Y%m%d")
            log_file = self.log_dir / f"agent_actions_{date_str}.log"

            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            agent_str = f" [{agent_name}]" if agent_name else ""

            log_line = f"[{timestamp}] [{severity}]{agent_str} [{action_type}] {details}\n"

            # Append to daily log file
            with open(log_file, 'a', encoding='utf-8') as f:
                f.write(log_line)

            return str(log_file)

        except Exception as e:
            logger.error(f"Failed to write agent action log: {e}")
            return ""

    def log_snapshot(
        self,
        snapshot_data: Dict[str, Any],
        instance_name: str = None
    ) -> str:
        """Log snapshot creation to file.

        Args:
            snapshot_data: Snapshot results
            instance_name: Instance name

        Returns:
            Path to log file
        """
        try:
            instance_name = instance_name or snapshot_data.get('instance', 'UNKNOWN')
            log_file = self._get_log_file_path('snapshot', instance_name)

            with open(log_file, 'w', encoding='utf-8') as f:
                f.write("=" * 80 + "\n")
                f.write("HANA INSTANCE VM SNAPSHOT LOG\n")
                f.write("=" * 80 + "\n")
                f.write(f"Instance: {instance_name}\n")
                f.write(f"Status: {snapshot_data.get('status', 'UNKNOWN').upper()}\n")
                f.write(f"Timestamp: {datetime.now().isoformat()}\n")
                f.write("=" * 80 + "\n\n")

                # Snapshots created
                if snapshot_data.get('snapshots'):
                    f.write("SNAPSHOTS CREATED:\n")
                    f.write("─" * 80 + "\n")
                    for snapshot in snapshot_data['snapshots']:
                        f.write(f"  ✓ {snapshot.get('snapshot_name', 'Unknown')}\n")
                        f.write(f"    Disk: {snapshot.get('disk_name', 'Unknown')}\n")
                        f.write(f"    Operation: {snapshot.get('operation', 'N/A')}\n")
                        f.write(f"    Time: {snapshot.get('timestamp', 'N/A')}\n\n")

                # Skipped
                if snapshot_data.get('skipped'):
                    f.write("SKIPPED:\n")
                    f.write("─" * 80 + "\n")
                    for skipped in snapshot_data['skipped']:
                        f.write(f"  - {skipped.get('disk_name', 'Unknown')}: {skipped.get('reason', 'Unknown reason')}\n")
                        if skipped.get('existing_snapshot'):
                            f.write(f"    Existing: {skipped['existing_snapshot']}\n")
                    f.write("\n")

                # Errors
                if snapshot_data.get('errors'):
                    f.write("ERRORS:\n")
                    f.write("─" * 80 + "\n")
                    for error in snapshot_data['errors']:
                        f.write(f"  ✗ {error.get('disk_name', 'Unknown')}: {error.get('error_message', 'Unknown error')}\n")
                    f.write("\n")

                f.write("=" * 80 + "\n")
                f.write(f"Snapshot log completed: {datetime.now().isoformat()}\n")
                f.write(f"Log file: {log_file}\n")
                f.write("=" * 80 + "\n")

            logger.info(f"Snapshot log written: {log_file}")
            return str(log_file)

        except Exception as e:
            logger.error(f"Failed to write snapshot log: {e}")
            return ""

    def get_recent_logs(
        self,
        log_type: str = None,
        count: int = 10
    ) -> list:
        """Get list of recent log files.

        Args:
            log_type: Filter by log type (diagnostic, healing, verification, agent_actions, snapshot)
            count: Number of recent logs to return

        Returns:
            List of log file paths (most recent first)
        """
        try:
            if log_type:
                pattern = f"{log_type}_*.log"
            else:
                pattern = "*.log"

            log_files = sorted(
                self.log_dir.glob(pattern),
                key=lambda p: p.stat().st_mtime,
                reverse=True
            )

            return [str(f) for f in log_files[:count]]

        except Exception as e:
            logger.error(f"Failed to get recent logs: {e}")
            return []

    def read_log_file(self, log_file_path: str) -> str:
        """Read contents of a log file.

        Args:
            log_file_path: Path to log file

        Returns:
            Log file contents as string
        """
        try:
            with open(log_file_path, 'r', encoding='utf-8') as f:
                return f.read()
        except Exception as e:
            logger.error(f"Failed to read log file: {e}")
            return ""


# Global instance logger
_instance_logger = None


def get_instance_logger() -> InstanceLogger:
    """Get global instance logger singleton.

    Returns:
        InstanceLogger instance
    """
    global _instance_logger
    if _instance_logger is None:
        _instance_logger = InstanceLogger()
    return _instance_logger


# Convenience functions

def log_diagnostic(diagnostic_data: Dict[str, Any], sid: str = None) -> str:
    """Log diagnostic results.

    Args:
        diagnostic_data: Diagnostic results
        sid: System ID

    Returns:
        Path to log file
    """
    return get_instance_logger().log_diagnostic(diagnostic_data, sid)


def log_healing(healing_data: Dict[str, Any], script_name: str = None) -> str:
    """Log healing execution.

    Args:
        healing_data: Healing results
        script_name: Script name

    Returns:
        Path to log file
    """
    return get_instance_logger().log_healing(healing_data, script_name)


def log_verification(verification_data: Dict[str, Any], script_name: str = None) -> str:
    """Log verification results.

    Args:
        verification_data: Verification results
        script_name: Script name

    Returns:
        Path to log file
    """
    return get_instance_logger().log_verification(verification_data, script_name)


def log_agent_action(
    action_type: str,
    details: str,
    severity: str = "INFO",
    agent_name: str = None
) -> str:
    """Log agent action.

    Args:
        action_type: Action type
        details: Action details
        severity: Severity level
        agent_name: Agent name

    Returns:
        Path to log file
    """
    return get_instance_logger().log_agent_action(action_type, details, severity, agent_name)


def log_snapshot(snapshot_data: Dict[str, Any], instance_name: str = None) -> str:
    """Log snapshot creation.

    Args:
        snapshot_data: Snapshot results
        instance_name: Instance name

    Returns:
        Path to log file
    """
    return get_instance_logger().log_snapshot(snapshot_data, instance_name)
