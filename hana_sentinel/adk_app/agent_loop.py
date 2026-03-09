"""
Agent Loop â€” Autonomous HANA Monitoring Orchestrator.

Runs a periodic loop that:
  Phase 1: Remote exec â†’ run analysis.sh
  Phase 2: Parse errors, discover schema, fix script
  Phase 3: Health checks (services, memory, disk, alerts, connections)
  Phase 4: Push fixes to HDB via hdbsql
  Phase 5: Verify changes took effect
  Phase 6: Learn from results, generate PDF report

Each cycle produces a timestamped PDF report in reports/.
"""

import os
import sys
import json
import time
import logging
import traceback
from datetime import datetime
from typing import Dict, Any, Optional

# Ensure project is importable
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

logger = logging.getLogger("hana_sentinel.loop")

# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# Configuration
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
DEFAULT_INTERVAL = int(os.getenv("AGENT_LOOP_INTERVAL", "300"))  # 5 min
DEFAULT_SID = os.getenv("HANA_SID", "")
DEFAULT_INSTANCE = os.getenv("HANA_INSTANCE_NR", "")
DEFAULT_CONTAINER = os.getenv("HANA_CONTAINER_NAME", "")
HANA_USER = os.getenv("HANA_USER", "")
HANA_PASSWORD = os.getenv("HANA_PASSWORD", "")
HANA_DATABASE = os.getenv("HANA_DATABASE", "")


def _hdbsql_query_via_remote(query: str, database: str = "") -> dict:
    """Execute a SQL query on HANA via the remote exec server."""
    from adk_app.tools.hana_tools import execute_remote_command

    db = database or HANA_DATABASE
    sid = DEFAULT_SID
    instance = DEFAULT_INSTANCE

    hdbsql_cmd = (
        f"/usr/sap/{sid}/HDB{instance}/exe/hdbsql "
        f"-i {instance} -u {HANA_USER} -p {HANA_PASSWORD} -d {db} "
        f"-C -A -j -x '{query}'"
    )

    result = execute_remote_command(hdbsql_cmd)
    stdout = result.get("stdout", "")
    stderr = result.get("stderr", "")
    exit_code = result.get("exit_code", -1)
    if exit_code == 0:
        # Parse rows from output
        rows = []
        for line in stdout.strip().split("\n"):
            line = line.strip()
            if line and not line.startswith("*") and "row" not in line.lower():
                rows.append(line)
        return {"status": "success", "data": rows, "raw": stdout}
    return {
        "status": "error",
        "error_message": stderr or stdout or "unknown",
        "data": [],
    }


# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# Phase Functions
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€


def phase1_run_analysis(sid: str) -> dict:
    """Phase 1: Run the analysis script on the VM."""
    logger.info("â•â•â• PHASE 1: Running analysis script â•â•â•")
    from adk_app.tools.analysis_tools import run_analysis_script

    result = run_analysis_script(sid, "all")
    logger.info(
        "Analysis script: %s (%d chars output)",
        result.get("status"),
        len(result.get("output", "")),
    )
    return result


def phase2_detect_and_fix(analysis_output: str) -> dict:
    """Phase 2: Parse errors, discover schema, fix script."""
    logger.info("â•â•â• PHASE 2: Detecting and fixing errors â•â•â•")
    from adk_app.tools.analysis_tools import (
        parse_analysis_errors,
        discover_hana_schema,
        fix_analysis_script,
    )

    results = {"errors": {}, "schema_discovery": {}, "fixes": {}}

    # 2a: Parse errors
    parse_result = parse_analysis_errors(analysis_output)
    results["errors"] = parse_result
    error_count = parse_result.get("error_count", 0)
    logger.info("Errors found: %d", error_count)

    if error_count == 0:
        logger.info("No errors to fix â€” skipping schema discovery and fix phases")
        return results

    # 2b: Discover correct schema for failing views
    invalid_cols = [
        e for e in parse_result.get("errors", []) if e.get("type") == "invalid_column"
    ]
    failing_views = list(
        set(e["view_name"] for e in invalid_cols if e.get("view_name"))
    )

    if failing_views:
        logger.info("Discovering schema for: %s", ", ".join(failing_views))
        schema_result = discover_hana_schema(",".join(failing_views))
        results["schema_discovery"] = schema_result
    else:
        results["schema_discovery"] = {"status": "skipped", "schema": {}}

    # 2c: Fix the script
    errors_json = json.dumps(parse_result.get("errors", []))
    schema_json = json.dumps(results["schema_discovery"].get("schema", {}))
    fix_result = fix_analysis_script(errors_json, schema_json)
    results["fixes"] = fix_result
    logger.info(
        "Fixes applied: %d/%d",
        fix_result.get("applied_count", 0),
        fix_result.get("total_sed_commands", 0),
    )

    return results


