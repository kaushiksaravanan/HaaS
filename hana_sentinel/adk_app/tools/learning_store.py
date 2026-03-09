"""
Learning Command Store — Dynamic monitoring command loop.
Persists commands to disk (JSON). Learns new commands from successful resolutions.
Each resolution adds the diagnostic/remediation commands that worked to the store,
so the monitoring agent becomes smarter over time.

PRD: Continuous learning loop for the monitoring agent.
"""

import os
import json
import time
import logging
from datetime import datetime
from typing import List, Dict, Optional

logger = logging.getLogger(__name__)

# Default store path — persistent across restarts
_DEFAULT_STORE_PATH = os.getenv(
    "LEARNING_STORE_PATH",
    os.path.join(
        os.path.dirname(os.path.dirname(__file__)), "data", "learned_commands.json"
    ),
)

# ──────────────────────────────────────────────
# Seed commands — baseline monitoring check set
# These run on every health check cycle
# ──────────────────────────────────────────────
SEED_COMMANDS = [
    {
        "id": "seed_001",
        "name": "HANA process check",
        "command": "ps aux | grep -E 'hdb(indexserver|nameserver|compileserver|preprocessor|daemon)' | grep -v grep",
        "category": "process",
        "severity": "critical",
        "expected_pattern": "hdbindexserver",
        "failure_action": "Flag service down — trigger recovery agent",
        "added_by": "seed",
        "added_at": "2026-01-01T00:00:00",
        "success_count": 0,
        "failure_count": 0,
        "enabled": True,
    },
    {
        "id": "seed_002",
        "name": "HANA memory usage",
        "command": "free -m | head -2",
        "category": "memory",
        "severity": "warning",
        "expected_pattern": "",
        "failure_action": "Escalate if used > 90%",
        "added_by": "seed",
        "added_at": "2026-01-01T00:00:00",
        "success_count": 0,
        "failure_count": 0,
        "enabled": True,
    },
    {
        "id": "seed_003",
        "name": "Disk space check",
        "command": "df -h /hana/data /hana/log /hana/shared 2>/dev/null || df -h",
        "category": "disk",
        "severity": "critical",
        "expected_pattern": "",
        "failure_action": "Trigger capacity agent for cleanup",
        "added_by": "seed",
        "added_at": "2026-01-01T00:00:00",
        "success_count": 0,
        "failure_count": 0,
        "enabled": True,
    },
    {
        "id": "seed_004",
        "name": "HANA trace files check",
        "command": "ls -lt /usr/sap/*/HDB*/*/trace/*.trc 2>/dev/null | head -5",
        "category": "logs",
        "severity": "info",
        "expected_pattern": "",
        "failure_action": "Note: no trace files found or path incorrect",
        "added_by": "seed",
        "added_at": "2026-01-01T00:00:00",
        "success_count": 0,
        "failure_count": 0,
        "enabled": True,
    },
    {
        "id": "seed_005",
        "name": "sapcontrol process list",
        "command": "sapcontrol -nr ${HANA_INSTANCE_NR:-00} -function GetProcessList 2>/dev/null || echo 'sapcontrol not available'",
        "category": "process",
        "severity": "critical",
        "expected_pattern": "GREEN",
        "failure_action": "Service not GREEN — trigger recovery",
        "added_by": "seed",
        "added_at": "2026-01-01T00:00:00",
        "success_count": 0,
        "failure_count": 0,
        "enabled": True,
    },
    {
        "id": "seed_006",
        "name": "Network connectivity",
        "command": "ss -tlnp | grep -E '3(9|0)0[0-9]{2}' || netstat -tlnp 2>/dev/null | grep -E '3(9|0)0[0-9]{2}'",
        "category": "network",
        "severity": "critical",
        "expected_pattern": "LISTEN",
        "failure_action": "HANA ports not listening — service may be down",
        "added_by": "seed",
        "added_at": "2026-01-01T00:00:00",
        "success_count": 0,
        "failure_count": 0,
        "enabled": True,
    },
    {
        "id": "seed_007",
        "name": "System uptime and load",
        "command": "uptime",
        "category": "system",
        "severity": "info",
        "expected_pattern": "",
        "failure_action": "",
        "added_by": "seed",
        "added_at": "2026-01-01T00:00:00",
        "success_count": 0,
        "failure_count": 0,
        "enabled": True,
    },
    {
        "id": "seed_008",
        "name": "HANA alert check via SQL",
        "command": "hdbsql -U DEFAULT -j 'SELECT ALERT_ID, ALERT_RATING, ALERT_DETAILS FROM _SYS_STATISTICS.STATISTICS_CURRENT_ALERTS WHERE ALERT_RATING >= 3' 2>/dev/null || echo 'hdbsql not available in container'",
        "category": "alerts",
        "severity": "warning",
        "expected_pattern": "",
        "failure_action": "Active alerts found — evaluate and escalate",
        "added_by": "seed",
        "added_at": "2026-01-01T00:00:00",
        "success_count": 0,
        "failure_count": 0,
        "enabled": True,
    },
    {
        "id": "seed_009",
        "name": "HDB data volume space",
        "command": "df -h /hana/data /hdb/*/data 2>/dev/null || df -h /usr/sap/*/data 2>/dev/null || echo 'HDB data path not found'",
        "category": "disk",
        "severity": "critical",
        "expected_pattern": "",
        "failure_action": "HDB data volume critically low — trigger capacity agent",
        "added_by": "seed",
        "added_at": "2026-01-01T00:00:00",
        "success_count": 0,
        "failure_count": 0,
        "enabled": True,
    },
    {
        "id": "seed_010",
        "name": "HDB log volume space",
        "command": "df -h /hana/log /hdb/*/log 2>/dev/null || df -h /usr/sap/*/log 2>/dev/null || echo 'HDB log path not found'",
        "category": "disk",
        "severity": "critical",
        "expected_pattern": "",
        "failure_action": "HDB log volume full — risk of log writes failing",
        "added_by": "seed",
        "added_at": "2026-01-01T00:00:00",
        "success_count": 0,
        "failure_count": 0,
        "enabled": True,
    },
    {
        "id": "seed_011",
        "name": "HDB backup volume space",
        "command": (
            "df -h /hana/backup /hdb/*/backup 2>/dev/null"
            " || df -h /backup 2>/dev/null"
            " || echo 'Backup path not found'"
        ),
        "category": "disk",
        "severity": "critical",
        "expected_pattern": "",
        "failure_action": "Backup path exhausted — backup agent will fail",
        "added_by": "seed",
        "added_at": "2026-01-01T00:00:00",
        "success_count": 0,
        "failure_count": 0,
        "enabled": True,
    },
    {
        "id": "seed_012",
        "name": "HDB shared volume space",
        "command": (
            "df -h /hana/shared /usr/sap 2>/dev/null"
            " || echo 'Shared/usr/sap path not found'"
        ),
        "category": "disk",
        "severity": "warning",
        "expected_pattern": "",
        "failure_action": "Shared volume low — may affect HANA operations",
        "added_by": "seed",
        "added_at": "2026-01-01T00:00:00",
        "success_count": 0,
        "failure_count": 0,
        "enabled": True,
    },
    {
        "id": "seed_013",
        "name": "HDB inode usage",
        "command": (
            "df -ih /hana/data /hana/log /hana/shared"
            " 2>/dev/null || df -ih / /usr/sap 2>/dev/null"
        ),
        "category": "disk",
        "severity": "warning",
        "expected_pattern": "",
        "failure_action": (
            "Inode exhaustion can cause HANA write failures despite free space"
        ),
        "added_by": "seed",
        "added_at": "2026-01-01T00:00:00",
        "success_count": 0,
        "failure_count": 0,
        "enabled": True,
    },
    {
        "id": "seed_014",
        "name": "HDB trace and dump size",
        "command": (
            "du -sh /usr/sap/*/HDB*/*/trace/ 2>/dev/null;"
            " du -sh /usr/sap/*/HDB*/*/diag/ 2>/dev/null"
            " || echo 'Trace paths not found'"
        ),
        "category": "disk",
        "severity": "info",
        "expected_pattern": "",
        "failure_action": (
            "Large trace/dump files consuming disk \u2014 consider cleanup"
        ),
        "added_by": "seed",
        "added_at": "2026-01-01T00:00:00",
        "success_count": 0,
        "failure_count": 0,
        "enabled": True,
    },
]


