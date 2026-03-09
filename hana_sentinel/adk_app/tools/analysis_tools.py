"""
Analysis Script Tools — Self-learning SQL error detection and correction.
Enables the HANA Sentinel agent to autonomously:
  1. Run analysis.sh on the VM
  2. Parse output for SQL errors (invalid column names)
  3. Discover correct HANA schema via system catalog
  4. Fix the script on the VM
  5. Re-run and record learned fixes

All tools use the HTTP remote exec server — no SSH connections.
"""

import os
import re
import logging
from typing import List, Dict, Optional

logger = logging.getLogger(__name__)

# ──────────────────────────────────────────────
# Constants
# ──────────────────────────────────────────────
_DEFAULT_CONTAINER = os.getenv("HANA_CONTAINER_NAME", "")
_DEFAULT_SID = os.getenv("HANA_SID", "")
_DEFAULT_INSTANCE = os.getenv("HANA_INSTANCE_NR", "")
_DEFAULT_USER = os.getenv("HANA_USER", "")
_DEFAULT_PASSWORD = os.getenv("HANA_PASSWORD", "")
_DEFAULT_DATABASE = os.getenv("HANA_DATABASE", "")
_SCRIPT_PATH = os.getenv("ANALYSIS_SCRIPT_PATH", "")

# Regex to extract invalid column errors from hdbsql output
_INVALID_COL_RE = re.compile(
    r"invalid column name:\s+(\w+).*?SQLSTATE:\s+HY000",
    re.IGNORECASE,
)

# Regex to extract the SQL query that caused the error
_QUERY_RE = re.compile(
    r"run_hdbsql\s+'(SELECT[^']+)'",
    re.IGNORECASE,
)

# Map known view names to their schema + table for catalog lookup
_VIEW_SCHEMA_MAP = {
    "M_DATABASE": ("SYS", "M_DATABASE"),
    "M_BACKUP_CATALOG": ("SYS", "M_BACKUP_CATALOG"),
    "STATISTICS_CURRENT_ALERTS": ("_SYS_STATISTICS", "STATISTICS_CURRENT_ALERTS"),
    "M_TRANSACTIONS": ("SYS", "M_TRANSACTIONS"),
    "M_CS_TABLES": ("SYS", "M_CS_TABLES"),
    "M_SERVICES": ("SYS", "M_SERVICES"),
    "M_CONNECTIONS": ("SYS", "M_CONNECTIONS"),
    "M_SERVICE_REPLICATION": ("SYS", "M_SERVICE_REPLICATION"),
    "M_HOST_RESOURCE_UTILIZATION": ("SYS", "M_HOST_RESOURCE_UTILIZATION"),
    "M_DISKS": ("SYS", "M_DISKS"),
    "M_LICENSE": ("SYS", "M_LICENSE"),
    "M_EXPENSIVE_STATEMENTS": ("SYS", "M_EXPENSIVE_STATEMENTS"),
    "M_DISK_USAGE": ("SYS", "M_DISK_USAGE"),
    "M_SERVICE_MEMORY": ("SYS", "M_SERVICE_MEMORY"),
}


# ──────────────────────────────────────────────
# Internal helpers
# ──────────────────────────────────────────────


def _hdbsql_via_docker(query: str, database: str = "") -> dict:
    """Execute an hdbsql query inside the HANA Docker container via the remote exec server.

    Args:
        query: SQL query to execute.
        database: Target database (default: SYSTEMDB).

    Returns:
        dict with status, stdout, stderr.
    """
    from .hana_tools import execute_remote_command

    db = database or _DEFAULT_DATABASE
    sid_lower = _DEFAULT_SID.lower()

    # Build the docker exec command
    hdbsql_path = f"/usr/sap/{_DEFAULT_SID}/HDB{_DEFAULT_INSTANCE}/exe/hdbsql"
    docker_cmd = (
        f"docker exec -u {sid_lower}adm {_DEFAULT_CONTAINER} "
        f"{hdbsql_path} "
        f"-i {_DEFAULT_INSTANCE} "
        f"-u {_DEFAULT_USER} "
        f"-p {_DEFAULT_PASSWORD} "
        f"-d {db} "
        f"-C -A -j -x "
        f"'{query}'"
    )

    return execute_remote_command(docker_cmd, admin_override=True)


