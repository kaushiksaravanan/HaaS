"""
Instance Backup Agent — VM snapshot management for vlgdbzo3 HANA instance.
Creates daily VM snapshots (one per day, never deletes).
"""

from google.genai import types
from adk_app.tools.gcp_snapshot_tools import create_instance_snapshot, list_instance_snapshots
from adk_app.tools.instance_logger import log_snapshot, log_agent_action
import logging

logger = logging.getLogger(__name__)

# Agent tools

def create_daily_snapshot() -> str:
    """Create daily VM snapshot of vlgdbzo3 instance.

    Returns:
        Snapshot creation results
    """
    try:
        log_agent_action(
            action_type="SNAPSHOT_REQUESTED",
            details="Creating daily VM snapshot for vlgdbzo3",
            agent_name="instance_backup_agent"
        )

        # Create snapshot
        result = create_instance_snapshot()

        # Log results
        log_snapshot(result)

        if result.get('status') == 'success':
            log_agent_action(
                action_type="SNAPSHOT_COMPLETED",
                details=f"Snapshot completed: {len(result.get('snapshots', []))} created, {len(result.get('skipped', []))} skipped",
                severity="INFO",
                agent_name="instance_backup_agent"
            )
        elif result.get('status') == 'partial':
            log_agent_action(
                action_type="SNAPSHOT_PARTIAL",
                details=f"Snapshot partially completed: {len(result.get('snapshots', []))} created, {len(result.get('errors', []))} errors",
                severity="WARNING",
                agent_name="instance_backup_agent"
            )
        else:
            log_agent_action(
                action_type="SNAPSHOT_FAILED",
                details=f"Snapshot failed: {result.get('error_message', 'Unknown error')}",
                severity="ERROR",
                agent_name="instance_backup_agent"
            )

        # Format output
        output = f"""
Daily VM Snapshot Results
=========================
Instance: {result.get('instance', 'vlgdbzo3')}
Status: {result.get('status', 'unknown').upper()}

"""

        if result.get('snapshots'):
            output += "Snapshots Created:\n"
            for snapshot in result['snapshots']:
                output += f"  ✓ {snapshot.get('snapshot_name', 'Unknown')}\n"
                output += f"    Disk: {snapshot.get('disk_name', 'Unknown')}\n"
                output += f"    Time: {snapshot.get('timestamp', 'N/A')}\n"
            output += "\n"

        if result.get('skipped'):
            output += "Skipped (already exists today):\n"
            for skipped in result['skipped']:
                output += f"  - {skipped.get('disk_name', 'Unknown')}\n"
                output += f"    Existing: {skipped.get('existing_snapshot', 'N/A')}\n"
            output += "\n"

        if result.get('errors'):
            output += "Errors:\n"
            for error in result['errors']:
                output += f"  ✗ {error.get('disk_name', 'Unknown')}: {error.get('error_message', 'Unknown error')}\n"
            output += "\n"

        output += f"\nRisk Budget Cost: 3 points (snapshot creation)\n"

        return output

    except Exception as e:
        logger.error(f"Snapshot creation failed: {e}")
        return f"Error creating snapshot: {str(e)}"


def list_snapshots(days: int = 7) -> str:
    """List recent VM snapshots for vlgdbzo3 instance.

    Args:
        days: Number of days to look back (default: 7)

    Returns:
        List of snapshots
    """
    try:
        # List snapshots
        snapshots = list_instance_snapshots()

        # Format output
        output = f"""
VM Snapshots for vlgdbzo3
=========================
Showing snapshots from last {days} days

"""

        if not snapshots:
            output += "No snapshots found.\n"
        else:
            for idx, snapshot in enumerate(snapshots[:20], 1):  # Show up to 20
                output += f"{idx}. {snapshot.get('name', 'Unknown')}\n"
                output += f"   Created: {snapshot.get('creation_time', 'N/A')}\n"
                output += f"   Size: {snapshot.get('disk_size_gb', 'Unknown')} GB\n"
                output += f"   Status: {snapshot.get('status', 'Unknown')}\n"
                if snapshot.get('description'):
                    output += f"   Description: {snapshot['description']}\n"
                output += "\n"

            if len(snapshots) > 20:
                output += f"... and {len(snapshots) - 20} more snapshots\n"

        output += f"\nTotal snapshots: {len(snapshots)}\n"
        output += "\nNote: Snapshots are NEVER deleted automatically. Manual cleanup required.\n"

        return output

    except Exception as e:
        logger.error(f"Failed to list snapshots: {e}")
        return f"Error listing snapshots: {str(e)}"