class LearningCommandStore:
    """Persistent store for monitoring commands with learning loop.

    How learning works:
    1. Monitoring Agent runs commands from the store against the container.
    2. When a resolution succeeds, the diagnostic +
       remediation commands are recorded.
    3. On next cycle, the new commands are automatically included.
    4. Commands that consistently fail are disabled (but not deleted).
    5. High-success commands get promoted (run earlier in the cycle).
    """

    def __init__(self, store_path: str = ""):
        self.store_path = store_path or _DEFAULT_STORE_PATH
        self.commands: List[Dict] = []
        self._load()

    def _load(self):
        """Load commands from disk, or initialize with seed commands."""
        if os.path.exists(self.store_path):
            try:
                with open(self.store_path, "r") as f:
                    data = json.load(f)
                self.commands = data.get("commands", [])
                logger.info(
                    "Loaded %d commands from %s",
                    len(self.commands),
                    self.store_path,
                )
                return
            except Exception as e:
                logger.warning("Failed to load store: %s, reinitializing", e)

        # Initialize with seed commands
        self.commands = [cmd.copy() for cmd in SEED_COMMANDS]
        self._save()
        logger.info("Initialized store with %d seed cmds", len(self.commands))

    def _save(self):
        """Persist commands to disk."""
        os.makedirs(os.path.dirname(self.store_path), exist_ok=True)
        data = {
            "version": 1,
            "last_updated": datetime.utcnow().isoformat(),
            "total_commands": len(self.commands),
            "learned_count": sum(
                1 for c in self.commands if c.get("added_by") != "seed"
            ),
            "commands": self.commands,
        }
        with open(self.store_path, "w") as f:
            json.dump(data, f, indent=2)
        logger.info(f"Saved {len(self.commands)} commands to {self.store_path}")

    def get_enabled_commands(self, category: str = "") -> List[Dict]:
        """Get all enabled commands, optionally filtered by category.
        Sorted by priority: critical first, then by success rate.
        """
        cmds = [c for c in self.commands if c.get("enabled", True)]
        if category:
            cmds = [c for c in cmds if c.get("category", "") == category]

        # Sort: critical first, then warning, then info;
        # within tier by success ratio
        severity_order = {"critical": 0, "warning": 1, "info": 2}

        def sort_key(c):
            sev = severity_order.get(c.get("severity", "info"), 3)
            total = c.get("success_count", 0) + c.get("failure_count", 0)
            success_rate = c.get("success_count", 0) / max(total, 1)
            return (sev, -success_rate)

        cmds.sort(key=sort_key)
        return cmds

    def get_categories(self) -> List[str]:
        """Get all unique command categories."""
        return list(set(c.get("category", "other") for c in self.commands))

    def record_result(self, command_id: str, success: bool, output: str = ""):
        """Record the result of running a command. Updates success/failure counts."""
        for cmd in self.commands:
            if cmd["id"] == command_id:
                if success:
                    cmd["success_count"] = cmd.get("success_count", 0) + 1
                else:
                    cmd["failure_count"] = cmd.get("failure_count", 0) + 1

                cmd["last_run"] = datetime.utcnow().isoformat()
                cmd["last_output"] = output[:2000]  # Cap stored output

                # Auto-disable if failure ratio > 80% and run count > 10
                total = cmd.get("success_count", 0) + cmd.get("failure_count", 0)
                if total >= 10 and cmd.get("failure_count", 0) / total > 0.8:
                    cmd["enabled"] = False
                    cmd["disabled_reason"] = (
                        "Auto-disabled: >80% failure rate after 10+ runs"
                    )
                    logger.warning(
                        "Auto-disabled command '%s' due to high failure rate",
                        cmd["name"],
                    )

                self._save()
                return True
        return False

    def learn_from_resolution(
        self,
        incident_summary: str,
        diagnostic_commands: List[str],
        remediation_commands: List[str],
        category: str = "learned",
        severity: str = "warning",
        agent_name: str = "monitoring_agent",
    ) -> List[str]:
        """LEARNING LOOP: Add new commands learned from a successful resolution.

        Called AFTER a successful remediation to capture the commands that
        helped diagnose and fix the issue. These are automatically added
        to the monitoring cycle.

        Args:
            incident_summary: What happened (used as command name prefix).
            diagnostic_commands: Commands that helped diagnose the issue.
            remediation_commands: Commands that fixed the issue (added as info-only checks).
            category: Category to assign.
            severity: Severity level.
            agent_name: Which agent learned this.

        Returns:
            List of new command IDs that were added.
        """
        new_ids = []
        existing_cmds = {c["command"] for c in self.commands}

        # Add diagnostic commands
        for i, cmd in enumerate(diagnostic_commands):
            cmd = cmd.strip()
            if not cmd or cmd in existing_cmds:
                continue

            cmd_id = f"learned_{int(time.time())}_{i}"
            new_cmd = {
                "id": cmd_id,
                "name": f"[Learned] {incident_summary[:50]} (diag-{i + 1})",
                "command": cmd,
                "category": category,
                "severity": severity,
                "expected_pattern": "",
                "failure_action": f"Recurrence of: {incident_summary[:100]}",
                "added_by": agent_name,
                "added_at": datetime.utcnow().isoformat(),
                "learned_from": incident_summary[:200],
                "command_type": "diagnostic",
                "success_count": 1,  # Already succeeded once
                "failure_count": 0,
                "enabled": True,
            }
            self.commands.append(new_cmd)
            existing_cmds.add(cmd)
            new_ids.append(cmd_id)

        # Add remediation check commands (to detect if fix is still holding)
        for i, cmd in enumerate(remediation_commands):
            cmd = cmd.strip()
            if not cmd or cmd in existing_cmds:
                continue

            cmd_id = f"learned_{int(time.time())}_{len(diagnostic_commands) + i}"
            new_cmd = {
                "id": cmd_id,
                "name": f"[Learned] Verify fix: {incident_summary[:40]} (check-{i + 1})",
                "command": cmd,
                "category": category,
                "severity": "info",
                "expected_pattern": "",
                "failure_action": f"Fix may have regressed: {incident_summary[:100]}",
                "added_by": agent_name,
                "added_at": datetime.utcnow().isoformat(),
                "learned_from": incident_summary[:200],
                "command_type": "remediation_verify",
                "success_count": 1,
                "failure_count": 0,
                "enabled": True,
            }
            self.commands.append(new_cmd)
            existing_cmds.add(cmd)
            new_ids.append(cmd_id)

        if new_ids:
            self._save()
            logger.info(
                "Learned %d new cmds from: %s",
                len(new_ids),
                incident_summary[:50],
            )

        return new_ids

    def add_command(
        self,
        name: str,
        command: str,
        category: str = "custom",
        severity: str = "info",
        expected_pattern: str = "",
        failure_action: str = "",
    ) -> str:
        """Manually add a new monitoring command.

        Args:
            name: Human-readable name.
            command: Shell command to execute.
            category: Category (process, memory, disk, network, logs, alerts, system, custom).
            severity: Severity (critical, warning, info).
            expected_pattern: Regex/string expected in output (empty = always passes).
            failure_action: Description of action to take on failure.

        Returns:
            The ID of the newly added command.
        """
        # Dedup
        for c in self.commands:
            if c["command"] == command:
                return c["id"]

        cmd_id = f"manual_{int(time.time())}"
        new_cmd = {
            "id": cmd_id,
            "name": name,
            "command": command,
            "category": category,
            "severity": severity,
            "expected_pattern": expected_pattern,
            "failure_action": failure_action,
            "added_by": "manual",
            "added_at": datetime.utcnow().isoformat(),
            "command_type": "manual",
            "success_count": 0,
            "failure_count": 0,
            "enabled": True,
        }
        self.commands.append(new_cmd)
        self._save()
        return cmd_id

    def remove_command(self, command_id: str) -> bool:
        """Remove a command by ID."""
        before = len(self.commands)
        self.commands = [c for c in self.commands if c["id"] != command_id]
        if len(self.commands) < before:
            self._save()
            return True
        return False

    def get_stats(self) -> dict:
        """Get store statistics."""
        total = len(self.commands)
        enabled = sum(1 for c in self.commands if c.get("enabled", True))
        learned = sum(
            1 for c in self.commands if c.get("added_by") not in ("seed", "manual")
        )
        return {
            "total_commands": total,
            "enabled_commands": enabled,
            "disabled_commands": total - enabled,
            "seed_commands": sum(
                1 for c in self.commands if c.get("added_by") == "seed"
            ),
            "learned_commands": learned,
            "manual_commands": sum(
                1 for c in self.commands if c.get("added_by") == "manual"
            ),
            "categories": self.get_categories(),
        }

    def export_as_script(self) -> str:
        """Export all enabled commands as a standalone shell script."""
        lines = [
            "#!/bin/bash",
            "# HANA Sentinel — Auto-generated monitoring script",
            f"# Generated: {datetime.utcnow().isoformat()}",
            f"# Total commands: {len(self.get_enabled_commands())}",
            "",
            'echo "=== HANA Sentinel Monitoring Report ==="',
            'echo "Generated: $(date)"',
            "",
        ]
        for cmd in self.get_enabled_commands():
            lines.append(f"# [{cmd.get('severity', 'info').upper()}] {cmd['name']}")
            lines.append(f'echo "--- {cmd["name"]} ---"')
            lines.append(cmd["command"])
            lines.append("echo")
            lines.append("")

        lines.append('echo "=== End Report ==="')
        return "\n".join(lines)