def _extract_view_from_query(query: str) -> str:
    """Extract the main view/table name from a SELECT query.

    Looks for FROM <schema>.<table> or FROM <table> patterns.
    """
    match = re.search(
        r"\bFROM\s+(?:SYS\.|_SYS_STATISTICS\.)?(\w+)",
        query,
        re.IGNORECASE,
    )
    if match:
        return match.group(1).upper()
    return ""


# ──────────────────────────────────────────────
# ADK Tool Functions
# ──────────────────────────────────────────────


def run_analysis_script(sid: str = "", function: str = "all") -> dict:
    """Run the analysis.sh script on the remote VM and capture its output.
    The script executes hdbsql queries inside the HANA Docker container
    to gather system metrics.

    Args:
        sid (str): SAP HANA System ID (default: HXE).
        function (str): Which analysis function to run — 'all' or a specific
            function name like 'get_system_overview' (default: all).

    Returns:
        dict: status, full stdout output, and stderr from the script execution.
    """
    from .hana_tools import execute_remote_command

    sid = sid or _DEFAULT_SID
    script_path = _SCRIPT_PATH

    command = f"bash -x {script_path} {sid} {function}"
    result = execute_remote_command(command, admin_override=True)

    if result.get("status") == "success":
        return {
            "status": "success",
            "source": "remote_exec",
            "output": result.get("stdout", ""),
            "stderr": result.get("stderr", ""),
            "script_path": script_path,
            "sid": sid,
            "function": function,
        }
    return {
        "status": "error",
        "error_message": f"Failed to run analysis script: {result.get('error_message', result.get('stderr', 'unknown'))}",
        "methods_tried": result.get("methods_tried", []),
    }


def parse_analysis_errors(analysis_output: str) -> dict:
    """Parse the output of analysis.sh to detect SQL errors.
    Identifies invalid column names, failed queries, and the dispatch bug.

    Args:
        analysis_output (str): The full stdout from running analysis.sh
            (typically captured from run_analysis_script).

    Returns:
        dict: status, list of detected errors with details (view_name,
            bad_column, original_query, error_message), and a summary.
    """
    errors: List[Dict] = []
    seen_errors = set()

    lines = analysis_output.split("\n")

    for i, line in enumerate(lines):
        # Check for invalid column name errors
        col_match = _INVALID_COL_RE.search(line)
        if col_match:
            bad_column = col_match.group(1)

            # Look backwards to find the originating SELECT query
            original_query = ""
            view_name = ""
            for j in range(max(0, i - 10), i):
                q_match = _QUERY_RE.search(lines[j])
                if q_match:
                    original_query = q_match.group(1)
                    view_name = _extract_view_from_query(original_query)
                    break

            error_key = f"{view_name}:{bad_column}"
            if error_key not in seen_errors:
                seen_errors.add(error_key)
                errors.append(
                    {
                        "type": "invalid_column",
                        "bad_column": bad_column,
                        "view_name": view_name,
                        "original_query": original_query,
                        "error_message": line.strip(),
                        "line_number": i + 1,
                    }
                )

    # Check for dispatch bug (line 204: all: command not found)
    dispatch_bug = False
    for line in lines:
        if "command not found" in line and "all" in line:
            dispatch_bug = True
            errors.append(
                {
                    "type": "dispatch_bug",
                    "bad_column": "",
                    "view_name": "",
                    "original_query": "",
                    "error_message": line.strip(),
                    "line_number": 0,
                    "fix": "Change case pattern: 'all)' should call 'run_all' not '$FUNC'",
                }
            )
            break

    return {
        "status": "success",
        "error_count": len(errors),
        "errors": errors,
        "has_dispatch_bug": dispatch_bug,
        "summary": (
            f"Found {len(errors)} error(s): "
            f"{len([e for e in errors if e['type'] == 'invalid_column'])} invalid column(s), "
            f"{'1 dispatch bug' if dispatch_bug else '0 dispatch bugs'}"
        ),
    }