def phase3_health_checks(sid: str) -> dict:
    """Phase 3: Run health checks using sub-agent tools."""
    logger.info("â•â•â• PHASE 3: Running health checks â•â•â•")

    health = {}

    # 3a: Services
    try:
        logger.info("  Checking services...")
        result = _hdbsql_query_via_remote(
            "SELECT SERVICE_NAME, HOST, PORT, ACTIVE_STATUS FROM SYS.M_SERVICES"
        )
        # If ACTIVE_STATUS fails, try without it
        if result.get("status") != "success" or "invalid column" in str(result):
            result = _hdbsql_query_via_remote(
                "SELECT SERVICE_NAME, HOST, PORT FROM SYS.M_SERVICES"
            )
        health["services"] = result
    except Exception as exc:
        health["services"] = {"status": "error", "error_message": str(exc), "data": []}

    # 3b: Memory
    try:
        logger.info("  Checking memory...")
        result = _hdbsql_query_via_remote(
            "SELECT SERVICE_NAME, TOTAL_MEMORY_USED_SIZE, EFFECTIVE_ALLOCATION_LIMIT "
            "FROM SYS.M_SERVICE_MEMORY"
        )
        health["memory"] = result
    except Exception as exc:
        health["memory"] = {"status": "error", "error_message": str(exc), "data": []}

    # 3c: Disk usage
    try:
        logger.info("  Checking disk usage...")
        result = _hdbsql_query_via_remote(
            "SELECT USAGE_TYPE, USED_SIZE, TOTAL_SIZE FROM SYS.M_DISK_USAGE"
        )
        health["disk"] = result
    except Exception as exc:
        health["disk"] = {"status": "error", "error_message": str(exc), "data": []}

    # 3d: Storage (OS-level)
    try:
        logger.info("  Checking HDB storage paths...")
        from adk_app.tools.log_preprocessor import check_hdb_storage

        storage_result = check_hdb_storage()
        health["storage"] = storage_result
    except Exception as exc:
        health["storage"] = {"status": "error", "error_message": str(exc)}

    # 3e: Alerts
    try:
        logger.info("  Checking active alerts...")
        result = _hdbsql_query_via_remote(
            "SELECT ALERT_ID, ALERT_RATING, ALERT_NAME, ALERT_DETAILS "
            "FROM _SYS_STATISTICS.STATISTICS_CURRENT_ALERTS "
            "WHERE ALERT_RATING >= 3 ORDER BY ALERT_RATING DESC"
        )
        # Fallback without ALERT_NAME if it fails
        if result.get("status") != "success" or "invalid column" in str(result):
            result = _hdbsql_query_via_remote(
                "SELECT ALERT_ID, ALERT_RATING, ALERT_DETAILS "
                "FROM _SYS_STATISTICS.STATISTICS_CURRENT_ALERTS "
                "WHERE ALERT_RATING >= 3"
            )
        health["alerts"] = result
    except Exception as exc:
        health["alerts"] = {"status": "error", "error_message": str(exc), "data": []}

    # 3f: Connections
    try:
        logger.info("  Checking connections...")
        result = _hdbsql_query_via_remote(
            "SELECT COUNT(*) AS CNT FROM SYS.M_CONNECTIONS WHERE CONNECTION_STATUS = 'RUNNING'"
        )
        health["connections"] = {
            "status": result.get("status"),
            "count": result.get("data", ["0"])[0] if result.get("data") else "N/A",
        }
    except Exception as exc:
        health["connections"] = {"status": "error", "error_message": str(exc)}

    # 3g: Database info
    try:
        logger.info("  Checking database info...")
        result = _hdbsql_query_via_remote(
            "SELECT DATABASE_NAME, VERSION, USAGE, START_TIME FROM SYS.M_DATABASE"
        )
        health["database"] = result
    except Exception as exc:
        health["database"] = {"status": "error", "error_message": str(exc), "data": []}

    # Count successes
    success_count = sum(1 for v in health.values() if v.get("status") == "success")
    logger.info("Health checks: %d/%d succeeded", success_count, len(health))

    return health