def get_snapshot_status() -> str:
    """Get current snapshot backup status.

    Returns:
        Snapshot status summary
    """
    try:
        # Get today's snapshots
        snapshots = list_instance_snapshots()

        from datetime import datetime
        today = datetime.now().strftime("%Y%m%d")

        today_snapshots = [
            s for s in snapshots
            if s.get('creation_time', '').startswith(today)
        ]

        output = """
Snapshot Backup Status
======================

"""

        if today_snapshots:
            output += f"✓ Backup completed today: {len(today_snapshots)} snapshot(s)\n\n"
            for snapshot in today_snapshots:
                output += f"  - {snapshot.get('name', 'Unknown')}\n"
                output += f"    Created: {snapshot.get('creation_time', 'N/A')}\n"
        else:
            output += "⚠ No backup created today yet.\n"
            output += "   Run create_daily_snapshot to create today's backup.\n"

        output += f"\n Total snapshots available: {len(snapshots)}\n"

        return output

    except Exception as e:
        logger.error(f"Failed to get snapshot status: {e}")
        return f"Error getting snapshot status: {str(e)}"


# Agent definition

instance_backup_agent_tools = [
    types.Tool(function_declarations=[
        types.FunctionDeclaration(
            name="create_daily_snapshot",
            description="Create daily VM snapshot of vlgdbzo3 instance. Only one snapshot per day is created. If snapshot already exists for today, it will be skipped. Snapshots are NEVER deleted automatically.",
            parameters=types.Schema(
                type=types.Type.OBJECT,
                properties={},
                required=[]
            )
        ),
        types.FunctionDeclaration(
            name="list_snapshots",
            description="List recent VM snapshots for vlgdbzo3 instance.",
            parameters=types.Schema(
                type=types.Type.OBJECT,
                properties={
                    "days": types.Schema(
                        type=types.Type.INTEGER,
                        description="Number of days to look back (default: 7)"
                    )
                },
                required=[]
            )
        ),
        types.FunctionDeclaration(
            name="get_snapshot_status",
            description="Get current snapshot backup status, including whether today's backup has been completed.",
            parameters=types.Schema(
                type=types.Type.OBJECT,
                properties={},
                required=[]
            )
        )
    ])
]

instance_backup_agent_instructions = """
You are the Instance Backup Agent for the vlgdbzo3 HANA instance on GCP.

Your PRIMARY responsibility:
Create and manage daily VM snapshots for disaster recovery.

BACKUP STRATEGY:
1. ONE snapshot per day maximum
2. Snapshots are created for ALL disks attached to the instance
3. NEVER delete snapshots automatically (manual cleanup only)
4. Check if snapshot already exists before creating
5. Use GCP Compute Engine snapshot API

SNAPSHOT NAMING:
Format: {instance_name}-{disk_name}-{YYYYMMDD-HHMMSS}
Example: vlgdbzo3-boot-disk-20260304-103000

RISK BUDGET:
- Snapshot creation: 3 points (MEDIUM risk)
- Snapshot listing: 0 points (read-only)
- Status check: 0 points (read-only)

SAFETY RULES (CRITICAL):
- Only create ONE snapshot per day per disk
- Check for existing snapshots before creating
- NEVER delete snapshots (user must delete manually)
- Log all snapshot operations
- Snapshots are stored in GCP project, incur storage costs
- Reversible operation (can restore from snapshot)

WHEN TO CREATE SNAPSHOTS:
- Daily scheduled backup (typically after hours)
- Before major system changes
- After successful HANA backup completion
- On-demand when requested by human operator

MONITORING:
- Track snapshot success/failure rate
- Alert if snapshot creation fails
- Monitor storage costs (informational only)
- Report snapshot age and retention

ERROR HANDLING:
- If snapshot fails, log error and escalate
- Do not retry automatically (may indicate resource issues)
- Report disk space constraints
- Report permission issues

COMMUNICATION STYLE:
- Clear status reporting
- Indicate success/skip/failure for each disk
- Provide snapshot names for reference
- Estimate storage impact when relevant
- Remind that snapshots persist until manually deleted

INTEGRATION WITH OTHER AGENTS:
- Monitor agent: Provides system health before snapshot
- Healing agent: May trigger snapshot before risky operations
- Root supervisor: Reports backup status for governance

Remember: Snapshots are your safety net. Be reliable, be consistent, never delete without permission.
"""

# Tool execution mapping
INSTANCE_BACKUP_TOOLS = {
    "create_daily_snapshot": create_daily_snapshot,
    "list_snapshots": list_snapshots,
    "get_snapshot_status": get_snapshot_status
}
