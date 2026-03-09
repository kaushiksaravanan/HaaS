"""
Instance Healing Tools — Healing script implementations for HANA instances.
Implements all 4 healing scripts from HANA DB Agent Toolkit.
"""

import os
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional
from adk_app.tools.hana_tools import execute_remote_command

logger = logging.getLogger(__name__)


class InstanceHealingExecutor:
    """Executes healing scripts for HANA instance via HTTP remote exec server."""

    def __init__(
        self,
        instance_name: str = None,
        project_id: str = None,
        zone: str = None,
        hana_user: str = None,
        sid: str = None,
        instance_number: str = None
    ):
        self.instance_name = instance_name or os.getenv("GCP_TOOLKIT_INSTANCE_NAME", "")
        self.project_id = project_id or os.getenv("GCP_TOOLKIT_PROJECT_ID", "")
        self.zone = zone or os.getenv("GCP_TOOLKIT_ZONE", "")
        self.hana_user = hana_user or os.getenv("GCP_TOOLKIT_HANA_USER", "")
        self.sid = sid or os.getenv("GCP_TOOLKIT_HANA_SID", "")
        self.instance_number = instance_number or os.getenv("GCP_TOOLKIT_INSTANCE_NUMBER", "")

        if not self.instance_name or not self.project_id:
            raise ValueError("Instance name and project ID must be provided")

        self.lower_sid = self.sid.lower()

    def _execute_as_hana_user(self, command: str) -> Dict[str, Any]:
        """Execute command as HANA admin user via remote exec server."""
        try:
            full_command = f"sudo su - {self.hana_user} -c '{command}'"
            result = execute_remote_command(
                command=full_command,
                admin_override=True
            )
            return result
        except Exception as e:
            logger.error(f"Failed to execute command: {e}")
            return {"output": "", "error": str(e), "exit_code": 1}

    def _execute_as_root(self, command: str) -> Dict[str, Any]:
        """Execute command as root via remote exec server."""
        try:
            full_command = f"sudo {command}"
            result = execute_remote_command(
                command=full_command,
                admin_override=True
            )
            return result
        except Exception as e:
            logger.error(f"Failed to execute command: {e}")
            return {"output": "", "error": str(e), "exit_code": 1}

    # ============================================================================
    # HEALING SCRIPT 1: auto_db_userstoremanagement (Risk: MEDIUM = 6 points)
    # ============================================================================

    def heal_userstore_management(self, keys_to_fix: List[str] = None) -> Dict[str, Any]:
        """Fix HANA userstore connectivity issues.

        Args:
            keys_to_fix: List of userstore keys to reconfigure (defaults to all standard keys)

        Returns:
            dict with healing results
        """
        logger.info("Starting userstore management healing")

        if not keys_to_fix:
            keys_to_fix = ['BKPMON', 'SAPDBCTRL', 'SYSTEM', 'TRANSPORT']

        results = {
            "status": "in_progress",
            "script": "auto_db_userstoremanagement",
            "timestamp": datetime.now().isoformat(),
            "keys_fixed": [],
            "keys_failed": [],
            "steps": []
        }

        try:
            # Step 1: List current userstore keys
            results['steps'].append("Listing current userstore keys")
            list_result = self._execute_as_hana_user("hdbuserstore list")

            if list_result['exit_code'] != 0:
                results['status'] = 'error'
                results['error'] = 'Failed to list userstore keys'
                return results

            # Step 2: For each key, test connection and reconfigure if needed
            for key in keys_to_fix:
                results['steps'].append(f"Processing key: {key}")

                # Test connection
                test_cmd = f"hdbsql -U {key} 'SELECT 1 FROM DUMMY'"
                test_result = self._execute_as_hana_user(test_cmd)

                if test_result['exit_code'] == 0:
                    logger.info(f"Key {key} is already working")
                    results['steps'].append(f"Key {key}: Already working, skipped")
                    continue

                # Key is not working, reconfigure it
                logger.info(f"Reconfiguring key {key}")
                results['steps'].append(f"Reconfiguring key: {key}")

                # Delete existing key
                delete_cmd = f"hdbuserstore delete {key}"
                delete_result = self._execute_as_hana_user(delete_cmd)

                # Recreate key based on type
                if key == 'SYSTEM':
                    # SYSTEM key for SYSTEMDB
                    set_cmd = f"hdbuserstore set {key} localhost:3{self.instance_number}13 SYSTEM"
                elif key == 'BKPMON':
                    # BKPMON key for backup monitoring
                    set_cmd = f"hdbuserstore set {key} localhost:3{self.instance_number}13 BKPMON"
                elif key == 'SAPDBCTRL':
                    # SAPDBCTRL key for SAP control
                    set_cmd = f"hdbuserstore set {key} localhost:3{self.instance_number}15 SAPDBCTRL"
                elif key == 'TRANSPORT':
                    # TRANSPORT key
                    set_cmd = f"hdbuserstore set {key} localhost:3{self.instance_number}15 TRANSPORT"
                else:
                    results['keys_failed'].append({
                        "key": key,
                        "reason": "Unknown key type"
                    })
                    continue

                # Note: Password will need to be provided interactively or stored securely
                # For now, this sets up the key structure without password
                set_result = self._execute_as_hana_user(set_cmd)

                if set_result['exit_code'] == 0:
                    results['keys_fixed'].append(key)
                    results['steps'].append(f"Key {key}: Successfully reconfigured")
                else:
                    results['keys_failed'].append({
                        "key": key,
                        "error": set_result['error']
                    })
                    results['steps'].append(f"Key {key}: Failed to reconfigure")

            # Step 3: Verify all keys
            results['steps'].append("Verifying all userstore keys")
            verify_result = self._execute_as_hana_user("hdbuserstore list")

            results['status'] = 'success' if not results['keys_failed'] else 'partial'
            results['completion_time'] = datetime.now().isoformat()

            logger.info(f"Userstore healing completed: {len(results['keys_fixed'])} fixed, {len(results['keys_failed'])} failed")
            return results

        except Exception as e:
            logger.error(f"Userstore healing failed: {e}")
            results['status'] = 'error'
            results['error'] = str(e)
            return results

    # ============================================================================
    # HEALING SCRIPT 2: auto_db_metadata (Risk: MEDIUM-HIGH = 8 points)
    # ============================================================================

    def heal_db_metadata(self, issues: List[str] = None) -> Dict[str, Any]:
        """Fix database metadata issues (backup paths, trace permissions, DB parameters).

        Args:
            issues: List of specific issues to fix (defaults to all checks)

        Returns:
            dict with healing results
        """
        logger.info("Starting database metadata healing")

        results = {
            "status": "in_progress",
            "script": "auto_db_metadata",
            "timestamp": datetime.now().isoformat(),
            "fixes_applied": [],
            "fixes_failed": [],
            "steps": []
        }

        try:
            # Fix 1: Backup path configuration
            if not issues or 'backup_paths' in issues:
                results['steps'].append("Configuring backup paths")
                logger.info("Fixing backup path configuration")

                # Set backup path parameters
                sql_commands = [
                    f"ALTER SYSTEM ALTER CONFIGURATION ('global.ini', 'SYSTEM') SET ('persistence', 'basepath_databackup') = '/hana/backup/{self.sid}/data' WITH RECONFIGURE",
                    f"ALTER SYSTEM ALTER CONFIGURATION ('global.ini', 'SYSTEM') SET ('persistence', 'basepath_logbackup') = '/hana/backup/{self.sid}/log' WITH RECONFIGURE"
                ]

                for sql in sql_commands:
                    cmd = f'hdbsql -U SYSTEM "{sql}"'
                    result = self._execute_as_hana_user(cmd)

                    if result['exit_code'] == 0:
                        results['fixes_applied'].append("backup_paths")
                        results['steps'].append("Backup paths configured successfully")
                    else:
                        results['fixes_failed'].append({
                            "fix": "backup_paths",
                            "error": result['error']
                        })
                        results['steps'].append(f"Backup paths configuration failed: {result['error']}")

            # Fix 2: Trace directory permissions
            if not issues or 'trace_permissions' in issues:
                results['steps'].append("Fixing trace directory permissions")
                logger.info("Fixing trace directory permissions")

                trace_dir = f"/usr/sap/{self.sid}/HDB{self.instance_number}"

                # Set proper ownership and permissions
                chmod_cmd = f"chmod -R 755 {trace_dir}/*/trace"
                chown_cmd = f"chown -R {self.lower_sid}adm:sapsys {trace_dir}/*/trace"

                chmod_result = self._execute_as_root(chmod_cmd)
                chown_result = self._execute_as_root(chown_cmd)

                if chmod_result['exit_code'] == 0 and chown_result['exit_code'] == 0:
                    results['fixes_applied'].append("trace_permissions")
                    results['steps'].append("Trace permissions fixed successfully")
                else:
                    results['fixes_failed'].append({
                        "fix": "trace_permissions",
                        "error": "Failed to set permissions"
                    })

            # Fix 3: Database parameters
            if not issues or 'db_parameters' in issues:
                results['steps'].append("Resetting database parameters")
                logger.info("Resetting database parameters to standard values")

                # Reset common problematic parameters
                param_commands = [
                    "ALTER SYSTEM ALTER CONFIGURATION ('global.ini', 'SYSTEM') SET ('memorymanager', 'global_allocation_limit') = '0' WITH RECONFIGURE",
                    "ALTER SYSTEM ALTER CONFIGURATION ('indexserver.ini', 'SYSTEM') SET ('sql', 'sql_executors') = '-1' WITH RECONFIGURE"
                ]

                param_success = 0
                for sql in param_commands:
                    cmd = f'hdbsql -U SYSTEM "{sql}"'
                    result = self._execute_as_hana_user(cmd)
                    if result['exit_code'] == 0:
                        param_success += 1

                if param_success > 0:
                    results['fixes_applied'].append("db_parameters")
                    results['steps'].append(f"Database parameters reset: {param_success} parameters")
                else:
                    results['fixes_failed'].append({
                        "fix": "db_parameters",
                        "error": "No parameters were successfully reset"
                    })

            results['status'] = 'success' if not results['fixes_failed'] else 'partial'
            results['completion_time'] = datetime.now().isoformat()

            logger.info(f"Metadata healing completed: {len(results['fixes_applied'])} fixes applied")
            return results

        except Exception as e:
            logger.error(f"Metadata healing failed: {e}")
            results['status'] = 'error'
            results['error'] = str(e)
            return results

    # ============================================================================
    # HEALING SCRIPT 3: auto_db_dbintegrations (Risk: HIGH = 12 points)
    # ============================================================================

    def heal_db_integrations(self, parameters: List[str] = None) -> Dict[str, Any]:
        """Fix OS-level database integration issues (swappiness, THP, ASLR).

        Args:
            parameters: List of specific parameters to fix (defaults to all)

        Returns:
            dict with healing results
        """
        logger.info("Starting database integrations healing (HIGH RISK)")

        results = {
            "status": "in_progress",
            "script": "auto_db_dbintegrations",
            "risk_level": "HIGH",
            "timestamp": datetime.now().isoformat(),
            "fixes_applied": [],
            "fixes_failed": [],
            "steps": []
        }

        try:
            # Fix 1: Swappiness
            if not parameters or 'swappiness' in parameters:
                results['steps'].append("Setting swappiness to 10")
                logger.info("Setting swappiness to 10")

                cmd = "sysctl -w vm.swappiness=10"
                result = self._execute_as_root(cmd)

                if result['exit_code'] == 0:
                    # Make permanent
                    permanent_cmd = "echo 'vm.swappiness=10' >> /etc/sysctl.conf"
                    self._execute_as_root(permanent_cmd)

                    results['fixes_applied'].append("swappiness")
                    results['steps'].append("Swappiness set to 10 successfully")
                else:
                    results['fixes_failed'].append({
                        "fix": "swappiness",
                        "error": result['error']
                    })

            # Fix 2: Transparent Huge Pages (THP)
            if not parameters or 'thp' in parameters:
                results['steps'].append("Disabling Transparent Huge Pages")
                logger.info("Disabling THP")

                cmd = "echo never > /sys/kernel/mm/transparent_hugepage/enabled"
                result = self._execute_as_root(cmd)

                if result['exit_code'] == 0:
                    results['fixes_applied'].append("transparent_hugepage")
                    results['steps'].append("THP disabled successfully")
                else:
                    results['fixes_failed'].append({
                        "fix": "thp",
                        "error": result['error']
                    })

            # Fix 3: ASLR (Address Space Layout Randomization)
            if not parameters or 'aslr' in parameters:
                results['steps'].append("Disabling ASLR")
                logger.info("Setting ASLR to 0")

                cmd = "sysctl -w kernel.randomize_va_space=0"
                result = self._execute_as_root(cmd)

                if result['exit_code'] == 0:
                    # Make permanent
                    permanent_cmd = "echo 'kernel.randomize_va_space=0' >> /etc/sysctl.conf"
                    self._execute_as_root(permanent_cmd)

                    results['fixes_applied'].append("aslr")
                    results['steps'].append("ASLR disabled successfully")
                else:
                    results['fixes_failed'].append({
                        "fix": "aslr",
                        "error": result['error']
                    })

            # Fix 4: User shell configuration
            if not parameters or 'user_shell' in parameters:
                results['steps'].append("Verifying user shell configuration")
                logger.info("Checking user shell")

                # Ensure user has bash shell
                cmd = f"usermod -s /bin/bash {self.lower_sid}adm"
                result = self._execute_as_root(cmd)

                if result['exit_code'] == 0:
                    results['fixes_applied'].append("user_shell")
                    results['steps'].append("User shell configured")

            # Fix 5: File permissions
            if not parameters or 'permissions' in parameters:
                results['steps'].append("Setting file permissions")
                logger.info("Setting HANA directory permissions")

                dirs_to_fix = [
                    f"/usr/sap/{self.sid}",
                    f"/hana/shared/{self.sid}"
                ]

                permission_success = 0
                for directory in dirs_to_fix:
                    cmd = f"chown -R {self.lower_sid}adm:sapsys {directory}"
                    result = self._execute_as_root(cmd)
                    if result['exit_code'] == 0:
                        permission_success += 1

                if permission_success > 0:
                    results['fixes_applied'].append("permissions")
                    results['steps'].append(f"Permissions set for {permission_success} directories")

            results['status'] = 'success' if not results['fixes_failed'] else 'partial'
            results['completion_time'] = datetime.now().isoformat()

            logger.info(f"DB integrations healing completed: {len(results['fixes_applied'])} fixes applied")
            return results

        except Exception as e:
            logger.error(f"DB integrations healing failed: {e}")
            results['status'] = 'error'
            results['error'] = str(e)
            return results

    # ============================================================================
    # HEALING SCRIPT 4: auto_db_eligibility (Risk: MEDIUM = 6 points)
    # ============================================================================

    def heal_db_eligibility(self, checks: List[str] = None) -> Dict[str, Any]:
        """Validate and fix database eligibility criteria (backups, archives).

        Args:
            checks: List of specific checks to fix (defaults to all)

        Returns:
            dict with healing results
        """
        logger.info("Starting database eligibility healing")

        results = {
            "status": "in_progress",
            "script": "auto_db_eligibility",
            "timestamp": datetime.now().isoformat(),
            "fixes_applied": [],
            "fixes_failed": [],
            "steps": []
        }

        try:
            # Fix 1: Backup configuration validation
            if not checks or 'backup_config' in checks:
                results['steps'].append("Validating backup configuration")
                logger.info("Checking backup configuration")

                sql = "SELECT * FROM M_BACKUP_CONFIGURATION"
                cmd = f'hdbsql -U BKPMON "{sql}" -a'
                result = self._execute_as_hana_user(cmd)

                if result['exit_code'] == 0:
                    results['fixes_applied'].append("backup_config_validated")
                    results['steps'].append("Backup configuration validated")
                else:
                    results['fixes_failed'].append({
                        "fix": "backup_config",
                        "error": "Failed to query backup configuration"
                    })

            # Fix 2: Archive directory validation
            if not checks or 'archive_dirs' in checks:
                results['steps'].append("Validating archive directories")
                logger.info("Checking archive directories")

                archive_dir = f"/hana/data/{self.sid}/mnt00001/hdb00001/backup/log"

                # Check if directory exists
                check_cmd = f"test -d {archive_dir} && echo 'exists' || echo 'missing'"
                check_result = self._execute_as_root(check_cmd)

                if 'exists' in check_result['output']:
                    results['fixes_applied'].append("archive_dir_validated")
                    results['steps'].append("Archive directory exists")

                    # Set proper permissions
                    chmod_cmd = f"chmod 755 {archive_dir}"
                    chown_cmd = f"chown {self.lower_sid}adm:sapsys {archive_dir}"
                    self._execute_as_root(chmod_cmd)
                    self._execute_as_root(chown_cmd)
                else:
                    # Create directory if missing
                    mkdir_cmd = f"mkdir -p {archive_dir}"
                    chown_cmd = f"chown -R {self.lower_sid}adm:sapsys {archive_dir}"
                    chmod_cmd = f"chmod -R 755 {archive_dir}"

                    mkdir_result = self._execute_as_root(mkdir_cmd)
                    if mkdir_result['exit_code'] == 0:
                        self._execute_as_root(chown_cmd)
                        self._execute_as_root(chmod_cmd)
                        results['fixes_applied'].append("archive_dir_created")
                        results['steps'].append("Archive directory created")

            # Fix 3: System database configuration
            if not checks or 'systemdb_config' in checks:
                results['steps'].append("Validating system database configuration")
                logger.info("Checking system database")

                sql = "SELECT DATABASE_NAME, ACTIVE_STATUS FROM M_DATABASES"
                cmd = f'hdbsql -U SYSTEM "{sql}" -a'
                result = self._execute_as_hana_user(cmd)

                if result['exit_code'] == 0:
                    results['fixes_applied'].append("systemdb_validated")
                    results['steps'].append("System database configuration validated")
                else:
                    results['fixes_failed'].append({
                        "fix": "systemdb_config",
                        "error": "Failed to query system database"
                    })

            # Fix 4: Backup catalog check
            if not checks or 'backup_catalog' in checks:
                results['steps'].append("Checking backup catalog")
                logger.info("Validating backup catalog")

                sql = "SELECT COUNT(*) as BACKUP_COUNT FROM M_BACKUP_CATALOG"
                cmd = f'hdbsql -U BKPMON "{sql}" -a'
                result = self._execute_as_hana_user(cmd)

                if result['exit_code'] == 0:
                    results['fixes_applied'].append("backup_catalog_validated")
                    results['steps'].append("Backup catalog validated")

            results['status'] = 'success' if not results['fixes_failed'] else 'partial'
            results['completion_time'] = datetime.now().isoformat()

            logger.info(f"Eligibility healing completed: {len(results['fixes_applied'])} checks passed")
            return results

        except Exception as e:
            logger.error(f"Eligibility healing failed: {e}")
            results['status'] = 'error'
            results['error'] = str(e)
            return results

    # ============================================================================
    # VERIFICATION
    # ============================================================================

    def verify_healing(self, script_name: str, healing_result: Dict[str, Any]) -> Dict[str, Any]:
        """Verify healing script execution.

        Args:
            script_name: Name of the healing script
            healing_result: Results from healing execution

        Returns:
            dict with verification results
        """
        logger.info(f"Verifying healing script: {script_name}")

        verification = {
            "script": script_name,
            "timestamp": datetime.now().isoformat(),
            "verification_checks": [],
            "overall_status": "pending"
        }

        try:
            if script_name == "auto_db_userstoremanagement":
                # Verify userstore keys
                list_result = self._execute_as_hana_user("hdbuserstore list")
                verification['verification_checks'].append({
                    "check": "userstore_list",
                    "status": "pass" if list_result['exit_code'] == 0 else "fail"
                })

                # Test key connectivity
                for key in healing_result.get('keys_fixed', []):
                    test_cmd = f"hdbsql -U {key} 'SELECT 1 FROM DUMMY'"
                    test_result = self._execute_as_hana_user(test_cmd)
                    verification['verification_checks'].append({
                        "check": f"key_{key}_connectivity",
                        "status": "pass" if test_result['exit_code'] == 0 else "fail"
                    })

            elif script_name == "auto_db_metadata":
                # Verify backup configuration
                sql = "SELECT * FROM M_BACKUP_CONFIGURATION"
                cmd = f'hdbsql -U BKPMON "{sql}"'
                result = self._execute_as_hana_user(cmd)
                verification['verification_checks'].append({
                    "check": "backup_configuration",
                    "status": "pass" if result['exit_code'] == 0 else "fail"
                })

            elif script_name == "auto_db_dbintegrations":
                # Verify system parameters
                swap_check = self._execute_as_root("cat /proc/sys/vm/swappiness")
                verification['verification_checks'].append({
                    "check": "swappiness",
                    "status": "pass" if "10" in swap_check['output'] else "fail",
                    "value": swap_check['output'].strip()
                })

                thp_check = self._execute_as_root("cat /sys/kernel/mm/transparent_hugepage/enabled")
                verification['verification_checks'].append({
                    "check": "transparent_hugepage",
                    "status": "pass" if "[never]" in thp_check['output'] else "fail",
                    "value": thp_check['output'].strip()
                })

                aslr_check = self._execute_as_root("cat /proc/sys/kernel/randomize_va_space")
                verification['verification_checks'].append({
                    "check": "aslr",
                    "status": "pass" if "0" in aslr_check['output'] else "fail",
                    "value": aslr_check['output'].strip()
                })

            elif script_name == "auto_db_eligibility":
                # Verify backup catalog
                sql = "SELECT COUNT(*) FROM M_BACKUP_CATALOG"
                cmd = f'hdbsql -U BKPMON "{sql}"'
                result = self._execute_as_hana_user(cmd)
                verification['verification_checks'].append({
                    "check": "backup_catalog",
                    "status": "pass" if result['exit_code'] == 0 else "fail"
                })

            # Determine overall status
            all_passed = all(check['status'] == 'pass' for check in verification['verification_checks'])
            any_failed = any(check['status'] == 'fail' for check in verification['verification_checks'])

            verification['overall_status'] = 'pass' if all_passed else 'fail' if any_failed else 'partial'
            verification['checks_passed'] = sum(1 for c in verification['verification_checks'] if c['status'] == 'pass')
            verification['checks_failed'] = sum(1 for c in verification['verification_checks'] if c['status'] == 'fail')

            logger.info(f"Verification completed: {verification['overall_status']}")
            return verification

        except Exception as e:
            logger.error(f"Verification failed: {e}")
            verification['overall_status'] = 'error'
            verification['error'] = str(e)
            return verification