def discover_hana_schema(view_names: str) -> dict:
    """Query the HANA system catalog to discover available columns for views.
    Uses docker exec → hdbsql to query SYS.TABLE_COLUMNS inside the container.

    This is the key 'learning' step: the agent discovers what the actual HANA
    schema looks like before trying to fix queries.

    Args:
        view_names (str): Comma-separated list of view/table names to discover
            (e.g., "M_DATABASE,M_BACKUP_CATALOG,M_TRANSACTIONS").

    Returns:
        dict: For each view, the list of available column names and their
            schema/table info. Returns error details if discovery fails.
    """
    views = [v.strip().upper() for v in view_names.split(",") if v.strip()]
    schema_info: Dict[str, Dict] = {}

    for view in views:
        schema_table = _VIEW_SCHEMA_MAP.get(view)
        if not schema_table:
            schema_info[view] = {
                "status": "unknown_view",
                "error": f"View '{view}' not in known schema map. Add it to _VIEW_SCHEMA_MAP.",
                "columns": [],
            }
            continue

        schema_name, table_name = schema_table

        # Query the system catalog for columns
        query = (
            f"SELECT COLUMN_NAME FROM SYS.TABLE_COLUMNS "
            f"WHERE SCHEMA_NAME=''{schema_name}'' AND TABLE_NAME=''{table_name}'' "
            f"ORDER BY POSITION"
        )
        result = _hdbsql_via_docker(query)

        if result.get("status") == "success":
            stdout = result.get("stdout", "")
            # Parse column names from hdbsql tabular output
            columns = []
            for line in stdout.split("\n"):
                line = line.strip()
                # Skip header lines (|------|), empty lines, and the header row
                if not line or line.startswith("|") and "---" in line:
                    continue
                if line.startswith("| COLUMN_NAME"):
                    continue
                # Extract column name from | value | format
                if line.startswith("|"):
                    parts = [p.strip() for p in line.split("|") if p.strip()]
                    if parts:
                        columns.append(parts[0])
                elif line and not line.startswith("*"):
                    # Plain text output (no table formatting)
                    columns.append(line.strip('" '))

            schema_info[view] = {
                "status": "discovered",
                "schema": schema_name,
                "table": table_name,
                "column_count": len(columns),
                "columns": columns,
            }
            logger.info(
                "Discovered %d columns for %s.%s",
                len(columns),
                schema_name,
                table_name,
            )
        else:
            schema_info[view] = {
                "status": "error",
                "error": result.get("error_message", result.get("stderr", "unknown")),
                "columns": [],
            }
            logger.warning("Failed to discover schema for %s: %s", view, result)

    return {
        "status": "success",
        "views_queried": len(views),
        "schema": schema_info,
    }