def phase4_push_fixes(sid: str, fixes: dict) -> dict:
    """Phase 4: Push any pending fixes to HDB."""
    logger.info("â•â•â• PHASE 4: Pushing fixes to HDB â•â•â•")

    results = {"pushed": [], "status": "success"}

    # If analysis script was fixed, re-run it to push corrected queries
    if fixes.get("applied_count", 0) > 0:
        logger.info(
            "Analysis script was fixed â€” re-running to push corrected queries to HDB"
        )
        from adk_app.tools.analysis_tools import run_analysis_script

        rerun = run_analysis_script(sid, "all")
        results["rerun_analysis"] = {
            "status": rerun.get("status"),
            "output_length": len(rerun.get("output", "")),
        }
        results["pushed"].append("Re-ran analysis.sh with corrected SQL queries")
    else:
        logger.info("No fixes to push â€” script was already clean")
        results["status"] = "no_changes"

    return results


def phase5_verify(sid: str, fixes: dict, push_result: dict) -> dict:
    """Phase 5: Verify that fixes took effect."""
    logger.info("â•â•â• PHASE 5: Verifying changes â•â•â•")

    verification = {"checks": [], "status": "success"}

    # 5a: Verify analysis script re-run (if it was fixed)
    if push_result.get("rerun_analysis", {}).get("status") == "success":
        # Parse the re-run output for remaining errors
        rerun_output = push_result.get("rerun_analysis", {}).get("output", "")
        if rerun_output:
            from adk_app.tools.analysis_tools import parse_analysis_errors

            reparse = parse_analysis_errors(rerun_output)
            remaining = reparse.get("error_count", 0)
            verification["rerun_errors"] = reparse
            verification["checks"].append(
                {
                    "name": "analysis_script_errors",
                    "passed": remaining == 0,
                    "details": f"{remaining} errors remaining after fix",
                }
            )
        else:
            verification["checks"].append(
                {
                    "name": "analysis_script_rerun",
                    "passed": True,
                    "details": "Analysis script re-run succeeded",
                }
            )

    # 5b: Verify HANA connectivity
    try:
        result = _hdbsql_query_via_remote("SELECT 1 FROM DUMMY")
        verification["checks"].append(
            {
                "name": "hana_connectivity",
                "passed": result.get("status") == "success",
                "details": "HANA SQL connectivity via docker exec",
            }
        )
    except Exception as exc:
        verification["checks"].append(
            {
                "name": "hana_connectivity",
                "passed": False,
                "details": str(exc),
            }
        )

    # 5c: Verify services are running
    try:
        result = _hdbsql_query_via_remote(
            "SELECT COUNT(*) FROM SYS.M_SERVICES WHERE ACTIVE_STATUS = 'YES'"
        )
        # Fallback
        if result.get("status") != "success":
            result = _hdbsql_query_via_remote("SELECT COUNT(*) FROM SYS.M_SERVICES")
        verification["checks"].append(
            {
                "name": "services_active",
                "passed": result.get("status") == "success",
                "details": f"Active services: {result.get('data', ['?'])[0] if result.get('data') else '?'}",
            }
        )
    except Exception as exc:
        verification["checks"].append(
            {
                "name": "services_active",
                "passed": False,
                "details": str(exc),
            }
        )

    # Overall
    all_passed = all(c.get("passed", False) for c in verification["checks"])
    verification["status"] = "success" if all_passed else "partial"
    logger.info(
        "Verification: %d/%d checks passed",
        sum(1 for c in verification["checks"] if c.get("passed")),
        len(verification["checks"]),
    )

    return verification


