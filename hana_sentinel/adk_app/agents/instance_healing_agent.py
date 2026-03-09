"""
Instance Healing Agent — Execution agent for healing/fixing scripts on vlgdbzo3.
Implements all 4 toolkit healing scripts with approval workflow.
"""

from google.genai import types
from adk_app.tools.instance_healing_tools import execute_healing_script, verify_healing_execution
from adk_app.tools.instance_logger import log_healing, log_verification, log_agent_action
import logging

logger = logging.getLogger(__name__)

# Agent tools

def execute_userstore_healing(keys_to_fix: list = None) -> str:
    """Execute auto_db_userstoremanagement healing script.

    Args:
        keys_to_fix: List of userstore keys to fix (optional)

    Returns:
        Healing execution results
    """
    try:
        log_agent_action(
            action_type="HEALING_STARTED",
            details="Executing auto_db_userstoremanagement",
            agent_name="instance_healing_agent"
        )

        parameters = {"keys_to_fix": keys_to_fix} if keys_to_fix else {}
        result = execute_healing_script("auto_db_userstoremanagement", parameters)

        # Log results
        log_healing(result, "auto_db_userstoremanagement")

        # Verify
        verification = verify_healing_execution("auto_db_userstoremanagement", result)
        log_verification(verification, "auto_db_userstoremanagement")

        log_agent_action(
            action_type="HEALING_COMPLETED",
            details=f"Userstore healing completed: {result.get('status', 'unknown')}",
            severity="INFO" if result.get('status') == 'success' else "WARNING",
            agent_name="instance_healing_agent"
        )

        # Format output
        output = f"""
Userstore Management Healing
==============================
Script: auto_db_userstoremanagement
Status: {result.get('status', 'unknown').upper()}
Risk Level: MEDIUM (6 points)

Keys Fixed: {len(result.get('keys_fixed', []))}
Keys Failed: {len(result.get('keys_failed', []))}

"""

        if result.get('keys_fixed'):
            output += "Successfully Fixed:\n"
            for key in result['keys_fixed']:
                output += f"  ✓ {key}\n"

        if result.get('keys_failed'):
            output += "\nFailed:\n"
            for failure in result['keys_failed']:
                output += f"  ✗ {failure.get('key', 'Unknown')}: {failure.get('error', failure.get('reason', 'Unknown'))}\n"

        output += f"\nVerification Status: {verification.get('overall_status', 'unknown').upper()}\n"
        output += f"Checks Passed: {verification.get('checks_passed', 0)}/{len(verification.get('verification_checks', []))}\n"

        return output

    except Exception as e:
        logger.error(f"Userstore healing failed: {e}")
        return f"Error executing userstore healing: {str(e)}"


def execute_metadata_healing(issues: list = None) -> str:
    """Execute auto_db_metadata healing script.

    Args:
        issues: List of specific issues to fix (optional)

    Returns:
        Healing execution results
    """
    try:
        log_agent_action(
            action_type="HEALING_STARTED",
            details="Executing auto_db_metadata",
            agent_name="instance_healing_agent"
        )

        parameters = {"issues": issues} if issues else {}
        result = execute_healing_script("auto_db_metadata", parameters)

        # Log results
        log_healing(result, "auto_db_metadata")

        # Verify
        verification = verify_healing_execution("auto_db_metadata", result)
        log_verification(verification, "auto_db_metadata")

        log_agent_action(
            action_type="HEALING_COMPLETED",
            details=f"Metadata healing completed: {result.get('status', 'unknown')}",
            severity="INFO" if result.get('status') == 'success' else "WARNING",
            agent_name="instance_healing_agent"
        )

        # Format output
        output = f"""
Database Metadata Healing
==========================
Script: auto_db_metadata
Status: {result.get('status', 'unknown').upper()}
Risk Level: MEDIUM-HIGH (8 points)

Fixes Applied: {len(result.get('fixes_applied', []))}
Fixes Failed: {len(result.get('fixes_failed', []))}

"""

        if result.get('fixes_applied'):
            output += "Successfully Applied:\n"
            for fix in result['fixes_applied']:
                output += f"  ✓ {fix}\n"

        if result.get('fixes_failed'):
            output += "\nFailed:\n"
            for failure in result['fixes_failed']:
                output += f"  ✗ {failure.get('fix', 'Unknown')}: {failure.get('error', 'Unknown')}\n"

        output += f"\nVerification Status: {verification.get('overall_status', 'unknown').upper()}\n"

        return output

    except Exception as e:
        logger.error(f"Metadata healing failed: {e}")
        return f"Error executing metadata healing: {str(e)}"