def fix_analysis_script(errors_json: str, schema_json: str) -> dict:
    """Fix the analysis.sh script on the VM based on detected errors and
    discovered schema. Generates sed commands to replace invalid column
    references with correct ones and applies them via remote exec.

    The tool backs up the original script before making changes.

    Args:
        errors_json (str): JSON string of the errors list from parse_analysis_errors
            (the 'errors' field). Each error should have 'type', 'bad_column',
            'view_name', and 'original_query'.
        schema_json (str): JSON string of the schema dict from discover_hana_schema
            (the 'schema' field). Each view should have 'columns' list.

    Returns:
        dict: status, list of fixes applied, and any remaining unfixed errors.
    """
    import json
    from .hana_tools import execute_remote_command

    try:
        errors = (
            json.loads(errors_json) if isinstance(errors_json, str) else errors_json
        )
        schema = (
            json.loads(schema_json) if isinstance(schema_json, str) else schema_json
        )
    except json.JSONDecodeError as exc:
        return {
            "status": "error",
            "error_message": f"Invalid JSON input: {exc}",
        }

    fixes_applied: List[Dict] = []
    unfixed: List[Dict] = []
    sed_commands: List[str] = []

    # Step 1: Backup the original script
    backup_cmd = f"cp {_SCRIPT_PATH} {_SCRIPT_PATH}.bak"
    backup_result = execute_remote_command(backup_cmd, admin_override=True)
    if backup_result.get("status") != "success":
        logger.warning("Could not backup script: %s", backup_result)

    # Step 2: Fix the dispatch bug
    for error in errors:
        if error.get("type") == "dispatch_bug":
            # Fix: change `$FUNC` on the all) dispatch line to `run_all`
            sed_commands.append(
                f"sed -i 's/^  all).*$/  all) run_all ;;/' {_SCRIPT_PATH}"
            )
            fixes_applied.append(
                {
                    "type": "dispatch_bug",
                    "description": "Fixed 'all' case dispatch to call run_all instead of $FUNC",
                }
            )

    # Step 3: Fix invalid column errors
    for error in errors:
        if error.get("type") != "invalid_column":
            continue

        bad_col = error.get("bad_column", "")
        view_name = error.get("view_name", "")
        original_query = error.get("original_query", "")

        if not bad_col or not view_name or not original_query:
            unfixed.append(
                {**error, "reason": "Missing bad_column, view_name, or original_query"}
            )
            continue

        # Get the discovered columns for this view
        view_schema = schema.get(view_name, {})
        available_cols = view_schema.get("columns", [])

        if not available_cols:
            unfixed.append({**error, "reason": f"No schema discovered for {view_name}"})
            continue

        # Strategy: Remove the bad column from the SELECT query
        # Build a new query without the invalid column
        fixed_query = _remove_column_from_select(original_query, bad_col)

        if fixed_query and fixed_query != original_query:
            # Escape special characters for sed
            escaped_old = original_query.replace("/", "\\/").replace("'", "'\\''")
            escaped_new = fixed_query.replace("/", "\\/").replace("'", "'\\''")
            sed_commands.append(
                f'sed -i "s|{_escape_sed(original_query)}|{_escape_sed(fixed_query)}|" {_SCRIPT_PATH}'
            )
            fixes_applied.append(
                {
                    "type": "invalid_column",
                    "view": view_name,
                    "removed_column": bad_col,
                    "description": f"Removed invalid column '{bad_col}' from {view_name} query",
                    "original_query": original_query[:120],
                    "fixed_query": fixed_query[:120],
                }
            )
        else:
            unfixed.append({**error, "reason": "Could not auto-fix query"})

    # Step 4: Apply all fixes via remote exec
    applied_count = 0
    for cmd in sed_commands:
        result = execute_remote_command(cmd, admin_override=True)
        if result.get("status") == "success":
            applied_count += 1
        else:
            logger.warning("sed command failed: %s → %s", cmd, result)

    return {
        "status": "success" if applied_count > 0 else "no_fixes",
        "fixes_applied": fixes_applied,
        "applied_count": applied_count,
        "total_sed_commands": len(sed_commands),
        "unfixed_errors": unfixed,
        "backup_path": f"{_SCRIPT_PATH}.bak",
        "message": f"Applied {applied_count}/{len(sed_commands)} fixes to {_SCRIPT_PATH}",
    }


def _escape_sed(text: str) -> str:
    """Escape special characters for use in sed replacement strings."""
    # Escape sed special chars: & \ /
    text = text.replace("\\", "\\\\")
    text = text.replace("|", "\\|")
    text = text.replace("&", "\\&")
    return text