# ──────────────────────────────────────────────
# ADK Tool Functions for Learning Store
# ──────────────────────────────────────────────
_store_instance: Optional[LearningCommandStore] = None


def _get_store() -> LearningCommandStore:
    global _store_instance
    if _store_instance is None:
        _store_instance = LearningCommandStore()
    return _store_instance


def get_monitoring_commands(category: str = "") -> dict:
    """Get all enabled monitoring commands from the learning store.
    Commands are sorted by priority (critical first, highest success rate first).

    Args:
        category (str): Optional filter by category (process, memory, disk, network, logs, alerts, system).

    Returns:
        dict: List of commands with their metadata, category list, and store stats.
    """
    store = _get_store()
    commands = store.get_enabled_commands(category)
    return {
        "status": "success",
        "commands": commands,
        "count": len(commands),
        "categories": store.get_categories(),
        "stats": store.get_stats(),
    }


def record_command_result(command_id: str, success: bool, output: str = "") -> dict:
    """Record the result of executing a monitoring command.
    Updates success/failure counts. Auto-disables commands with >80% failure rate.

    Args:
        command_id (str): The command ID.
        success (bool): Whether the command execution was successful.
        output (str): The command output (capped at 2000 chars).

    Returns:
        dict: Updated command status.
    """
    store = _get_store()
    found = store.record_result(command_id, success, output)
    if not found:
        return {
            "status": "error",
            "error_message": f"Command ID not found: {command_id}",
        }
    return {
        "status": "success",
        "message": f"Result recorded for {command_id}",
        "success": success,
    }