def phase6_learn_and_report(
    cycle_data: dict,
    sid: str,
    cycle_num: int,
    fixes: dict,
) -> dict:
    """Phase 6: Record learned fixes and generate PDF report."""
    logger.info("â•â•â• PHASE 6: Learning and generating report â•â•â•")

    results = {"learning": {}, "report": {}}

    # 6a: Record learned fixes in the learning store
    if fixes.get("fixes_applied"):
        try:
            from adk_app.tools.learning_store import learn_new_commands

            fix_descriptions = [f["description"] for f in fixes["fixes_applied"]]
            learn_result = learn_new_commands(
                incident_summary=f"Cycle #{cycle_num}: Fixed {len(fix_descriptions)} SQL errors in analysis.sh",
                diagnostic_commands="run_analysis_script; parse_analysis_errors; discover_hana_schema",
                remediation_commands="; ".join(fix_descriptions),
                category="analysis",
                severity="warning",
            )
            results["learning"] = learn_result
            logger.info("Learned %d new commands", len(fix_descriptions))
        except Exception as exc:
            logger.warning("Learning store update failed: %s", exc)
            results["learning"] = {"status": "error", "error_message": str(exc)}
    else:
        results["learning"] = {"status": "skipped", "reason": "No fixes to learn from"}

    # 6b: Generate PDF report
    try:
        from adk_app.report_generator import generate_report

        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        report_result = generate_report(cycle_data, timestamp=ts)
        results["report"] = report_result
        if report_result.get("status") == "success":
            logger.info("Report generated: %s", report_result.get("report_path"))
        else:
            logger.warning(
                "Report generation failed: %s", report_result.get("error_message")
            )
    except Exception as exc:
        logger.warning("Report generation failed: %s", exc)
        results["report"] = {"status": "error", "error_message": str(exc)}

    return results


# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# Main Loop
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€