def _remove_column_from_select(query: str, bad_column: str) -> str:
    """Remove a specific column reference from a SELECT query.

    Handles patterns like:
    - 'BAD_COL, NEXT_COL' → 'NEXT_COL'
    - 'PREV_COL, BAD_COL' → 'PREV_COL'
    - 'PREV_COL, BAD_COL, NEXT_COL' → 'PREV_COL, NEXT_COL'
    - 'ROUND(BAD_COL / ..., 2) AS ALIAS' → removed entirely
    """
    # Pattern 1: Column with expression (e.g., ROUND(BACKUP_SIZE / 1024, 2) AS SIZE_MB)
    expr_pattern = re.compile(
        r",?\s*ROUND\s*\([^)]*\b"
        + re.escape(bad_column)
        + r"\b[^)]*\)\s+AS\s+\w+\s*,?",
        re.IGNORECASE,
    )
    result = expr_pattern.sub("", query)
    if result != query:
        # Clean up any double commas or trailing/leading commas
        result = re.sub(r",\s*,", ",", result)
        result = re.sub(r"SELECT\s+,", "SELECT ", result)
        result = re.sub(r",\s+FROM", " FROM", result)
        return result.strip()

    # Pattern 2: Simple column reference (e.g., 'ACTIVE_STATUS' or 'IDLE_TIME')
    # Match optional preceding comma or trailing comma
    simple_pattern = re.compile(
        r",\s*\b"
        + re.escape(bad_column)
        + r"\b\s*(?=,|\s+FROM|\s+WHERE|\s+ORDER|\s+LIMIT|$)"
        r"|"
        r"\b" + re.escape(bad_column) + r"\b\s*,\s*",
        re.IGNORECASE,
    )
    result = simple_pattern.sub("", query)
    if result != query:
        result = re.sub(r",\s*,", ",", result)
        result = re.sub(r"SELECT\s+,", "SELECT ", result)
        result = re.sub(r",\s+FROM", " FROM", result)
        return result.strip()

    # Pattern 3: Column with alias (e.g., 'STATEMENT_STRING')
    alias_pattern = re.compile(
        r",?\s*(?:SUBSTR\s*\([^)]*\b"
        + re.escape(bad_column)
        + r"\b[^)]*\)\s+AS\s+\w+)\s*,?",
        re.IGNORECASE,
    )
    result = alias_pattern.sub("", query)
    if result != query:
        result = re.sub(r",\s*,", ",", result)
        result = re.sub(r"SELECT\s+,", "SELECT ", result)
        result = re.sub(r",\s+FROM", " FROM", result)
        return result.strip()

    # Pattern 4: In WHERE clause (e.g., IDLE_TIME > 600)
    where_pattern = re.compile(
        r"\s+AND\s+\b" + re.escape(bad_column) + r"\b\s*[><=!]+\s*\d+",
        re.IGNORECASE,
    )
    result = where_pattern.sub("", query)
    if result != query:
        return result.strip()

    # Pattern 5: In ORDER BY (e.g., ORDER BY IDLE_TIME DESC)
    order_pattern = re.compile(
        r"\b" + re.escape(bad_column) + r"\b\s+(?:ASC|DESC)\s*,?\s*",
        re.IGNORECASE,
    )
    result = order_pattern.sub("", query)
    if result != query:
        result = re.sub(r"ORDER BY\s*$", "", result)
        result = re.sub(r"ORDER BY\s+LIMIT", "LIMIT", result)
        return result.strip()

    return query


