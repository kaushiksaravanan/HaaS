"""
Instance Diagnostics — Diagnostic checks for HANA instances via HTTP API.
Uses remote_exec_server_v2.py endpoints for all diagnostic operations.
"""

import os
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional
from .http_command_executor import get_http_executor

logger = logging.getLogger(__name__)


class InstanceDiagnostics:
    """Diagnostic checks for HANA instance via HTTP API."""

    def __init__(
        self,
        instance_name: str = None,
        project_id: str = None,
        zone: str = None,
        hana_user: str = None,
        sid: str = None,
        instance_number: str = None
    ):
        """Initialize instance diagnostics.

        Args:
            instance_name: GCP instance name (defaults to env)
            project_id: GCP project ID (defaults to env)
            zone: GCP zone (defaults to env)
            hana_user: HANA admin user (defaults to env)
            sid: HANA System ID (defaults to env)
            instance_number: HANA instance number (defaults to env)
        """
        self.instance_name = instance_name or os.getenv("GCP_TOOLKIT_INSTANCE_NAME", "")
        self.project_id = project_id or os.getenv("GCP_TOOLKIT_PROJECT_ID", "")
        self.zone = zone or os.getenv("GCP_TOOLKIT_ZONE", "")
        self.hana_user = hana_user or os.getenv("GCP_TOOLKIT_HANA_USER", "")
        self.sid = sid or os.getenv("GCP_TOOLKIT_HANA_SID", "")
        self.instance_number = instance_number or os.getenv("GCP_TOOLKIT_INSTANCE_NUMBER", "")

        self.executor = get_http_executor()

        if not self.executor.is_configured():
            logger.warning("HTTP executor not configured - diagnostics may fail")

    def check_hana_process_status(self) -> Dict[str, Any]:
        """Check HANA process status using remote diagnostics.

        Returns:
            dict with status and process details
        """
        logger.info("Checking HANA process status via HTTP API")

        try:
            result = self.executor.run_diagnostics()

            if result.get("status") != "success":
                return {
                    "status": "error",
                    "check": "process_status",
                    "error": result.get("error", "Unknown error"),
                    "severity": "critical"
                }

            data = result.get("data", {})
            process_check = data.get("diagnostics", {}).get("hana_processes", {})

            output = process_check.get("output", "")
            status = process_check.get("status", "error")

            if status != "success":
                # Check if output has process info even on non-zero exit
                has_green = "GREEN" in output
                has_processes = "hdbdaemon" in output.lower() or "hdbnameserver" in output.lower()
                if has_processes:
                    all_green = has_green and "GRAY" not in output and "YELLOW" not in output
                    severity = "ok" if all_green else "warning"
                    return {
                        "status": "success",
                        "check": "process_status",
                        "severity": severity,
                        "all_green": all_green,
                        "message": output
                    }
                error_msg = process_check.get("error") or output or "Process check failed"
                return {
                    "status": "error",
                    "check": "process_status",
                    "error": error_msg,
                    "severity": "critical"
                }

            all_green = "GREEN" in output and "GRAY" not in output and "YELLOW" not in output
            severity = "ok" if all_green else "warning"

            return {
                "status": "success",
                "check": "process_status",
                "severity": severity,
                "all_green": all_green,
                "message": output
            }

        except Exception as e:
            logger.error(f"Process status check failed: {e}")
            return {
                "status": "error",
                "check": "process_status",
                "error": str(e),
                "severity": "critical"
            }

    def check_hdb_info(self) -> Dict[str, Any]:
        """Check HDB info via HTTP API.

        Returns:
            dict with HDB info
        """
        logger.info("Checking HDB info via HTTP API")

        try:
            result = self.executor.get_node_info()

            if result.get("status") != "success":
                return {
                    "status": "error",
                    "check": "hdb_info",
                    "error": result.get("error", "Unknown error"),
                    "severity": "critical"
                }

            data = result.get("data", {})
            hana = data.get("hana", {})
            system = data.get("system", {})

            sid = hana.get("sid", "")
            instance_nr = hana.get("instance_number", "")
            user = hana.get("user", "")
            hostname = system.get("hostname", "")

            return {
                "status": "success",
                "check": "hdb_info",
                "severity": "ok" if sid else "warning",
                "message": f"SID: {sid}, Instance: {instance_nr}, User: {user}, Host: {hostname}"
            }

        except Exception as e:
            logger.error(f"HDB info check failed: {e}")
            return {
                "status": "error",
                "check": "hdb_info",
                "error": str(e),
                "severity": "critical"
            }

    def check_disk_usage(self) -> Dict[str, Any]:
        """Check disk usage via HTTP API.

        Returns:
            dict with disk usage details
        """
        logger.info("Checking disk usage via HTTP API")

        try:
            result = self.executor.run_diagnostics()

            if result.get("status") != "success":
                return {
                    "status": "error",
                    "check": "disk_usage",
                    "error": result.get("error", "Unknown error"),
                    "severity": "warning"
                }

            data = result.get("data", {})
            disk_check = data.get("diagnostics", {}).get("disk_usage", {})
            output = disk_check.get("output", "")

            if disk_check.get("status") != "success":
                return {
                    "status": "error",
                    "check": "disk_usage",
                    "error": disk_check.get("error", "Disk check failed"),
                    "severity": "warning"
                }

            # Parse df output to find max usage
            max_usage = 0
            critical_partition = None
            partitions = []
            for line in output.split("\n"):
                parts = line.split()
                if len(parts) >= 6 and "%" in parts[4]:
                    try:
                        pct = int(parts[4].replace("%", ""))
                        partitions.append({
                            "mount": parts[5],
                            "size": parts[1],
                            "used": parts[2],
                            "avail": parts[3],
                            "use_pct": pct
                        })
                        if pct > max_usage:
                            max_usage = pct
                            critical_partition = parts[5]
                    except ValueError:
                        pass

            severity = "ok"
            if max_usage >= 90:
                severity = "critical"
            elif max_usage >= 80:
                severity = "warning"

            return {
                "status": "success",
                "check": "disk_usage",
                "severity": severity,
                "partitions": partitions,
                "max_usage": max_usage,
                "critical_partition": critical_partition,
                "message": f"Max disk usage: {max_usage}% on {critical_partition or 'N/A'}"
            }

        except Exception as e:
            logger.error(f"Disk usage check failed: {e}")
            return {
                "status": "error",
                "check": "disk_usage",
                "error": str(e),
                "severity": "warning"
            }

    def check_database_version(self) -> Dict[str, Any]:
        """Check HANA database version via HTTP API.

        Returns:
            dict with version info
        """
        logger.info("Checking database version via HTTP API")

        try:
            result = self.executor.get_version_info()

            if result.get("status") != "success":
                return {
                    "status": "error",
                    "check": "database_version",
                    "error": result.get("error", "Unknown error"),
                    "severity": "info"
                }

            data = result.get("data", {})
            hana_version = data.get("hana_version", "Unknown")
            hana_sid = data.get("hana_sid", "")
            instance_number = data.get("instance_number", "")
            os_info = data.get("os_info", "")

            return {
                "status": "success",
                "check": "database_version",
                "severity": "info",
                "version": hana_version,
                "message": f"SID: {hana_sid}, Instance: {instance_number}, OS: {os_info}"
            }

        except Exception as e:
            logger.error(f"Database version check failed: {e}")
            return {
                "status": "error",
                "check": "database_version",
                "error": str(e),
                "severity": "info"
            }

    def check_userstore(self) -> Dict[str, Any]:
        """Check HANA userstore keys via HTTP API.

        Returns:
            dict with userstore key details
        """
        logger.info("Checking userstore keys via HTTP API")

        try:
            result = self.executor.run_diagnostics()

            if result.get("status") != "success":
                return {
                    "status": "error",
                    "check": "userstore",
                    "error": result.get("error", "Unknown error"),
                    "severity": "warning"
                }

            data = result.get("data", {})
            userstore_check = data.get("diagnostics", {}).get("userstore", {})
            output = userstore_check.get("output", "")

            if userstore_check.get("status") != "success":
                return {
                    "status": "error",
                    "check": "userstore",
                    "error": userstore_check.get("error", "Userstore check failed"),
                    "severity": "warning"
                }

            # Parse hdbuserstore list output to extract key names
            keys = [line.replace("KEY ", "").strip()
                    for line in output.split("\n")
                    if line.strip().startswith("KEY ")]

            # Check for essential keys
            essential = ["SYSTEM"]
            missing_keys = [k for k in essential if k not in keys]
            severity = "ok" if not missing_keys else "warning"

            return {
                "status": "success",
                "check": "userstore",
                "severity": severity,
                "keys": keys,
                "missing_keys": missing_keys,
                "key_count": len(keys),
                "message": f"{len(keys)} keys configured" + (f", missing: {missing_keys}" if missing_keys else "")
            }

        except Exception as e:
            logger.error(f"Userstore check failed: {e}")
            return {
                "status": "error",
                "check": "userstore",
                "error": str(e),
                "severity": "warning"
            }

    def check_database_alerts(self) -> Dict[str, Any]:
        """Check recent database alerts via HTTP API.

        Returns:
            dict with alert details
        """
        logger.info("Checking database alerts via HTTP API")

        try:
            result = self.executor.get_system_health()

            if result.get("status") != "success":
                return {
                    "status": "warning",
                    "check": "database_alerts",
                    "error": "Unable to retrieve alerts",
                    "severity": "info"
                }

            data = result.get("data", {})
            alerts = data.get("alerts", [])

            alert_count = len(alerts)
            severity = "ok" if alert_count == 0 else "warning"

            return {
                "status": "success",
                "check": "database_alerts",
                "severity": severity,
                "alerts": alerts,
                "alert_count": alert_count,
                "message": f"{alert_count} alerts" if alert_count else "No alerts"
            }

        except Exception as e:
            logger.error(f"Database alerts check failed: {e}")
            return {
                "status": "error",
                "check": "database_alerts",
                "error": str(e),
                "severity": "info"
            }

    def check_memory_usage(self) -> Dict[str, Any]:
        """Check system memory usage via HTTP API.

        Returns:
            dict with memory usage details
        """
        logger.info("Checking memory usage via HTTP API")

        try:
            result = self.executor.get_system_health()

            if result.get("status") != "success":
                return {
                    "status": "error",
                    "check": "memory_usage",
                    "error": result.get("error", "Unknown error"),
                    "severity": "warning"
                }

            data = result.get("data", {})
            memory = data.get("memory", {})
            output = memory.get("output", "")

            # Parse 'free -h' output: "Mem: 179Gi  6.9Gi  170Gi ..."
            total = "Unknown"
            used = "Unknown"
            available = "Unknown"
            usage_pct = 0
            for line in output.split("\n"):
                if line.startswith("Mem:"):
                    parts = line.split()
                    if len(parts) >= 4:
                        total = parts[1]
                        used = parts[2]
                        available = parts[6] if len(parts) >= 7 else parts[3]
                        # Estimate usage pct from values
                        try:
                            def parse_mem(s):
                                s = s.strip()
                                if s.endswith("Gi"):
                                    return float(s[:-2])
                                if s.endswith("Mi"):
                                    return float(s[:-2]) / 1024
                                if s.endswith("Ti"):
                                    return float(s[:-2]) * 1024
                                return float(s)
                            usage_pct = round(parse_mem(used) / parse_mem(total) * 100, 1)
                        except (ValueError, ZeroDivisionError):
                            pass
                    break

            severity = "ok"
            if usage_pct >= 95:
                severity = "critical"
            elif usage_pct >= 85:
                severity = "warning"

            return {
                "status": "success",
                "check": "memory_usage",
                "severity": severity,
                "memory_info": {"total": total, "used": used, "available": available},
                "usage_percent": usage_pct,
                "message": f"Memory: {used} / {total} ({usage_pct}% used)"
            }

        except Exception as e:
            logger.error(f"Memory usage check failed: {e}")
            return {
                "status": "error",
                "check": "memory_usage",
                "error": str(e),
                "severity": "warning"
            }

    def check_backup_status(self) -> Dict[str, Any]:
        """Check last backup status via HTTP API.

        Returns:
            dict with backup details
        """
        logger.info("Checking backup status via HTTP API")

        try:
            result = self.executor.get_backup_status()

            if result.get("status") != "success":
                return {
                    "status": "warning",
                    "check": "backup_status",
                    "error": "Unable to retrieve backup status",
                    "severity": "info"
                }

            data = result.get("data", {})
            backup_dirs = data.get("backup_directories", {})
            backups = backup_dirs.get("backups", backup_dirs)

            data_backup = backups.get("data_backup", {})
            log_backup = backups.get("log_backup", {})

            data_exists = data_backup.get("exists", False) if isinstance(data_backup, dict) else False
            log_exists = log_backup.get("exists", False) if isinstance(log_backup, dict) else False

            severity = "ok" if (data_exists or log_exists) else "warning"

            return {
                "status": "success",
                "check": "backup_status",
                "severity": severity,
                "backup_info": {"data_backup": data_backup, "log_backup": log_backup},
                "message": f"Data backup: {'exists' if data_exists else 'not found'}, Log backup: {'exists' if log_exists else 'not found'}"
            }

        except Exception as e:
            logger.error(f"Backup status check failed: {e}")
            return {
                "status": "error",
                "check": "backup_status",
                "error": str(e),
                "severity": "info"
            }

    def check_system_parameters(self) -> Dict[str, Any]:
        """Check critical system parameters via HTTP API.

        Returns:
            dict with system parameter details
        """
        logger.info("Checking system parameters via HTTP API")

        try:
            result = self.executor.get_system_health()

            if result.get("status") != "success":
                return {
                    "status": "error",
                    "check": "system_parameters",
                    "error": result.get("error", "Unknown error"),
                    "severity": "warning"
                }

            data = result.get("data", {})
            sys_params = data.get("system_parameters", {})

            if sys_params.get("status") != "success":
                return {
                    "status": "error",
                    "check": "system_parameters",
                    "error": "Unable to check system parameters",
                    "severity": "warning"
                }

            parameters = sys_params.get("parameters", {})
            # Derive all_ok from individual parameter statuses
            all_ok = all(
                p.get("status") == "ok"
                for p in parameters.values()
                if isinstance(p, dict)
            )
            severity = "ok" if all_ok else "warning"

            # Build summary message
            warnings = [k for k, v in parameters.items() if isinstance(v, dict) and v.get("status") != "ok"]
            msg = "All parameters OK" if all_ok else f"Warnings: {', '.join(warnings)}"

            return {
                "status": "success",
                "check": "system_parameters",
                "severity": severity,
                "parameters": parameters,
                "all_ok": all_ok,
                "message": msg
            }

        except Exception as e:
            logger.error(f"System parameters check failed: {e}")
            return {
                "status": "error",
                "check": "system_parameters",
                "error": str(e),
                "severity": "warning"
            }

    def check_trace_directory(self) -> Dict[str, Any]:
        """Check trace directory status via HTTP API.

        Returns:
            dict with trace directory details
        """
        logger.info("Checking trace directory via HTTP API")

        try:
            # First try to list the HDB directory to find the hostname subdir
            list_result = self.executor.execute_command(
                f"ls -l /usr/sap/{self.sid}/HDB{self.instance_number}/"
            )
            # Parse ls output to find directory entries (trace dirs are under hostname subdir)
            trace_dir = f"/usr/sap/{self.sid}/HDB{self.instance_number}"
            list_output = list_result.get("output", "") or list_result.get("stdout", "")
            if list_output:
                for line in list_output.strip().split("\n"):
                    parts = line.split()
                    # Look for directory entries (start with 'd')
                    if parts and parts[0].startswith("d") and len(parts) >= 9:
                        dirname = parts[-1]
                        if dirname not in (".", "..", "work", "backup", "sapscripts"):
                            trace_dir = f"/usr/sap/{self.sid}/HDB{self.instance_number}/{dirname}/trace"
                            break

            result = self.executor.execute_command(f"du -sh {trace_dir}")

            output = ""
            if result.get("status") == "success":
                output = result.get("output", "") or result.get("stdout", "")

            trace_size = output.split("\t")[0].strip() if output and "\t" in output else "Unknown"

            return {
                "status": "success",
                "check": "trace_directory",
                "severity": "info",
                "trace_directory": trace_dir,
                "trace_size": trace_size,
                "message": f"Trace directory size: {trace_size}"
            }

        except Exception as e:
            logger.error(f"Trace directory check failed: {e}")
            return {
                "status": "error",
                "check": "trace_directory",
                "error": str(e),
                "severity": "info"
            }

    def run_full_diagnostic(self) -> Dict[str, Any]:
        """Run all diagnostic checks via HTTP API.

        Returns:
            dict with complete diagnostic report
        """
        logger.info(f"Running full diagnostic on instance {self.instance_name} via HTTP API")

        timestamp = datetime.now().isoformat()
        diagnostic_id = f"diag_{self.sid}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

        results = {
            "diagnostic_id": diagnostic_id,
            "timestamp": timestamp,
            "instance_name": self.instance_name,
            "sid": self.sid,
            "instance_number": self.instance_number,
            "checks": {}
        }

        # Run all checks
        checks = [
            ("process_status", self.check_hana_process_status),
            ("hdb_info", self.check_hdb_info),
            ("disk_usage", self.check_disk_usage),
            ("database_version", self.check_database_version),
            ("userstore", self.check_userstore),
            ("database_alerts", self.check_database_alerts),
            ("memory_usage", self.check_memory_usage),
            ("backup_status", self.check_backup_status),
            ("system_parameters", self.check_system_parameters),
            ("trace_directory", self.check_trace_directory)
        ]

        for check_name, check_func in checks:
            try:
                results['checks'][check_name] = check_func()
            except Exception as e:
                logger.error(f"Check {check_name} failed: {e}")
                results['checks'][check_name] = {
                    "status": "error",
                    "check": check_name,
                    "error": str(e),
                    "severity": "warning"
                }

        # Determine overall status and issues
        issues_detected = []
        max_severity = "info"

        for check_name, check_result in results['checks'].items():
            severity = check_result.get('severity', 'info')

            if severity == "critical":
                max_severity = "critical"
                issues_detected.append(f"{check_name}: {check_result.get('error', 'Critical issue')}")
            elif severity == "warning" and max_severity != "critical":
                max_severity = "warning"
                issues_detected.append(f"{check_name}: Warning detected")

        results['overall_status'] = max_severity
        results['issues_detected'] = issues_detected
        results['issue_count'] = len(issues_detected)

        logger.info(f"Diagnostic completed: {results['issue_count']} issues detected, severity: {max_severity}")

        return results


# Convenience function for ADK tools

def run_instance_diagnostic(
    instance_name: str = None,
    project_id: str = None,
    zone: str = None
) -> Dict[str, Any]:
    """Run full diagnostic on HANA instance via HTTP API.

    Args:
        instance_name: Instance name (defaults to env)
        project_id: Project ID (defaults to env)
        zone: Zone (defaults to env)

    Returns:
        Complete diagnostic report
    """
    try:
        diagnostics = InstanceDiagnostics(
            instance_name=instance_name,
            project_id=project_id,
            zone=zone
        )

        return diagnostics.run_full_diagnostic()

    except Exception as e:
        logger.error(f"Failed to run instance diagnostic: {e}")
        return {
            "status": "error",
            "error_message": str(e),
            "timestamp": datetime.now().isoformat()
        }