def execute_integrations_healing(parameters: list = None) -> str:
    """Execute auto_db_dbintegrations healing script (HIGH RISK).

    Args:
        parameters: List of specific parameters to fix (optional)

    Returns:
        Healing execution results
    """
    try:
        log_agent_action(
            action_type="HEALING_STARTED",
            details="Executing auto_db_dbintegrations (HIGH RISK)",
            severity="WARNING",
            agent_name="instance_healing_agent"
        )

        params = {"parameters": parameters} if parameters else {}
        result = execute_healing_script("auto_db_dbintegrations", params)

        # Log results
        log_healing(result, "auto_db_dbintegrations")

        # Verify
        verification = verify_healing_execution("auto_db_dbintegrations", result)
        log_verification(verification, "auto_db_dbintegrations")

        log_agent_action(
            action_type="HEALING_COMPLETED",
            details=f"DB integrations healing completed: {result.get('status', 'unknown')}",
            severity="INFO" if result.get('status') == 'success' else "WARNING",
            agent_name="instance_healing_agent"
        )

        # Format output
        output = f"""
Database Integrations Healing (HIGH RISK)
==========================================
Script: auto_db_dbintegrations
Status: {result.get('status', 'unknown').upper()}
Risk Level: HIGH (12 points)

⚠️  This script modifies OS-level system settings!

Fixes Applied: {len(result.get('fixes_applied', []))}
Fixes Failed: {len(result.get('fixes_failed', []))}

"""

        if result.get('fixes_applied'):
            output += "Successfully Applied:\n"
            for fix in result['fixes_applied']:
                output += f"  ✓ {fix}\n"

        if result.get('fixes_failed'):
            output += "\nFailed:\n"
            for failure in result['fixes_failed']:
                output += f"  ✗ {failure.get('fix', 'Unknown')}: {failure.get('error', 'Unknown')}\n"

        output += f"\nVerification Status: {verification.get('overall_status', 'unknown').upper()}\n"

        if verification.get('verification_checks'):
            output += "\nSystem Parameters:\n"
            for check in verification['verification_checks']:
                status_icon = "✓" if check['status'] == 'pass' else "✗"
                output += f"  {status_icon} {check['check']}: {check.get('value', 'N/A')}\n"

        return output

    except Exception as e:
        logger.error(f"Integrations healing failed: {e}")
        return f"Error executing integrations healing: {str(e)}"


def execute_eligibility_healing(checks: list = None) -> str:
    """Execute auto_db_eligibility healing script.

    Args:
        checks: List of specific checks to perform (optional)

    Returns:
        Healing execution results
    """
    try:
        log_agent_action(
            action_type="HEALING_STARTED",
            details="Executing auto_db_eligibility",
            agent_name="instance_healing_agent"
        )

        parameters = {"checks": checks} if checks else {}
        result = execute_healing_script("auto_db_eligibility", parameters)

        # Log results
        log_healing(result, "auto_db_eligibility")

        # Verify
        verification = verify_healing_execution("auto_db_eligibility", result)
        log_verification(verification, "auto_db_eligibility")

        log_agent_action(
            action_type="HEALING_COMPLETED",
            details=f"Eligibility healing completed: {result.get('status', 'unknown')}",
            severity="INFO" if result.get('status') == 'success' else "WARNING",
            agent_name="instance_healing_agent"
        )

        # Format output
        output = f"""
Database Eligibility Healing
=============================
Script: auto_db_eligibility
Status: {result.get('status', 'unknown').upper()}
Risk Level: MEDIUM (6 points)

Fixes Applied: {len(result.get('fixes_applied', []))}
Fixes Failed: {len(result.get('fixes_failed', []))}

"""

        if result.get('fixes_applied'):
            output += "Successfully Applied:\n"
            for fix in result['fixes_applied']:
                output += f"  ✓ {fix}\n"

        if result.get('fixes_failed'):
            output += "\nFailed:\n"
            for failure in result['fixes_failed']:
                output += f"  ✗ {failure.get('fix', 'Unknown')}: {failure.get('error', 'Unknown')}\n"

        output += f"\nVerification Status: {verification.get('overall_status', 'unknown').upper()}\n"

        return output

    except Exception as e:
        logger.error(f"Eligibility healing failed: {e}")
        return f"Error executing eligibility healing: {str(e)}"


# Agent definition