def run_and_learn_analysis(sid: str = "", function: str = "all") -> dict:
    """Full self-learning loop: run analysis → detect errors → discover schema
    → fix script → re-run. Records learned fixes in the LearningCommandStore.

    This is the main orchestration tool that ties everything together.

    Args:
        sid (str): SAP HANA System ID (default: HXE).
        function (str): Analysis function to run (default: all).

    Returns:
        dict: Complete results including initial errors, fixes applied,
            final run status, and learning store updates.
    """
    import json

    sid = sid or _DEFAULT_SID
    results = {
        "sid": sid,
        "function": function,
        "phases": {},
    }

    # ── Phase 1: Run the analysis script ──
    logger.info("Phase 1: Running analysis script...")
    run_result = run_analysis_script(sid, function)
    results["phases"]["initial_run"] = {
        "status": run_result.get("status"),
        "output_length": len(run_result.get("output", "")),
    }

    if run_result.get("status") != "success":
        results["status"] = "error"
        results["error_message"] = (
            f"Initial run failed: {run_result.get('error_message', 'unknown')}"
        )
        return results

    output = run_result.get("output", "")

    # ── Phase 2: Parse for errors ──
    logger.info("Phase 2: Parsing errors...")
    parse_result = parse_analysis_errors(output)
    results["phases"]["error_detection"] = parse_result

    if parse_result.get("error_count", 0) == 0:
        results["status"] = "success"
        results["message"] = "No errors detected — analysis script ran cleanly!"
        results["output"] = output
        return results

    # ── Phase 3: Discover correct schema ──
    logger.info("Phase 3: Discovering HANA schema...")
    failing_views = list(
        set(
            e["view_name"] for e in parse_result.get("errors", []) if e.get("view_name")
        )
    )
    if failing_views:
        schema_result = discover_hana_schema(",".join(failing_views))
        results["phases"]["schema_discovery"] = schema_result
    else:
        schema_result = {"schema": {}}
        results["phases"]["schema_discovery"] = {
            "status": "skipped",
            "reason": "No failing views identified",
        }

    # ── Phase 4: Fix the script ──
    logger.info("Phase 4: Fixing analysis script...")
    errors_json = json.dumps(parse_result.get("errors", []))
    schema_json = json.dumps(schema_result.get("schema", {}))
    fix_result = fix_analysis_script(errors_json, schema_json)
    results["phases"]["fix"] = fix_result

    # ── Phase 5: Re-run the fixed script ──
    logger.info("Phase 5: Re-running fixed analysis script...")
    rerun_result = run_analysis_script(sid, function)
    results["phases"]["rerun"] = {
        "status": rerun_result.get("status"),
        "output_length": len(rerun_result.get("output", "")),
    }

    if rerun_result.get("status") == "success":
        # Parse again to check if errors are resolved
        reparse = parse_analysis_errors(rerun_result.get("output", ""))
        results["phases"]["rerun_errors"] = reparse
        results["output"] = rerun_result.get("output", "")

        if reparse.get("error_count", 0) == 0:
            results["status"] = "success"
            results["message"] = "All errors fixed! Analysis script runs cleanly now."
        else:
            results["status"] = "partial"
            results["message"] = (
                f"Fixed some errors but {reparse['error_count']} remain. "
                "May need additional iteration."
            )
    else:
        results["status"] = "error"
        results["message"] = (
            f"Re-run failed: {rerun_result.get('error_message', 'unknown')}"
        )

    # ── Phase 6: Record learned fixes ──
    if fix_result.get("fixes_applied"):
        try:
            from .learning_store import learn_new_commands

            diagnostic_cmds = [
                f"# Schema discovery: docker exec hdbsql 'SELECT COLUMN_NAME FROM SYS.TABLE_COLUMNS WHERE TABLE_NAME={v}'"
                for v in failing_views
            ]
            remediation_cmds = [
                f"# Fix: {f['description']}"
                for f in fix_result.get("fixes_applied", [])
            ]

            learn_result = learn_new_commands(
                incident_summary=f"analysis.sh SQL errors: {', '.join(failing_views)}",
                diagnostic_commands="\n".join(diagnostic_cmds),
                remediation_commands="\n".join(remediation_cmds),
                category="analysis",
                severity="warning",
            )
            results["phases"]["learning"] = learn_result
        except Exception as exc:
            logger.warning("Failed to record learned commands: %s", exc)
            results["phases"]["learning"] = {"status": "error", "error": str(exc)}

    return results