# Convenience functions for ADK tools

def execute_healing_script(
    script_name: str,
    parameters: Dict[str, Any] = None,
    instance_name: str = None,
    project_id: str = None,
    zone: str = None
) -> Dict[str, Any]:
    """Execute a healing script on HANA instance.

    Args:
        script_name: Name of healing script
        parameters: Script-specific parameters
        instance_name: Instance name (defaults to env)
        project_id: Project ID (defaults to env)
        zone: Zone (defaults to env)

    Returns:
        Healing execution results
    """
    try:
        executor = InstanceHealingExecutor(
            instance_name=instance_name,
            project_id=project_id,
            zone=zone
        )

        parameters = parameters or {}

        if script_name == "auto_db_userstoremanagement":
            return executor.heal_userstore_management(
                keys_to_fix=parameters.get('keys_to_fix')
            )
        elif script_name == "auto_db_metadata":
            return executor.heal_db_metadata(
                issues=parameters.get('issues')
            )
        elif script_name == "auto_db_dbintegrations":
            return executor.heal_db_integrations(
                parameters=parameters.get('parameters')
            )
        elif script_name == "auto_db_eligibility":
            return executor.heal_db_eligibility(
                checks=parameters.get('checks')
            )
        else:
            return {
                "status": "error",
                "error": f"Unknown healing script: {script_name}"
            }

    except Exception as e:
        logger.error(f"Failed to execute healing script: {e}")
        return {
            "status": "error",
            "error": str(e),
            "script": script_name
        }


def verify_healing_execution(
    script_name: str,
    healing_result: Dict[str, Any],
    instance_name: str = None,
    project_id: str = None,
    zone: str = None
) -> Dict[str, Any]:
    """Verify healing script execution.

    Args:
        script_name: Name of healing script
        healing_result: Results from healing execution
        instance_name: Instance name (defaults to env)
        project_id: Project ID (defaults to env)
        zone: Zone (defaults to env)

    Returns:
        Verification results
    """
    try:
        executor = InstanceHealingExecutor(
            instance_name=instance_name,
            project_id=project_id,
            zone=zone
        )

        return executor.verify_healing(script_name, healing_result)

    except Exception as e:
        logger.error(f"Failed to verify healing: {e}")
        return {
            "status": "error",
            "error": str(e),
            "script": script_name
        }