instance_healing_agent_tools = [
    types.Tool(function_declarations=[
        types.FunctionDeclaration(
            name="execute_userstore_healing",
            description="Execute auto_db_userstoremanagement healing script to fix HANA userstore connectivity issues. Risk: MEDIUM (6 points). Requires approval.",
            parameters=types.Schema(
                type=types.Type.OBJECT,
                properties={
                    "keys_to_fix": types.Schema(
                        type=types.Type.ARRAY,
                        description="List of userstore keys to fix (e.g., ['BKPMON', 'SYSTEM']). Defaults to all standard keys if not provided.",
                        items=types.Schema(type=types.Type.STRING)
                    )
                },
                required=[]
            )
        ),
        types.FunctionDeclaration(
            name="execute_metadata_healing",
            description="Execute auto_db_metadata healing script to fix backup paths, trace permissions, and DB parameters. Risk: MEDIUM-HIGH (8 points). Requires approval.",
            parameters=types.Schema(
                type=types.Type.OBJECT,
                properties={
                    "issues": types.Schema(
                        type=types.Type.ARRAY,
                        description="List of specific issues to fix (e.g., ['backup_paths', 'trace_permissions']). Defaults to all if not provided.",
                        items=types.Schema(type=types.Type.STRING)
                    )
                },
                required=[]
            )
        ),
        types.FunctionDeclaration(
            name="execute_integrations_healing",
            description="Execute auto_db_dbintegrations healing script to fix OS-level settings (swappiness, THP, ASLR). Risk: HIGH (12 points). Requires explicit approval.",
            parameters=types.Schema(
                type=types.Type.OBJECT,
                properties={
                    "parameters": types.Schema(
                        type=types.Type.ARRAY,
                        description="List of specific parameters to fix (e.g., ['swappiness', 'thp', 'aslr']). Defaults to all if not provided.",
                        items=types.Schema(type=types.Type.STRING)
                    )
                },
                required=[]
            )
        ),
        types.FunctionDeclaration(
            name="execute_eligibility_healing",
            description="Execute auto_db_eligibility healing script to validate and fix database eligibility criteria (backups, archives). Risk: MEDIUM (6 points). Requires approval.",
            parameters=types.Schema(
                type=types.Type.OBJECT,
                properties={
                    "checks": types.Schema(
                        type=types.Type.ARRAY,
                        description="List of specific checks to perform (e.g., ['backup_config', 'archive_dirs']). Defaults to all if not provided.",
                        items=types.Schema(type=types.Type.STRING)
                    )
                },
                required=[]
            )
        )
    ])
]

instance_healing_agent_instructions = """
You are the Instance Healing Agent for the vlgdbzo3 HANA instance on GCP.

Your PRIMARY responsibility:
Execute healing/fixing scripts when problems are detected by the monitor agent.

AVAILABLE HEALING SCRIPTS:

1. auto_db_userstoremanagement (Risk: MEDIUM = 6 points)
   - Purpose: Fix HANA userstore connectivity issues
   - When: Userstore keys not working or misconfigured
   - Actions: Reconfigure userstore keys (BKPMON, SAPDBCTRL, SYSTEM, TRANSPORT)
   - Verification: Test connection with each key

2. auto_db_metadata (Risk: MEDIUM-HIGH = 8 points)
   - Purpose: Fix database metadata issues
   - When: Backup paths wrong, trace permission issues, DB parameter drift
   - Actions: Configure backup paths, fix trace permissions, reset parameters
   - Verification: Query M_BACKUP_CONFIGURATION, check permissions

3. auto_db_dbintegrations (Risk: HIGH = 12 points)
   - Purpose: Fix OS-level database integration settings
   - When: System parameters drift (swappiness, THP, ASLR)
   - Actions: Modify /proc/sys settings, set kernel parameters
   - Verification: Check /proc/sys values
   - ⚠️  HIGH RISK: Modifies OS settings!

4. auto_db_eligibility (Risk: MEDIUM = 6 points)
   - Purpose: Validate and fix database eligibility
   - When: Backup validation fails, archive issues
   - Actions: Validate backups, create archive directories, check system DB
   - Verification: Query M_BACKUP_CATALOG, check archive directories

SAFETY RULES (CRITICAL - PRODUCTION ENVIRONMENT):
- ⚠️  NEVER execute healing scripts without EXPLICIT APPROVAL
- ALWAYS create action certificate before proposing healing
- ALWAYS verify after healing execution
- ALWAYS log all operations
- HIGH-RISK scripts require synchronous HITL approval
- Deduct risk budget points BEFORE execution
- Document rollback steps for every operation
- If verification fails, DO NOT mark as complete

APPROVAL WORKFLOW:
1. Monitor agent detects issue
2. YOU propose healing script with:
   - Issue description
   - Recommended script
   - Risk assessment
   - Expected changes
   - Rollback plan
3. Wait for human approval via UI
4. Execute healing script after approval
5. Run verification
6. Report results
7. Update risk budget

RISK BUDGET MANAGEMENT:
- Check available budget before proposing
- Each script has fixed cost (6, 8, or 12 points)
- Daily baseline: 100 points
- If budget exhausted, ESCALATE (do not execute)
- If HIGH-RISK (>12 points), requires HITL-sync approval

VERIFICATION MANDATORY:
- Every healing execution MUST be verified
- Verification checks script-specific outcomes
- Only mark complete if verification passes
- If verification fails, report to human for investigation

ERROR HANDLING:
- Log all errors with full details
- Do not retry failed operations automatically
- Escalate persistent failures
- Provide clear error messages for troubleshooting

COMMUNICATION STYLE:
- Clear proposal with risk assessment
- Step-by-step execution reporting
- Transparent about failures
- Include verification results
- Provide log file references

INTEGRATION WITH OTHER AGENTS:
- Monitor agent: Provides issue detection
- Backup agent: May snapshot before high-risk operations
- Root supervisor: Enforces governance and budget

Remember: You are the HANDS of the system. Your job is to FIX problems SAFELY with APPROVAL. Never act without permission in production!
"""

# Tool execution mapping
INSTANCE_HEALING_TOOLS = {
    "execute_userstore_healing": execute_userstore_healing,
    "execute_metadata_healing": execute_metadata_healing,
    "execute_integrations_healing": execute_integrations_healing,
    "execute_eligibility_healing": execute_eligibility_healing
}
