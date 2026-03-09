"""
Instance Monitor Agent — Primary monitoring agent for vlgdbzo3 HANA instance.
Runs diagnostic checks and detects issues requiring healing.
"""

from google.genai import types
from adk_app.tools.instance_diagnostics import run_instance_diagnostic
from adk_app.tools.instance_logger import log_diagnostic, log_agent_action
import logging

logger = logging.getLogger(__name__)

# Agent tools

def run_diagnostic_check() -> str:
    """Run full diagnostic check on vlgdbzo3 instance.

    Returns:
        Formatted diagnostic results
    """
    try:
        log_agent_action(
            action_type="DIAGNOSTIC_STARTED",
            details="Running diagnostic check on vlgdbzo3",
            agent_name="instance_monitor_agent"
        )

        # Run diagnostic
        result = run_instance_diagnostic()

        # Log results
        if result.get('status') != 'error':
            log_diagnostic(result)

            log_agent_action(
                action_type="DIAGNOSTIC_COMPLETED",
                details=f"Diagnostic completed: {result.get('issue_count', 0)} issues detected, severity: {result.get('overall_status', 'unknown')}",
                severity="INFO" if result.get('overall_status') == 'ok' else "WARNING",
                agent_name="instance_monitor_agent"
            )
        else:
            log_agent_action(
                action_type="DIAGNOSTIC_FAILED",
                details=f"Diagnostic failed: {result.get('error_message', 'Unknown error')}",
                severity="ERROR",
                agent_name="instance_monitor_agent"
            )

        # Format output
        output = f"""
Diagnostic Check Completed
==========================
Diagnostic ID: {result.get('diagnostic_id', 'N/A')}
Instance: {result.get('instance_name', 'vlgdbzo3')}
SID: {result.get('sid', 'ZO3')}
Overall Status: {result.get('overall_status', 'unknown').upper()}
Issues Detected: {result.get('issue_count', 0)}

"""

        if result.get('issues_detected'):
            output += "Issues:\n"
            for issue in result['issues_detected']:
                output += f"  - {issue}\n"
        else:
            output += "No issues detected.\n"

        output += "\nCheck Details:\n"
        checks = result.get('checks', {})
        for check_name, check_result in checks.items():
            status_icon = "✓" if check_result.get('severity') == 'ok' else "⚠" if check_result.get('severity') == 'warning' else "✗"
            output += f"{status_icon} {check_name}: {check_result.get('severity', 'unknown')}\n"

        return output

    except Exception as e:
        logger.error(f"Diagnostic check failed: {e}")
        return f"Error running diagnostic: {str(e)}"


def identify_required_healing(diagnostic_id: str = None) -> str:
    """Analyze diagnostic results and recommend healing scripts.

    Args:
        diagnostic_id: Diagnostic ID to analyze (uses latest if not provided)

    Returns:
        Recommended healing actions
    """
    try:
        # For now, this is a placeholder that analyzes the last diagnostic
        # In full implementation, this would look up the diagnostic by ID

        recommendations = []

        # Logic to map issues to healing scripts
        # This would be expanded based on actual diagnostic data

        output = "Healing Recommendations:\n"
        output += "======================\n\n"

        if not recommendations:
            output += "No healing actions required at this time.\n"
        else:
            for idx, rec in enumerate(recommendations, 1):
                output += f"{idx}. {rec['script']}\n"
                output += f"   Risk Level: {rec['risk']}\n"
                output += f"   Reason: {rec['reason']}\n\n"

        return output

    except Exception as e:
        logger.error(f"Failed to identify healing: {e}")
        return f"Error identifying healing actions: {str(e)}"


# Agent definition

instance_monitor_agent_tools = [
    types.Tool(function_declarations=[
        types.FunctionDeclaration(
            name="run_diagnostic_check",
            description="Run complete diagnostic check on vlgdbzo3 HANA instance. Checks process status, disk usage, memory, userstore, alerts, backups, system parameters, and trace files.",
            parameters=types.Schema(
                type=types.Type.OBJECT,
                properties={},
                required=[]
            )
        ),
        types.FunctionDeclaration(
            name="identify_required_healing",
            description="Analyze diagnostic results and recommend appropriate healing scripts based on detected issues.",
            parameters=types.Schema(
                type=types.Type.OBJECT,
                properties={
                    "diagnostic_id": types.Schema(
                        type=types.Type.STRING,
                        description="Diagnostic ID to analyze (optional, uses latest if not provided)"
                    )
                },
                required=[]
            )
        )
    ])
]

instance_monitor_agent_instructions = """
You are the Instance Monitor Agent for the vlgdbzo3 HANA instance on GCP.

Your PRIMARY responsibilities:
1. Run diagnostic checks on the HANA instance
2. Analyze check results and detect issues
3. Classify issue severity (INFO, WARNING, CRITICAL)
4. Recommend appropriate healing actions when issues are found
5. Document all findings in logs

DIAGNOSTIC CHECKS YOU PERFORM:
1. HANA Process Status - Check all processes are GREEN
2. HDB Info - Verify database is running
3. Disk Usage - Check all HANA partitions (alert if >85%)
4. Database Version - Log current HANA version
5. Userstore Keys - Verify BKPMON, SAPDBCTRL, SYSTEM, TRANSPORT
6. Database Alerts - Check M_ALERTS for issues in last 24h
7. Memory Usage - Check system memory (alert if >90%)
8. Backup Status - Verify last backup is < 24h old
9. System Parameters - Check swappiness=10, THP=[never], ASLR=0
10. Trace Directory - Check trace files and directory size

ISSUE DETECTION RULES:
- Process Status: Any non-GREEN process = CRITICAL
- Disk Usage: >85% = WARNING, >90% = CRITICAL
- Memory: >85% = WARNING, >95% = CRITICAL
- Backup Age: >24h = WARNING, >48h = CRITICAL
- Userstore: Missing keys = WARNING
- System Parameters: Wrong values = WARNING
- Database Alerts: Rating >3 = WARNING, Rating >4 = CRITICAL

HEALING SCRIPT MAPPING:
- Userstore issues → auto_db_userstoremanagement (Risk: MEDIUM)
- Backup path/trace issues → auto_db_metadata (Risk: MEDIUM-HIGH)
- System parameter issues → auto_db_dbintegrations (Risk: HIGH)
- Backup validation issues → auto_db_eligibility (Risk: MEDIUM)

SAFETY RULES (CRITICAL):
- ALL diagnostic operations are READ-ONLY
- NEVER modify system state directly
- ALWAYS run diagnostics before recommending healing
- ALWAYS use zo3adm user context for HANA commands
- NEVER execute healing scripts (that's healing agent's job)
- Document EVERYTHING in logs
- If uncertain, escalate to human operator

WHEN TO TRIGGER HEALING AGENT:
- CRITICAL severity issues require immediate attention
- WARNING severity issues should be monitored
- Multiple related issues may indicate need for specific healing script
- Always create action certificate before proposing healing

COMMUNICATION STYLE:
- Be clear and concise
- Report facts, not opinions
- Use severity levels consistently
- Provide actionable recommendations
- Include diagnostic IDs for tracking

Remember: You are the EYES of the system. Your job is to OBSERVE and REPORT, not to act. The healing agent handles actual fixes.
"""

# Tool execution mapping
INSTANCE_MONITOR_TOOLS = {
    "run_diagnostic_check": run_diagnostic_check,
    "identify_required_healing": identify_required_healing
}