def learn_new_commands(
    incident_summary: str,
    diagnostic_commands: str,
    remediation_commands: str = "",
    category: str = "learned",
    severity: str = "warning",
) -> dict:
    """LEARNING LOOP: Teach the monitoring agent new commands from a successful resolution.
    After any incident is resolved, call this to add the diagnostic and remediation
    commands to the monitoring rotation. They will run automatically on future cycles.

    Args:
        incident_summary (str): What the incident was (e.g., "Indexserver OOM crash").
        diagnostic_commands (str): Newline-separated commands that helped diagnose the issue.
        remediation_commands (str): Newline-separated commands that fixed the issue (optional).
        category (str): Category for the new commands (default: learned).
        severity (str): Severity level (critical, warning, info).

    Returns:
        dict: List of new command IDs that were added to the monitoring rotation.
    """
    store = _get_store()
    diag_list = [
        c.strip() for c in diagnostic_commands.strip().split("\n") if c.strip()
    ]
    remed_list = (
        [c.strip() for c in remediation_commands.strip().split("\n") if c.strip()]
        if remediation_commands
        else []
    )

    new_ids = store.learn_from_resolution(
        incident_summary=incident_summary,
        diagnostic_commands=diag_list,
        remediation_commands=remed_list,
        category=category,
        severity=severity,
    )

    return {
        "status": "success",
        "message": f"Learned {len(new_ids)} new commands from: {incident_summary}",
        "new_command_ids": new_ids,
        "total_commands": len(store.commands),
    }


def add_monitoring_command(
    name: str,
    command: str,
    category: str = "custom",
    severity: str = "info",
    expected_pattern: str = "",
    failure_action: str = "",
) -> dict:
    """Manually add a new monitoring command to the dynamic command set.

    Args:
        name (str): Human-readable name for the command.
        command (str): Shell command to execute.
        category (str): Category (process, memory, disk, network, logs, alerts, system, custom).
        severity (str): Severity level (critical, warning, info).
        expected_pattern (str): String expected in output — absence triggers failure_action.
        failure_action (str): What to do if the check fails.

    Returns:
        dict: The new command ID.
    """
    store = _get_store()
    cmd_id = store.add_command(
        name, command, category, severity, expected_pattern, failure_action
    )
    return {
        "status": "success",
        "command_id": cmd_id,
        "total_commands": len(store.commands),
    }


def get_monitoring_script() -> dict:
    """Export all monitoring commands as a standalone bash script.
    This script can be deployed independently for cron-based monitoring.

    Returns:
        dict: The generated shell script content.
    """
    store = _get_store()
    return {
        "status": "success",
        "script": store.export_as_script(),
        "command_count": len(store.get_enabled_commands()),
    }