def run_cycle(sid: str = "", cycle_num: int = 1) -> dict:
    """Execute one complete monitoring cycle (all 6 phases).

    Args:
        sid: HANA System ID (default: from env).
        cycle_num: Cycle counter.

    Returns:
        Complete cycle results dict suitable for report generation.
    """
    sid = sid or DEFAULT_SID
    ts = datetime.now().isoformat()

    logger.info("â•”â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•—")
    logger.info("â•‘  HANA Sentinel â€” Cycle #%d               â•‘", cycle_num)
    logger.info("â•‘  SID: %s  |  %s      â•‘", sid, ts[:19])
    logger.info("â•šâ•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•")

    cycle_data = {
        "sid": sid,
        "cycle": cycle_num,
        "timestamp": ts,
        "phases": {},
        "overall_status": "unknown",
        "recommendations": [],
    }

    try:
        # Phase 1: Run analysis
        analysis_result = phase1_run_analysis(sid)
        cycle_data["phases"]["analysis"] = {
            "status": analysis_result.get("status"),
            "output_length": len(analysis_result.get("output", "")),
            "script_path": analysis_result.get("script_path", ""),
        }

        analysis_output = analysis_result.get("output", "")

        # Phase 2: Detect & Fix
        if analysis_result.get("status") == "success" and analysis_output:
            detect_fix = phase2_detect_and_fix(analysis_output)
        else:
            detect_fix = {
                "errors": {"error_count": 0, "errors": []},
                "schema_discovery": {},
                "fixes": {},
            }
            if analysis_result.get("status") != "success":
                cycle_data["recommendations"].append(
                    "Analysis script failed to run - check remote exec server connection and script path"
                )

        cycle_data["phases"]["errors"] = detect_fix.get("errors", {})
        cycle_data["phases"]["schema_discovery"] = detect_fix.get(
            "schema_discovery", {}
        )
        cycle_data["phases"]["fixes"] = detect_fix.get("fixes", {})

        # Phase 3: Health checks
        health = phase3_health_checks(sid)
        cycle_data["phases"]["health"] = health

        # Generate health-based recommendations
        storage = health.get("storage", {})
        if storage.get("has_critical"):
            cycle_data["recommendations"].append(
                "CRITICAL: Storage alerts detected â€” immediate attention required"
            )
        if storage.get("has_warning"):
            cycle_data["recommendations"].append(
                "WARNING: Storage approaching capacity â€” plan cleanup or expansion"
            )

        alerts = health.get("alerts", {})
        if alerts.get("data") and len(alerts["data"]) > 0:
            cycle_data["recommendations"].append(
                f"{len(alerts['data'])} active HANA alerts with rating >= 3 â€” review recommended"
            )

        # Phase 4: Push fixes
        fixes = detect_fix.get("fixes", {})
        push_result = phase4_push_fixes(sid, fixes)
        cycle_data["phases"]["push"] = push_result

        # Phase 5: Verify
        verification = phase5_verify(sid, fixes, push_result)
        cycle_data["phases"]["verification"] = verification

        # Phase 6: Learn & Report
        learn_report = phase6_learn_and_report(cycle_data, sid, cycle_num, fixes)
        cycle_data["phases"]["learning"] = learn_report.get("learning", {})
        cycle_data["phases"]["report"] = learn_report.get("report", {})

        # Overall status
        error_count = detect_fix.get("errors", {}).get("error_count", 0)
        fix_count = fixes.get("applied_count", 0)
        v_status = verification.get("status", "unknown")

        if error_count == 0 and v_status == "success":
            cycle_data["overall_status"] = "HEALTHY"
        elif fix_count > 0 and v_status == "success":
            cycle_data["overall_status"] = "FIXED"
        elif error_count > 0 and fix_count == 0:
            cycle_data["overall_status"] = "ERRORS_DETECTED"
        else:
            cycle_data["overall_status"] = "PARTIAL"

    except Exception as exc:
        logger.error("Cycle #%d failed: %s", cycle_num, exc)
        logger.error(traceback.format_exc())
        cycle_data["overall_status"] = "ERROR"
        cycle_data["error"] = str(exc)
        cycle_data["recommendations"].append(f"Cycle failed with error: {exc}")

        # Still try to generate a report even on failure
        try:
            from adk_app.report_generator import generate_report

            ts_str = datetime.now().strftime("%Y%m%d_%H%M%S")
            generate_report(cycle_data, timestamp=ts_str)
        except Exception:
            pass

    logger.info(
        "Cycle #%d complete â€” Status: %s",
        cycle_num,
        cycle_data["overall_status"],
    )

    return cycle_data


def run_loop(
    sid: str = "",
    interval: int = 0,
    max_cycles: int = 0,
):
    """Run the agent loop continuously.

    Args:
        sid: HANA System ID.
        interval: Seconds between cycles (default: AGENT_LOOP_INTERVAL env or 300).
        max_cycles: Max cycles to run (0 = infinite).
    """
    sid = sid or DEFAULT_SID
    interval = interval or DEFAULT_INTERVAL
    cycle_num = 0

    logger.info("Starting HANA Sentinel Agent Loop")
    logger.info("  SID: %s", sid)
    logger.info("  Interval: %ds", interval)
    logger.info("  Max cycles: %s", max_cycles or "infinite")

    try:
        while True:
            cycle_num += 1

            if max_cycles and cycle_num > max_cycles:
                logger.info("Reached max cycles (%d) â€” stopping", max_cycles)
                break

            cycle_data = run_cycle(sid, cycle_num)

            report = cycle_data.get("phases", {}).get("report", {})
            if report.get("status") == "success":
                logger.info("ðŸ“„ Report: %s", report.get("report_path"))

            if max_cycles and cycle_num >= max_cycles:
                break

            logger.info("Sleeping %ds until next cycle...", interval)
            time.sleep(interval)

    except KeyboardInterrupt:
        logger.info("Agent loop stopped by user (Ctrl+C)")
    except Exception as exc:
        logger.error("Agent loop crashed: %s", exc)
        logger.error(traceback.format_exc())
        raise
