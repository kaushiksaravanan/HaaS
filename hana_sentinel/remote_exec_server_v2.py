"""
Remote Command Execution Server - COMPREHENSIVE VERSION
=====================================================================

A lightweight FastAPI server with built-in diagnostics and healing.
All logic is in Python - no external scripts needed.

Security Features:
- API Key authentication
- Command allowlist (only safe commands)
- Request logging

Usage:
    python3 remote_exec_server.py
"""

import os
import signal
import subprocess
import logging
import json
import shlex
import re
import glob
import asyncio
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from typing import Optional, List, Dict, Any
from fastapi import FastAPI, HTTPException, Header, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel
import uvicorn

# Thread pool for running blocking I/O without freezing the async event loop
# Use more workers so a few stuck threads don't block the entire server
_executor = ThreadPoolExecutor(max_workers=32)

# Track active threads for health monitoring
_active_threads: Dict[int, Dict[str, Any]] = {}
_thread_lock = threading.Lock()

def _track_thread_start(description: str):
    """Register a thread as active for health monitoring."""
    tid = threading.current_thread().ident
    with _thread_lock:
        _active_threads[tid] = {
            "description": description,
            "started_at": datetime.now().isoformat(),
            "started_ts": datetime.now().timestamp(),
        }

def _track_thread_end():
    """Unregister a thread when it completes."""
    tid = threading.current_thread().ident
    with _thread_lock:
        _active_threads.pop(tid, None)


async def _to_thread(func, *args, _timeout: int = 120, _description: str = "", **kwargs):
    """Run a blocking function in the thread pool with an async timeout.

    If the thread doesn't finish in _timeout seconds, the await is cancelled
    and an error is returned so the endpoint doesn't hang forever.
    """
    loop = asyncio.get_event_loop()

    def _wrapper():
        _track_thread_start(_description or func.__name__)
        try:
            return func(*args, **kwargs)
        finally:
            _track_thread_end()

    try:
        return await asyncio.wait_for(
            loop.run_in_executor(_executor, _wrapper),
            timeout=_timeout,
        )
    except asyncio.TimeoutError:
        logger.error(f"Thread timed out after {_timeout}s: {_description or func.__name__}")
        raise HTTPException(
            status_code=504,
            detail=f"Operation timed out after {_timeout}s"
        )

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('remote_exec_server.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# ============================================================================
# Configuration
# ============================================================================

class Config:
    """Server configuration"""

    # API Key for authentication (pre-configured secure base64 key)
    API_KEY = os.getenv("REMOTE_EXEC_API_KEY", "REMOTE_EXEC_KEY_REVOKED_PLACEHOLDER_0000000000000000")

    # Server settings
    HOST = os.getenv("REMOTE_EXEC_HOST", "0.0.0.0")
    PORT = int(os.getenv("REMOTE_EXEC_PORT", "9999"))

    # Security settings
    MAX_COMMAND_LENGTH = 5000
    COMMAND_TIMEOUT = 300  # 5 minutes max

    # HANA Configuration
    HANA_SID = os.getenv("HANA_SID", "ZO3")
    HANA_INSTANCE_NR = os.getenv("HANA_INSTANCE_NR", "02")
    HANA_USER = os.getenv("HANA_USER", "zo3adm")

    # Commands that must run as HANA admin user (binaries only in HANA user's PATH)
    HANA_USER_COMMANDS = ["sapcontrol", "HDB", "hdbsql", "hdbuserstore"]

    # Allowed command prefixes (security: only allow specific commands)
    ALLOWED_COMMANDS = [
        "echo",
        "whoami",
        "pwd",
        "date",
        "hostname",
        "df",
        "free",
        "uptime",
        "cat /proc/",
        "cat /usr/sap/",
        "cat /hana/",
        "cat /hdb/",
        "cat /var/log/",
        "ls -l",
        "ls -la",
        "ls /",
        "tail ",
        "head ",
        "wc ",
        "grep ",
        "sapcontrol",
        "HDB",
        "hdbsql",
        "hdbuserstore",
        "du -sh",
        "ps aux",
        "id",
        "mount",
        "lsblk",
        "find /usr/sap",
        "find /hana",
    ]

# ============================================================================
# FastAPI Application
# ============================================================================

app = FastAPI(
    title="Remote Command Execution Server with Diagnostics & Healing",
    description="Comprehensive server with built-in HANA diagnostics and healing",
    version="2.0.0"
)

# ============================================================================
# Models
# ============================================================================

class CommandRequest(BaseModel):
    """Request model for command execution"""
    command: str
    timeout: Optional[int] = 60
    working_dir: Optional[str] = None
    admin_override: Optional[bool] = False

class CommandResponse(BaseModel):
    """Response model for command execution"""
    status: str
    exit_code: int
    stdout: str
    stderr: str
    execution_time: float
    timestamp: str

# ============================================================================
# Diagnostic Functions (Pure Python)
# ============================================================================

def _run_subprocess_safe(args, timeout: int = 30, shell: bool = False, cwd: str = None) -> Dict[str, Any]:
    """
    Run a subprocess with RELIABLE timeout enforcement.

    Uses start_new_session=True + os.killpg to kill the entire process group
    (including child processes spawned by sudo/bash). This prevents zombie
    processes from permanently consuming thread pool workers.
    """
    try:
        proc = subprocess.Popen(
            args,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=True,
            shell=shell,
            cwd=cwd,
            start_new_session=True,  # Create new process group for reliable killing
        )
        try:
            stdout, stderr = proc.communicate(timeout=timeout)
            return {
                "status": "success" if proc.returncode == 0 else "error",
                "exit_code": proc.returncode,
                "output": stdout.strip() if stdout else "",
                "error": stderr.strip() if stderr else None,
            }
        except subprocess.TimeoutExpired:
            # Kill the ENTIRE process group (sudo + all children)
            try:
                os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
            except (OSError, ProcessLookupError):
                proc.kill()  # Fallback: kill just the direct process
            proc.wait(timeout=5)  # Reap the zombie
            logger.warning(f"Killed timed-out process group (pgid={proc.pid}) after {timeout}s")
            return {"status": "error", "error": f"Command timeout after {timeout}s (process killed)"}
    except Exception as e:
        return {"status": "error", "error": str(e)}


def run_as_hana_user(command: List[str], timeout: int = 30) -> Dict[str, Any]:
    """
    Execute command as HANA admin user (zo3adm).

    Uses process-group killing to ensure timeouts reliably terminate
    sudo + all child processes.
    """
    full_command = ["sudo", "-i", "-u", Config.HANA_USER] + command
    return _run_subprocess_safe(full_command, timeout=timeout)


def run_shell_as_hana_user(command: str, timeout: int = 30) -> Dict[str, Any]:
    """
    Execute shell command as HANA admin user (zo3adm).
    """
    full_command = f"sudo -i -u {shlex.quote(Config.HANA_USER)} bash -c {shlex.quote(command)}"
    return _run_subprocess_safe(full_command, timeout=timeout, shell=True)


def check_hana_processes() -> Dict[str, Any]:
    """Check HANA process status via sapcontrol (as zo3adm)"""
    return run_as_hana_user(
        ["sapcontrol", "-nr", Config.HANA_INSTANCE_NR, "-function", "GetProcessList"],
        timeout=30
    )

def check_disk_usage() -> Dict[str, Any]:
    """Check disk usage for HANA partitions"""
    try:
        result = subprocess.run(
            ["df", "-h"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=True,
            timeout=10
        )

        lines = result.stdout.strip().split("\n")
        # Filter for HANA-related mounts
        hana_mounts = [line for line in lines if any(keyword in line.lower() for keyword in ['hana', 'hdb', Config.HANA_SID.lower(), 'filesystem'])]

        return {
            "status": "success",
            "output": "\n".join(hana_mounts)
        }
    except Exception as e:
        return {"status": "error", "error": str(e)}

def check_memory() -> Dict[str, Any]:
    """Check system memory usage"""
    try:
        result = subprocess.run(
            ["free", "-h"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=True,
            timeout=10
        )
        return {
            "status": "success",
            "output": result.stdout.strip()
        }
    except Exception as e:
        return {"status": "error", "error": str(e)}

def check_userstore() -> Dict[str, Any]:
    """Check HANA userstore keys (as zo3adm)"""
    return run_as_hana_user(["hdbuserstore", "list"], timeout=15)

def check_system_parameters() -> Dict[str, Any]:
    """Check critical system parameters"""
    params = {}

    try:
        # Swappiness
        with open("/proc/sys/vm/swappiness", "r") as f:
            swappiness = f.read().strip()
            params["swappiness"] = {
                "value": swappiness,
                "expected": "10",
                "status": "ok" if swappiness == "10" else "warning"
            }
    except Exception as e:
        params["swappiness"] = {"status": "error", "error": str(e)}

    try:
        # Transparent Huge Pages
        with open("/sys/kernel/mm/transparent_hugepage/enabled", "r") as f:
            thp = f.read().strip()
            params["transparent_hugepages"] = {
                "value": thp,
                "expected": "[never]",
                "status": "ok" if "[never]" in thp else "warning"
            }
    except Exception as e:
        params["transparent_hugepages"] = {"status": "error", "error": str(e)}

    try:
        # ASLR
        with open("/proc/sys/kernel/randomize_va_space", "r") as f:
            aslr = f.read().strip()
            params["aslr"] = {
                "value": aslr,
                "expected": "0",
                "status": "ok" if aslr == "0" else "warning"
            }
    except Exception as e:
        params["aslr"] = {"status": "error", "error": str(e)}

    return {"status": "success", "parameters": params}

def check_backups() -> Dict[str, Any]:
    """Check backup status"""
    backup_base = f"/hdb/{Config.HANA_SID}/backup"

    info = {}

    # Check data backup directory
    data_dir = f"{backup_base}/data"
    if os.path.exists(data_dir):
        try:
            files = os.listdir(data_dir)
            info["data_backup"] = {
                "exists": True,
                "file_count": len(files),
                "path": data_dir
            }
        except Exception as e:
            info["data_backup"] = {"exists": True, "error": str(e)}
    else:
        info["data_backup"] = {"exists": False, "path": data_dir}

    # Check log backup directory
    log_dir = f"{backup_base}/log"
    if os.path.exists(log_dir):
        try:
            files = os.listdir(log_dir)
            info["log_backup"] = {
                "exists": True,
                "file_count": len(files),
                "path": log_dir
            }
        except Exception as e:
            info["log_backup"] = {"exists": True, "error": str(e)}
    else:
        info["log_backup"] = {"exists": False, "path": log_dir}

    return {"status": "success", "backups": info}

# ============================================================================
# Healing Functions (Pure Python)
# ============================================================================

def heal_system_parameters(dry_run: bool = True) -> Dict[str, Any]:
    """Fix system parameters (swappiness, THP, ASLR)"""
    actions = []
    errors = []

    # Check current parameters
    current_params = check_system_parameters()["parameters"]

    # Fix swappiness
    if current_params.get("swappiness", {}).get("status") == "warning":
        if not dry_run:
            try:
                subprocess.run(
                    ["sysctl", "-w", "vm.swappiness=10"],
                    check=True,
                    capture_output=True
                )
                actions.append("Set swappiness to 10")
            except Exception as e:
                errors.append(f"Failed to set swappiness: {e}")
        else:
            actions.append("[DRY RUN] Would set swappiness to 10")

    # Fix THP
    if current_params.get("transparent_hugepages", {}).get("status") == "warning":
        if not dry_run:
            try:
                with open("/sys/kernel/mm/transparent_hugepage/enabled", "w") as f:
                    f.write("never")
                actions.append("Disabled transparent huge pages")
            except Exception as e:
                errors.append(f"Failed to disable THP: {e}")
        else:
            actions.append("[DRY RUN] Would disable transparent huge pages")

    # Fix ASLR
    if current_params.get("aslr", {}).get("status") == "warning":
        if not dry_run:
            try:
                subprocess.run(
                    ["sysctl", "-w", "kernel.randomize_va_space=0"],
                    check=True,
                    capture_output=True
                )
                actions.append("Disabled ASLR")
            except Exception as e:
                errors.append(f"Failed to disable ASLR: {e}")
        else:
            actions.append("[DRY RUN] Would disable ASLR")

    return {
        "status": "success" if not errors else "partial",
        "actions": actions,
        "errors": errors if errors else None
    }

def heal_trace_cleanup(dry_run: bool = True) -> Dict[str, Any]:
    """Clean up old trace files"""
    trace_pattern = f"/usr/sap/{Config.HANA_SID}/HDB{Config.HANA_INSTANCE_NR}/*/trace"
    actions = []

    try:
        # Expand glob pattern to actual directories (subprocess won't expand *)
        trace_dirs = glob.glob(trace_pattern)
        old_files = []
        for trace_d in trace_dirs:
            result = subprocess.run(
                ["find", trace_d, "-name", "*.trc", "-mtime", "+7"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                universal_newlines=True,
                timeout=30
            )
            if result.stdout and result.stdout.strip():
                old_files.extend(result.stdout.strip().split("\n"))

        if old_files:
            if not dry_run:
                for file in old_files:
                    try:
                        os.remove(file)
                        actions.append(f"Deleted {file}")
                    except Exception as e:
                        actions.append(f"Failed to delete {file}: {e}")
            else:
                actions.append(f"[DRY RUN] Would delete {len(old_files)} old trace files")

        return {
            "status": "success",
            "actions": actions,
            "files_found": len(old_files)
        }
    except Exception as e:
        return {"status": "error", "error": str(e)}

# ============================================================================
# HANA SQL Query Helper (via hdbsql)
# ============================================================================

def run_hdbsql(sql: str, timeout: int = 30) -> Dict[str, Any]:
    """
    Execute SQL query against HANA via hdbsql using userstore key SYSTEM.

    Runs as HANA admin user so hdbsql is in PATH and env is loaded.
    Returns parsed rows as list of dicts.

    Args:
        sql: SQL query string
        timeout: Command timeout in seconds

    Returns:
        dict with status, columns, rows, row_count
    """
    # Use hdbsql with userstore key, comma-separated output for parsing
    # No -a flag (it suppresses column headers which the parser needs)
    # -C: suppress page separator
    # Escape shell-sensitive characters in SQL to prevent injection
    safe_sql = sql.replace('\\', '\\\\').replace('"', '\\"').replace('`', '\\`').replace('$', '\\$')
    hdbsql_cmd = (
        f'hdbsql -U SYSTEM "{safe_sql}"'
    )

    result = run_shell_as_hana_user(hdbsql_cmd, timeout=timeout)

    if result.get("status") != "success" or not result.get("output"):
        # Try with SYSTEMDB userstore key as fallback (connects to port 30213)
        hdbsql_cmd_fallback = (
            f'hdbsql -U SYSTEMDB "{safe_sql}"'
        )
        result = run_shell_as_hana_user(hdbsql_cmd_fallback, timeout=timeout)

        if result.get("status") != "success":
            return {
                "status": "error",
                "error": result.get("error", "hdbsql query failed"),
                "output": result.get("output", "")
            }

    output = result.get("output", "").strip()
    if not output:
        return {"status": "success", "columns": [], "rows": [], "row_count": 0}

    # Parse comma-separated output (hdbsql default format)
    # Format: "COL1,COL2\nval1,val2\nN rows selected (overall time ...)"
    lines = output.split("\n")
    rows = []
    columns = []
    header_found = False

    for line in lines:
        line = line.strip()
        if not line:
            continue

        # Skip footer lines like "N rows selected (overall time ...)"
        if "row selected" in line.lower() or "rows selected" in line.lower():
            continue

        # Split by comma separator
        parts = [p.strip() for p in line.split(",")]

        if not header_found:
            # First non-empty, non-footer line is column headers
            columns = [p.upper() for p in parts if p]
            header_found = True
        else:
            if columns and len(parts) >= len(columns):
                row = {}
                for j, col in enumerate(columns):
                    val = parts[j] if j < len(parts) else ""
                    # Try to convert numeric values
                    try:
                        if "." in val:
                            row[col] = float(val)
                        else:
                            row[col] = int(val)
                    except (ValueError, TypeError):
                        row[col] = val
                rows.append(row)

    return {
        "status": "success",
        "columns": columns,
        "rows": rows,
        "row_count": len(rows)
    }


# ============================================================================
# HANA Monitoring Functions (via hdbsql)
# ============================================================================

def get_hana_realtime_metrics() -> Dict[str, Any]:
    """Get real-time HANA metrics: CPU, memory, connections, TPS, etc."""
    metrics = {
        "cpu_usage": None,
        "memory_usage": None,
        "active_connections": None,
        "active_transactions": None,
        "transactions_per_sec": None,
        "blocking_sessions": None,
        "cache_hit_ratio": None,
        "active_threads": None,
    }

    # CPU from latest statistics delta, memory from current utilization
    try:
        result = run_hdbsql(
            "SELECT TOP 1 "
            "ROUND(100.0 * (TOTAL_CPU_USER_TIME_DELTA + TOTAL_CPU_SYSTEM_TIME_DELTA) "
            "/ NULLIF(TOTAL_CPU_USER_TIME_DELTA + TOTAL_CPU_SYSTEM_TIME_DELTA "
            "+ TOTAL_CPU_WIO_TIME_DELTA + TOTAL_CPU_IDLE_TIME_DELTA, 0), 1) AS CPU_USAGE, "
            "ROUND(USED_PHYSICAL_MEMORY * 100.0 "
            "/ NULLIF(USED_PHYSICAL_MEMORY + FREE_PHYSICAL_MEMORY, 0), 1) AS MEMORY_USAGE "
            "FROM _SYS_STATISTICS.HOST_RESOURCE_UTILIZATION_STATISTICS "
            "ORDER BY SERVER_TIMESTAMP DESC"
        )
        if result.get("rows"):
            metrics["cpu_usage"] = result["rows"][0].get("CPU_USAGE")
            metrics["memory_usage"] = result["rows"][0].get("MEMORY_USAGE")
    except Exception:
        pass

    # Active connections
    try:
        result = run_hdbsql(
            "SELECT COUNT(*) AS CNT FROM M_CONNECTIONS WHERE CONNECTION_STATUS = 'RUNNING'"
        )
        if result.get("rows"):
            metrics["active_connections"] = result["rows"][0].get("CNT")
    except Exception:
        pass

    # Active transactions
    try:
        result = run_hdbsql(
            "SELECT COUNT(*) AS CNT FROM M_TRANSACTIONS WHERE TRANSACTION_STATUS = 'ACTIVE'"
        )
        if result.get("rows"):
            metrics["active_transactions"] = result["rows"][0].get("CNT")
    except Exception:
        pass

    # TPS from M_WORKLOAD (current rate)
    try:
        result = run_hdbsql(
            "SELECT ROUND(SUM(CURRENT_TRANSACTION_RATE), 0) AS TPS "
            "FROM M_WORKLOAD"
        )
        if result.get("rows"):
            metrics["transactions_per_sec"] = result["rows"][0].get("TPS")
    except Exception:
        pass

    # Blocking sessions
    try:
        result = run_hdbsql(
            "SELECT COUNT(*) AS CNT FROM M_BLOCKED_TRANSACTIONS"
        )
        if result.get("rows"):
            metrics["blocking_sessions"] = result["rows"][0].get("CNT")
    except Exception:
        pass

    # Cache hit ratio from SQL plan cache
    try:
        result = run_hdbsql(
            "SELECT ROUND(SUM(TO_BIGINT(EXECUTION_COUNT) - TO_BIGINT(PREPARATION_COUNT)) * 100.0 "
            "/ NULLIF(SUM(TO_BIGINT(EXECUTION_COUNT)), 0), 1) AS RATIO "
            "FROM M_SQL_PLAN_CACHE"
        )
        if result.get("rows"):
            metrics["cache_hit_ratio"] = result["rows"][0].get("RATIO")
    except Exception:
        pass

    # Active threads
    try:
        result = run_hdbsql(
            "SELECT COUNT(*) AS CNT FROM M_SERVICE_THREADS WHERE IS_ACTIVE = 'TRUE'"
        )
        if result.get("rows"):
            metrics["active_threads"] = result["rows"][0].get("CNT")
    except Exception:
        pass

    return metrics


def get_hana_services() -> List[Dict[str, Any]]:
    """Get HANA service status from M_SERVICES."""
    result = run_hdbsql(
        "SELECT SERVICE_NAME, ACTIVE_STATUS, PORT, "
        "ROUND(TOTAL_MEMORY_USED_SIZE / 1024 / 1024 / 1024, 2) AS MEMORY_GB, "
        "COORDINATOR_TYPE "
        "FROM M_SERVICES ORDER BY SERVICE_NAME"
    )
    if result.get("status") == "success":
        services = []
        for row in result.get("rows", []):
            services.append({
                "name": row.get("SERVICE_NAME", ""),
                "status": "running" if row.get("ACTIVE_STATUS") == "YES" else "stopped",
                "port": row.get("PORT", 0),
                "memory_gb": row.get("MEMORY_GB", 0),
                "coordinator": row.get("COORDINATOR_TYPE", ""),
            })
        return services
    return []


def get_active_transactions() -> List[Dict[str, Any]]:
    """Get active transactions with their SQL statements."""
    result = run_hdbsql(
        "SELECT t.TRANSACTION_ID, t.TRANSACTION_TYPE, t.TRANSACTION_STATUS, "
        "SECONDS_BETWEEN(t.START_TIME, CURRENT_TIMESTAMP) AS DURATION_SEC, "
        "t.START_TIME, c.CONNECTION_ID, c.CLIENT_IP, c.CLIENT_PID, "
        "SUBSTR(s.STATEMENT_STRING, 1, 200) AS SQL_TEXT, "
        "ROUND(s.DURATION_MICROSEC / 1000000.0, 2) AS STMT_DURATION_SEC "
        "FROM M_TRANSACTIONS t "
        "LEFT JOIN M_CONNECTIONS c ON t.CONNECTION_ID = c.CONNECTION_ID "
        "LEFT JOIN M_ACTIVE_STATEMENTS s ON t.CONNECTION_ID = s.CONNECTION_ID "
        "WHERE t.TRANSACTION_STATUS = 'ACTIVE' "
        "ORDER BY t.START_TIME ASC"
    )
    if result.get("status") == "success":
        transactions = []
        for row in result.get("rows", []):
            transactions.append({
                "transaction_id": row.get("TRANSACTION_ID"),
                "type": row.get("TRANSACTION_TYPE", ""),
                "status": row.get("TRANSACTION_STATUS", ""),
                "duration_sec": row.get("DURATION_SEC", 0),
                "start_time": str(row.get("START_TIME", "")),
                "connection_id": row.get("CONNECTION_ID"),
                "client_ip": row.get("CLIENT_IP", ""),
                "sql": row.get("SQL_TEXT", ""),
                "stmt_duration_sec": row.get("STMT_DURATION_SEC", 0),
            })
        return transactions
    return []


def get_expensive_queries(top_n: int = 10) -> List[Dict[str, Any]]:
    """Get top expensive queries from M_EXPENSIVE_STATEMENTS."""
    result = run_hdbsql(
        f"SELECT TOP {top_n} "
        "SUBSTR(STATEMENT_STRING, 1, 200) AS SQL_TEXT, "
        "ROUND(DURATION_MICROSEC / 1000000.0, 2) AS DURATION_SEC, "
        "ROUND(CPU_TIME / 1000000.0, 2) AS CPU_SEC, "
        "ROUND(LOCK_WAIT_DURATION / 1000000.0, 2) AS LOCK_WAIT_SEC "
        "FROM M_EXPENSIVE_STATEMENTS "
        "ORDER BY DURATION_MICROSEC DESC"
    )
    if result.get("status") == "success":
        queries = []
        for idx, row in enumerate(result.get("rows", []), 1):
            queries.append({
                "rank": idx,
                "sql": row.get("SQL_TEXT", ""),
                "duration_sec": row.get("DURATION_SEC", 0),
                "cpu_sec": row.get("CPU_SEC", 0),
                "lock_wait_sec": row.get("LOCK_WAIT_SEC", 0),
            })
        return queries
    return []


def get_database_alerts(hours: int = 24) -> List[Dict[str, Any]]:
    """Get database alerts from STATISTICS_CURRENT_ALERTS."""
    result = run_hdbsql(
        f"SELECT ALERT_ID, ALERT_RATING, ALERT_NAME, ALERT_DETAILS, ALERT_TIMESTAMP "
        f"FROM STATISTICS_CURRENT_ALERTS "
        f"WHERE ALERT_RATING >= 3 "
        f"AND ALERT_TIMESTAMP > ADD_SECONDS(CURRENT_TIMESTAMP, -{hours * 3600}) "
        f"ORDER BY ALERT_TIMESTAMP DESC"
    )
    if result.get("status") == "success":
        alerts = []
        for row in result.get("rows", []):
            rating = row.get("ALERT_RATING", 0)
            alerts.append({
                "alert_id": row.get("ALERT_ID"),
                "rating": rating,
                "severity": "CRITICAL" if rating >= 5 else "WARNING" if rating >= 3 else "INFO",
                "name": row.get("ALERT_NAME", ""),
                "details": row.get("ALERT_DETAILS", ""),
                "timestamp": str(row.get("ALERT_TIMESTAMP", "")),
            })
        return alerts
    return []


def get_blocked_transactions() -> List[Dict[str, Any]]:
    """Get blocked/waiting transactions."""
    result = run_hdbsql(
        "SELECT BLOCKED_CONNECTION_ID, BLOCKED_TRANSACTION_ID, "
        "LOCK_OWNER_CONNECTION_ID, LOCK_OWNER_TRANSACTION_ID, "
        "LOCK_TYPE, BLOCKED_TIME "
        "FROM M_BLOCKED_TRANSACTIONS "
        "ORDER BY BLOCKED_TIME DESC"
    )
    if result.get("status") == "success":
        blocked = []
        for row in result.get("rows", []):
            blocked.append({
                "blocked_connection": row.get("BLOCKED_CONNECTION_ID"),
                "blocked_transaction": row.get("BLOCKED_TRANSACTION_ID"),
                "blocker_connection": row.get("LOCK_OWNER_CONNECTION_ID"),
                "blocker_transaction": row.get("LOCK_OWNER_TRANSACTION_ID"),
                "lock_type": row.get("LOCK_TYPE", ""),
                "blocked_time": str(row.get("BLOCKED_TIME", "")),
            })
        return blocked
    return []


def get_database_info() -> Dict[str, Any]:
    """Get database version, uptime, and key configuration."""
    info = {}

    # Version
    try:
        result = run_hdbsql("SELECT VERSION, USAGE FROM M_DATABASE")
        if result.get("rows"):
            info["version"] = result["rows"][0].get("VERSION", "")
            info["usage"] = result["rows"][0].get("USAGE", "")
    except Exception:
        pass

    # Uptime
    try:
        result = run_hdbsql(
            "SELECT SECONDS_BETWEEN(START_TIME, CURRENT_TIMESTAMP) AS UPTIME_SEC, "
            "START_TIME FROM M_DATABASE"
        )
        if result.get("rows"):
            uptime = result["rows"][0].get("UPTIME_SEC", 0)
            info["uptime_seconds"] = uptime
            info["uptime_human"] = f"{uptime // 86400}d {(uptime % 86400) // 3600}h {(uptime % 3600) // 60}m"
            info["start_time"] = str(result["rows"][0].get("START_TIME", ""))
    except Exception:
        pass

    # Memory allocation
    try:
        result = run_hdbsql(
            "SELECT ROUND(SUM(TOTAL_MEMORY_USED_SIZE) / 1024 / 1024 / 1024, 2) AS USED_GB, "
            "ROUND(SUM(EFFECTIVE_ALLOCATION_LIMIT) / 1024 / 1024 / 1024, 2) AS LIMIT_GB "
            "FROM M_SERVICE_MEMORY"
        )
        if result.get("rows"):
            info["memory_used_gb"] = result["rows"][0].get("USED_GB", 0)
            info["memory_limit_gb"] = result["rows"][0].get("LIMIT_GB", 0)
    except Exception:
        pass

    # Disk usage from HANA perspective
    try:
        result = run_hdbsql(
            "SELECT USAGE_TYPE, "
            "ROUND(USED_SIZE / 1024 / 1024 / 1024, 2) AS USED_GB, "
            "ROUND(TOTAL_SIZE / 1024 / 1024 / 1024, 2) AS TOTAL_GB "
            "FROM M_DISKS"
        )
        if result.get("rows"):
            info["disks"] = result["rows"]
    except Exception:
        pass

    return info


def get_metrics_history(hours: int = 12) -> List[Dict[str, Any]]:
    """Get historical CPU/memory metrics from M_HOST_RESOURCE_UTILIZATION_STATISTICS."""
    result = run_hdbsql(
        f"SELECT SERVER_TIMESTAMP AS TIMESTAMP, "
        f"ROUND(100.0 * (TOTAL_CPU_USER_TIME_DELTA + TOTAL_CPU_SYSTEM_TIME_DELTA) "
        f"/ NULLIF(TOTAL_CPU_USER_TIME_DELTA + TOTAL_CPU_SYSTEM_TIME_DELTA "
        f"+ TOTAL_CPU_WIO_TIME_DELTA + TOTAL_CPU_IDLE_TIME_DELTA, 0), 1) AS CPU_USAGE, "
        f"ROUND(USED_PHYSICAL_MEMORY * 100.0 "
        f"/ NULLIF(USED_PHYSICAL_MEMORY + FREE_PHYSICAL_MEMORY, 0), 1) AS MEMORY_USAGE "
        f"FROM _SYS_STATISTICS.HOST_RESOURCE_UTILIZATION_STATISTICS "
        f"WHERE SERVER_TIMESTAMP > ADD_SECONDS(CURRENT_TIMESTAMP, -{hours * 3600}) "
        f"ORDER BY SERVER_TIMESTAMP ASC"
    )
    if result.get("status") == "success":
        history = []
        for row in result.get("rows", []):
            history.append({
                "timestamp": str(row.get("TIMESTAMP", "")),
                "cpu_usage": row.get("CPU_USAGE"),
                "memory_usage": row.get("MEMORY_USAGE"),
            })
        return history
    return []

# ============================================================================
# Authentication & Security
# ============================================================================

def verify_api_key(x_api_key: str = Header(None)) -> bool:
    """Verify API key from header"""
    if not x_api_key:
        raise HTTPException(status_code=401, detail="X-API-Key header missing")

    if x_api_key != Config.API_KEY:
        logger.warning("Invalid API key attempt from client")
        raise HTTPException(status_code=403, detail="Invalid API key")

    return True

def is_command_allowed(command: str) -> bool:
    """Check if command is in allowlist"""
    # Block command chaining/injection characters
    if re.search(r'[;`]|\$\(|&&|\|\|', command):
        return False
    for allowed in Config.ALLOWED_COMMANDS:
        if command.strip().startswith(allowed):
            return True
    return False

# ============================================================================
# Endpoints
# ============================================================================

@app.get("/")
async def root():
    """Health check endpoint"""
    return {
        "status": "running",
        "service": "Remote Command Execution Server with Diagnostics & Healing",
        "version": "2.0.0",
        "timestamp": datetime.now().isoformat()
    }

@app.get("/health")
async def health_check(x_api_key: str = Header(None)):
    """Authenticated health check with thread pool status"""
    verify_api_key(x_api_key)

    # Thread pool health info
    now_ts = datetime.now().timestamp()
    with _thread_lock:
        active_count = len(_active_threads)
        stuck_threads = [
            {**info, "stuck_seconds": int(now_ts - info["started_ts"])}
            for info in _active_threads.values()
            if now_ts - info["started_ts"] > 120  # stuck > 2 min
        ]

    pool_status = "healthy"
    if len(stuck_threads) > 0:
        pool_status = "degraded"
    if active_count >= 28:  # near exhaustion (32 max)
        pool_status = "critical"

    return {
        "status": "healthy" if pool_status == "healthy" else "degraded",
        "hostname": os.uname().nodename,
        "user": os.getenv("USER", "unknown"),
        "hana_sid": Config.HANA_SID,
        "thread_pool": {
            "status": pool_status,
            "max_workers": 32,
            "active_workers": active_count,
            "stuck_threads": len(stuck_threads),
        },
        "timestamp": datetime.now().isoformat()
    }

@app.get("/thread-pool/status")
async def thread_pool_status(x_api_key: str = Header(None)):
    """
    Detailed thread pool diagnostics — shows all active workers
    and identifies stuck threads. No thread pool worker needed (pure async).
    """
    verify_api_key(x_api_key)

    now_ts = datetime.now().timestamp()
    with _thread_lock:
        threads_info = []
        for tid, info in _active_threads.items():
            elapsed = int(now_ts - info["started_ts"])
            threads_info.append({
                "thread_id": tid,
                "description": info["description"],
                "started_at": info["started_at"],
                "elapsed_seconds": elapsed,
                "stuck": elapsed > 120,
            })

    return {
        "timestamp": datetime.now().isoformat(),
        "max_workers": 32,
        "active_workers": len(threads_info),
        "stuck_count": sum(1 for t in threads_info if t["stuck"]),
        "threads": sorted(threads_info, key=lambda t: t["elapsed_seconds"], reverse=True),
    }

@app.get("/node/info")
async def get_node_info(x_api_key: str = Header(None)):
    """
    Get comprehensive node information (architecture).
    Returns complete system details, capabilities, and status.
    """
    verify_api_key(x_api_key)

    def _gather_node_info():
        # System info
        uname = os.uname()

        # CPU info
        try:
            with open("/proc/cpuinfo", "r") as f:
                cpuinfo = f.read()
                cpu_count = cpuinfo.count("processor")
                cpu_model = ""
                for line in cpuinfo.split("\n"):
                    if "model name" in line:
                        cpu_model = line.split(":")[1].strip()
                        break
        except Exception:
            cpu_count = 0
            cpu_model = "unknown"

        # Memory info
        try:
            with open("/proc/meminfo", "r") as f:
                meminfo = f.read()
                total_mem_kb = 0
                for line in meminfo.split("\n"):
                    if line.startswith("MemTotal:"):
                        total_mem_kb = int(line.split()[1])
                        break
                total_mem_gb = round(total_mem_kb / 1024 / 1024, 2)
        except Exception:
            total_mem_gb = 0

        # Disk info (all mounts)
        try:
            result = subprocess.run(
                ["df", "-h"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                universal_newlines=True,
                timeout=10
            )
            disk_mounts = []
            for line in result.stdout.strip().split("\n")[1:]:
                parts = line.split()
                if len(parts) >= 6:
                    disk_mounts.append({
                        "filesystem": parts[0],
                        "size": parts[1],
                        "used": parts[2],
                        "available": parts[3],
                        "use_percent": parts[4],
                        "mount_point": parts[5]
                    })
        except Exception:
            disk_mounts = []

        # HANA-specific disks
        hana_disks = [d for d in disk_mounts if any(keyword in d["mount_point"].lower() for keyword in ["hana", "hdb", Config.HANA_SID.lower()])]

        # Network interfaces
        try:
            result = subprocess.run(
                ["ip", "-o", "addr", "show"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                universal_newlines=True,
                timeout=10
            )
            interfaces = []
            for line in result.stdout.strip().split("\n"):
                parts = line.split()
                if len(parts) >= 4:
                    interfaces.append({
                        "interface": parts[1],
                        "address": parts[3].split("/")[0],
                        "family": parts[2]
                    })
        except Exception:
            interfaces = []

        return uname, cpu_count, cpu_model, total_mem_gb, hana_disks, disk_mounts, interfaces

    uname, cpu_count, cpu_model, total_mem_gb, hana_disks, disk_mounts, interfaces = await _to_thread(_gather_node_info, _timeout=30, _description="node_info")

    return {
        "node_type": "hana_compute_instance",
        "instance_name": os.uname().nodename,
        "timestamp": datetime.now().isoformat(),

        "system": {
            "hostname": uname.nodename,
            "os": f"{uname.sysname} {uname.release}",
            "architecture": uname.machine,
            "kernel": uname.release,
            "user": os.getenv("USER", "unknown")
        },

        "hardware": {
            "cpu_count": cpu_count,
            "cpu_model": cpu_model,
            "memory_gb": total_mem_gb,
            "disks": hana_disks,
            "all_mounts": disk_mounts
        },

        "network": {
            "interfaces": interfaces
        },

        "hana": {
            "sid": Config.HANA_SID,
            "instance_number": Config.HANA_INSTANCE_NR,
            "user": Config.HANA_USER,
            "base_path": f"/hdb/{Config.HANA_SID}",
            "data_path": f"/hana/data/{Config.HANA_SID}",
            "log_path": f"/hana/log/{Config.HANA_SID}",
            "backup_path": f"/hdb/{Config.HANA_SID}/backup"
        },

        "capabilities": {
            "diagnostics": ["hana_processes", "disk_usage", "memory", "userstore", "system_parameters", "backups"],
            "healing": ["system_parameters", "trace_cleanup"],
            "commands": Config.ALLOWED_COMMANDS
        },

        "status": {
            "server_version": "2.0.0",
            "uptime_seconds": 0,  # Would need to track startup time
            "api_enabled": True,
            "diagnostics_enabled": True,
            "healing_enabled": True
        }
    }

@app.get("/node/specs")
async def get_node_specs(x_api_key: str = Header(None)):
    """Get hardware specifications only"""
    verify_api_key(x_api_key)

    # Get minimal specs
    uname = os.uname()

    try:
        with open("/proc/cpuinfo", "r") as f:
            cpuinfo = f.read()
            cpu_count = cpuinfo.count("processor")
    except Exception:
        cpu_count = 0

    total_mem_gb = 0
    try:
        with open("/proc/meminfo", "r") as f:
            for line in f:
                if line.startswith("MemTotal:"):
                    total_mem_kb = int(line.split()[1])
                    total_mem_gb = round(total_mem_kb / 1024 / 1024, 2)
                    break
    except Exception:
        pass

    return {
        "hostname": uname.nodename,
        "cpu_cores": cpu_count,
        "memory_gb": total_mem_gb,
        "architecture": uname.machine,
        "os": f"{uname.sysname} {uname.release}"
    }

@app.get("/node/capabilities")
async def get_node_capabilities(x_api_key: str = Header(None)):
    """List all capabilities this node provides"""
    verify_api_key(x_api_key)

    return {
        "node_name": os.uname().nodename,
        "node_type": "hana_compute_instance",

        "diagnostics": {
            "available": True,
            "checks": [
                {"name": "hana_processes", "description": "SAP HANA process status via sapcontrol"},
                {"name": "disk_usage", "description": "Disk usage for HANA partitions"},
                {"name": "memory", "description": "System memory usage"},
                {"name": "userstore", "description": "HANA userstore keys"},
                {"name": "system_parameters", "description": "OS parameters (swappiness, THP, ASLR)"},
                {"name": "backups", "description": "Backup directory status"}
            ]
        },

        "healing": {
            "available": True,
            "operations": [
                {
                    "name": "system_parameters",
                    "description": "Fix OS parameters (swappiness, THP, ASLR)",
                    "risk_level": "HIGH",
                    "risk_points": 12,
                    "dry_run_supported": True
                },
                {
                    "name": "trace_cleanup",
                    "description": "Clean up old trace files (>7 days)",
                    "risk_level": "LOW",
                    "risk_points": 3,
                    "dry_run_supported": True
                }
            ]
        },

        "commands": {
            "available": True,
            "allowed_prefixes": Config.ALLOWED_COMMANDS,
            "description": "Execute shell commands from allowed list"
        },

        "hana_monitoring": {
            "available": True,
            "description": "Direct HANA SQL-based monitoring via hdbsql",
            "endpoints": [
                {"path": "/hana/metrics", "description": "Real-time CPU, memory, connections, TPS, blocking, cache hit ratio"},
                {"path": "/hana/metrics/history", "description": "Historical CPU/memory metrics (configurable hours)"},
                {"path": "/hana/services", "description": "HANA service status, ports, memory"},
                {"path": "/hana/transactions", "description": "Active transactions with SQL statements"},
                {"path": "/hana/expensive-queries", "description": "Top N expensive queries by duration"},
                {"path": "/hana/alerts", "description": "Database alerts (warning/critical)"},
                {"path": "/hana/blocking", "description": "Blocked/waiting transactions"},
                {"path": "/hana/info", "description": "Database version, uptime, memory, disk"},
                {"path": "/hana/sql", "description": "Execute read-only SELECT queries"},
            ]
        },

        "apis": {
            "rest": True,
            "authentication": "api_key",
            "base_url": f"http://{Config.HOST}:{Config.PORT}"
        }
    }

@app.get("/diagnostics")
async def run_diagnostics(x_api_key: str = Header(None)):
    """
    Run comprehensive HANA diagnostics.
    All checks are run in Python - no external scripts needed.
    """
    verify_api_key(x_api_key)

    logger.info("Running diagnostics...")

    def _run_all_checks():
        return {
            "hana_processes": check_hana_processes(),
            "disk_usage": check_disk_usage(),
            "memory": check_memory(),
            "userstore": check_userstore(),
            "system_parameters": check_system_parameters(),
            "backups": check_backups()
        }

    results = await _to_thread(_run_all_checks, _timeout=180, _description="diagnostics_all")

    return {
        "timestamp": datetime.now().isoformat(),
        "diagnostics": results
    }

@app.get("/diagnostics/summary")
async def get_diagnostics_summary(x_api_key: str = Header(None)):
    """
    Get a summary of diagnostics (quick health check).
    Returns status indicators without full details.
    """
    verify_api_key(x_api_key)

    def _run_summary_checks():
        results = {
            "hana_processes": check_hana_processes(),
            "disk_usage": check_disk_usage(),
            "memory": check_memory(),
            "system_parameters": check_system_parameters(),
        }
        summary = {"overall_status": "healthy", "checks": {}}
        for check_name, result in results.items():
            status = result.get("status", "unknown")
            summary["checks"][check_name] = status
            if status == "error":
                summary["overall_status"] = "unhealthy"
        return summary

    summary = await _to_thread(_run_summary_checks, _timeout=90, _description="diagnostics_summary")
    summary["timestamp"] = datetime.now().isoformat()
    return summary

@app.get("/observability/system-health")
async def get_system_health(x_api_key: str = Header(None)):
    """
    Observability: Real-time system health summary.
    CPU, memory, disk, I/O, alerts overview.
    """
    verify_api_key(x_api_key)

    def _gather_health():
        # CPU usage
        try:
            result = subprocess.run(
                ["top", "-bn1"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                universal_newlines=True,
                timeout=5
            )
            cpu_line = [l for l in result.stdout.split("\n") if "Cpu(s)" in l]
            cpu_usage = cpu_line[0] if cpu_line else "unknown"
        except Exception:
            cpu_usage = "error"
        memory = check_memory()
        disk = check_disk_usage()
        sys_params = check_system_parameters()
        return cpu_usage, memory, disk, sys_params

    cpu_usage, memory, disk, sys_params = await _to_thread(_gather_health, _timeout=30, _description="system_health")

    return {
        "timestamp": datetime.now().isoformat(),
        "health_status": "healthy",
        "cpu": cpu_usage,
        "memory": memory,
        "disk": disk,
        "system_parameters": sys_params,
        "alerts": []
    }

@app.get("/observability/resource-utilization")
async def get_resource_utilization(x_api_key: str = Header(None)):
    """
    Observability: Analyze CPU, memory, disk I/O statistics.
    """
    verify_api_key(x_api_key)

    def _gather_utilization():
        try:
            with open("/proc/meminfo", "r") as f:
                meminfo = {}
                for line in f:
                    if ":" in line:
                        key, value = line.split(":", 1)
                        meminfo[key.strip()] = value.strip()
        except Exception:
            meminfo = {}
        try:
            with open("/proc/loadavg", "r") as f:
                loadavg = f.read().strip()
        except Exception:
            loadavg = "unknown"
        try:
            result = subprocess.run(
                ["iostat", "-x", "1", "2"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                universal_newlines=True,
                timeout=5
            )
            io_stats = result.stdout if result.returncode == 0 else "iostat not available"
        except Exception:
            io_stats = "error"
        return loadavg, meminfo, io_stats

    loadavg, meminfo, io_stats = await _to_thread(_gather_utilization, _timeout=30, _description="resource_utilization")

    return {
        "timestamp": datetime.now().isoformat(),
        "load_average": loadavg,
        "memory_details": meminfo,
        "disk_io": io_stats
    }

@app.get("/capacity/growth-analysis")
async def get_growth_analysis(x_api_key: str = Header(None)):
    """
    Capacity: Table and schema growth analysis.
    Shows disk usage trends.
    """
    verify_api_key(x_api_key)

    def _gather_growth():
        disk_usage = check_disk_usage()
        backup_status = check_backups()
        disk_summary = []
        if disk_usage.get("status") == "success":
            for line in disk_usage.get("output", "").split("\n")[1:]:
                parts = line.split()
                if len(parts) >= 6:
                    disk_summary.append({
                        "mount": parts[5],
                        "size": parts[1],
                        "used": parts[2],
                        "available": parts[3],
                        "use_percent": parts[4]
                    })
        return disk_summary, backup_status

    disk_summary, backup_status = await _to_thread(_gather_growth, _timeout=30, _description="growth_analysis")

    return {
        "timestamp": datetime.now().isoformat(),
        "disk_usage": disk_summary,
        "backup_storage": backup_status,
        "note": "Historical growth data requires time-series collection"
    }

@app.get("/operational/backup-status")
async def get_backup_status(x_api_key: str = Header(None)):
    """
    Operational: Check backup status and readiness.
    """
    verify_api_key(x_api_key)

    backup_info = await _to_thread(check_backups, _timeout=30, _description="backup_status")

    return {
        "timestamp": datetime.now().isoformat(),
        "backup_directories": backup_info,
        "recommendation": "Verify backup catalog via SQL: SELECT * FROM M_BACKUP_CATALOG ORDER BY ENTRY_ID DESC"
    }

@app.get("/operational/version-info")
async def get_version_info(x_api_key: str = Header(None)):
    """
    Operational: Get database version and configuration.
    """
    verify_api_key(x_api_key)

    def _gather_version():
        try:
            result = subprocess.run(
                ["HDB", "version"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                universal_newlines=True,
                timeout=10
            )
            hana_version = result.stdout if result.returncode == 0 else "HDB command not available"
        except Exception:
            hana_version = "error"
        sys_params = check_system_parameters()
        return hana_version, sys_params

    hana_version, sys_params = await _to_thread(_gather_version, _timeout=30, _description="version_info")

    return {
        "timestamp": datetime.now().isoformat(),
        "hana_version": hana_version,
        "hana_sid": Config.HANA_SID,
        "instance_number": Config.HANA_INSTANCE_NR,
        "system_parameters": sys_params,
        "os_info": f"{os.uname().sysname} {os.uname().release}"
    }

# ============================================================================
# HANA SQL-Based Monitoring Endpoints
# ============================================================================

@app.get("/hana/metrics")
async def hana_realtime_metrics(x_api_key: str = Header(None)):
    """
    Real-time HANA metrics: CPU, memory, connections, TPS,
    active transactions, blocking sessions, cache hit ratio.
    """
    verify_api_key(x_api_key)
    metrics = await _to_thread(get_hana_realtime_metrics, _timeout=90, _description="hana_metrics")
    return {
        "timestamp": datetime.now().isoformat(),
        "metrics": metrics
    }

@app.get("/hana/metrics/history")
async def hana_metrics_history(x_api_key: str = Header(None), hours: int = 12):
    """
    Historical CPU/memory metrics from M_HOST_RESOURCE_UTILIZATION_STATISTICS.
    """
    verify_api_key(x_api_key)
    history = await _to_thread(get_metrics_history, min(hours, 168), _timeout=90, _description="hana_metrics_history")  # cap at 7 days
    return {
        "timestamp": datetime.now().isoformat(),
        "period_hours": hours,
        "data_points": len(history),
        "history": history
    }

@app.get("/hana/services")
async def hana_services(x_api_key: str = Header(None)):
    """
    HANA service status from M_SERVICES.
    Shows each service's name, status, port, memory usage, coordinator type.
    """
    verify_api_key(x_api_key)
    services = await _to_thread(get_hana_services, _timeout=60, _description="hana_services")
    return {
        "timestamp": datetime.now().isoformat(),
        "service_count": len(services),
        "services": services
    }

@app.get("/hana/transactions")
async def hana_active_transactions(x_api_key: str = Header(None)):
    """
    Active transactions with SQL statements, duration, client info.
    Joins M_TRANSACTIONS + M_CONNECTIONS + M_ACTIVE_STATEMENTS.
    """
    verify_api_key(x_api_key)
    transactions = await _to_thread(get_active_transactions, _timeout=60, _description="hana_transactions")
    return {
        "timestamp": datetime.now().isoformat(),
        "active_count": len(transactions),
        "transactions": transactions
    }

@app.get("/hana/expensive-queries")
async def hana_expensive_queries(x_api_key: str = Header(None), top_n: int = 10):
    """
    Top expensive queries from M_EXPENSIVE_STATEMENTS.
    Ranked by duration, includes CPU time and lock wait.
    """
    verify_api_key(x_api_key)
    queries = await _to_thread(get_expensive_queries, min(top_n, 50), _timeout=60, _description="hana_expensive_queries")
    return {
        "timestamp": datetime.now().isoformat(),
        "query_count": len(queries),
        "queries": queries
    }

@app.get("/hana/alerts")
async def hana_alerts(x_api_key: str = Header(None), hours: int = 24):
    """
    Database alerts from STATISTICS_CURRENT_ALERTS (rating >= 3).
    Returns warnings and critical alerts from the specified time window.
    """
    verify_api_key(x_api_key)
    alerts = await _to_thread(get_database_alerts, min(hours, 168), _timeout=60, _description="hana_alerts")
    return {
        "timestamp": datetime.now().isoformat(),
        "period_hours": hours,
        "alert_count": len(alerts),
        "alerts": alerts
    }

@app.get("/hana/blocking")
async def hana_blocked_transactions(x_api_key: str = Header(None)):
    """
    Currently blocked/waiting transactions from M_BLOCKED_TRANSACTIONS.
    Shows blocker and blocked connections with lock type.
    """
    verify_api_key(x_api_key)
    blocked = await _to_thread(get_blocked_transactions, _timeout=60, _description="hana_blocking")
    return {
        "timestamp": datetime.now().isoformat(),
        "blocked_count": len(blocked),
        "blocked_transactions": blocked
    }

@app.get("/hana/info")
async def hana_database_info(x_api_key: str = Header(None)):
    """
    Database overview: version, uptime, memory allocation, disk usage.
    Comprehensive HANA instance information via SQL.
    """
    verify_api_key(x_api_key)
    info = await _to_thread(get_database_info, _timeout=90, _description="hana_info")
    return {
        "timestamp": datetime.now().isoformat(),
        "database": info
    }

@app.get("/hana/sql")
async def hana_run_sql(x_api_key: str = Header(None), query: str = ""):
    """
    Execute a read-only SQL query against HANA.
    Only SELECT statements are allowed for safety.
    """
    verify_api_key(x_api_key)

    if not query.strip():
        raise HTTPException(status_code=400, detail="Query parameter is required")

    # Safety: only allow SELECT queries
    normalized = query.strip().upper()
    if not normalized.startswith("SELECT"):
        raise HTTPException(status_code=403, detail="Only SELECT queries are allowed")

    # Block statement chaining
    if ";" in normalized:
        raise HTTPException(status_code=403, detail="Multiple statements not allowed")

    # Block dangerous patterns (word boundary match to avoid false positives on table names)
    dangerous = ["DROP", "DELETE", "INSERT", "UPDATE", "ALTER", "CREATE", "GRANT", "REVOKE", "TRUNCATE"]
    for keyword in dangerous:
        if re.search(rf'\b{keyword}\b', normalized):
            raise HTTPException(status_code=403, detail=f"Query contains forbidden keyword: {keyword}")

    result = await _to_thread(run_hdbsql, query, 60, _timeout=90, _description="hana_sql_query")
    if result.get("status") == "error":
        raise HTTPException(status_code=500, detail=result.get("error", "Query failed"))

    return {
        "timestamp": datetime.now().isoformat(),
        "query": query,
        "columns": result.get("columns", []),
        "rows": result.get("rows", []),
        "row_count": result.get("row_count", 0)
    }

@app.get("/healing/options")
async def list_healing_options(x_api_key: str = Header(None)):
    """List available healing operations"""
    verify_api_key(x_api_key)

    options = [
        {
            "name": "system_parameters",
            "description": "Fix system parameters (swappiness, THP, ASLR)",
            "risk_level": "HIGH",
            "risk_points": 12
        },
        {
            "name": "trace_cleanup",
            "description": "Clean up old trace files (>7 days)",
            "risk_level": "LOW",
            "risk_points": 3
        }
    ]

    return {"healing_options": options}

@app.post("/healing/execute/{operation}")
async def execute_healing(
    operation: str,
    x_api_key: str = Header(None),
    dry_run: bool = True
):
    """
    Execute a healing operation.

    Parameters:
    - operation: Name of the healing operation
    - dry_run: If true, runs in simulation mode (default: true)
    """
    verify_api_key(x_api_key)

    logger.info(f"Executing healing operation: {operation} (dry_run={dry_run})")

    if operation == "system_parameters":
        result = await _to_thread(heal_system_parameters, dry_run, _timeout=60, _description="heal_system_params")
    elif operation == "trace_cleanup":
        result = await _to_thread(heal_trace_cleanup, dry_run, _timeout=60, _description="heal_trace_cleanup")
    else:
        raise HTTPException(
            status_code=404,
            detail=f"Healing operation '{operation}' not found"
        )

    return {
        "operation": operation,
        "dry_run": dry_run,
        "timestamp": datetime.now().isoformat(),
        **result
    }

@app.post("/execute", response_model=CommandResponse)
async def execute_command(
    cmd_request: CommandRequest,
    request: Request,
    x_api_key: str = Header(None)
):
    """
    Execute a shell command on the server.

    Security:
    - Requires valid API key
    - Command must be in allowlist
    - Command length limits
    - Timeout limits
    """
    # Authentication
    verify_api_key(x_api_key)

    command = cmd_request.command
    timeout = min(cmd_request.timeout, Config.COMMAND_TIMEOUT)
    admin_override = bool(cmd_request.admin_override)

    # Validation
    if len(command) > Config.MAX_COMMAND_LENGTH:
        raise HTTPException(status_code=400, detail="Command too long")

    if not admin_override and not is_command_allowed(command):
        logger.warning(f"Blocked command attempt: {command[:100]}")
        raise HTTPException(
            status_code=403,
            detail=f"Command not allowed. Allowed prefixes: {Config.ALLOWED_COMMANDS}"
        )

    # Auto-detect HANA commands that need to run as HANA admin user
    needs_hana_user = any(command.strip().startswith(prefix) for prefix in Config.HANA_USER_COMMANDS)

    # Log the execution
    if admin_override:
        logger.warning(f"Executing with ADMIN OVERRIDE from {request.client.host}: {command[:200]}")
    elif needs_hana_user:
        logger.info(f"Executing HANA command as {Config.HANA_USER} from {request.client.host}: {command[:100]}")
    else:
        logger.info(f"Executing command from {request.client.host}: {command[:100]}")

    # Execute command
    start_time = datetime.now()
    try:
        if needs_hana_user:
            # HANA commands must run as HANA admin user for correct PATH/environment
            hana_result = await _to_thread(run_shell_as_hana_user, command, timeout, _timeout=timeout + 30, _description=f"execute_hana:{command[:50]}")
            execution_time = (datetime.now() - start_time).total_seconds()

            response = CommandResponse(
                status=hana_result.get("status", "error"),
                exit_code=hana_result.get("exit_code", 1),
                stdout=hana_result.get("output", ""),
                stderr=hana_result.get("error", "") or "",
                execution_time=execution_time,
                timestamp=datetime.now().isoformat()
            )
        else:
            cmd_result = await _to_thread(
                _run_subprocess_safe, command, timeout, True, cmd_request.working_dir,
                _timeout=timeout + 30, _description=f"execute_cmd:{command[:50]}"
            )

            execution_time = (datetime.now() - start_time).total_seconds()

            response = CommandResponse(
                status=cmd_result.get("status", "error"),
                exit_code=cmd_result.get("exit_code", 1),
                stdout=cmd_result.get("output", ""),
                stderr=cmd_result.get("error", "") or "",
                execution_time=execution_time,
                timestamp=datetime.now().isoformat()
            )

        logger.info(f"Command completed: exit_code={response.exit_code}, time={execution_time:.2f}s")

        return response

    except subprocess.TimeoutExpired:
        logger.error(f"Command timeout: {command[:100]}")
        raise HTTPException(status_code=408, detail=f"Command timeout after {timeout}s")

    except Exception as e:
        logger.error(f"Command execution failed: {e}")
        raise HTTPException(status_code=500, detail=f"Execution error: {str(e)}")


@app.post("/execute-as-user", response_model=CommandResponse)
async def execute_command_as_user(
    cmd_request: CommandRequest,
    request: Request,
    user: str = "",
    x_api_key: str = Header(None)
):
    """
    Execute a shell command as a specific user (e.g., HANA admin for HANA commands).

    HANA commands (sapcontrol, HDB, hdbsql, hdbuserstore) require execution as
    the HANA admin user because:
    - HANA binaries are in the admin user's PATH
    - Environment variables (HANA_HOME, etc.) are set in the admin user's profile

    Security:
    - Requires valid API key
    - Command must be in allowlist
    - Uses sudo -i -u for proper environment loading
    """
    # Authentication
    verify_api_key(x_api_key)

    # Default to configured HANA user if not specified
    if not user:
        user = Config.HANA_USER

    command = cmd_request.command
    timeout = min(cmd_request.timeout, Config.COMMAND_TIMEOUT)
    admin_override = bool(cmd_request.admin_override)

    # Validation
    if len(command) > Config.MAX_COMMAND_LENGTH:
        raise HTTPException(status_code=400, detail="Command too long")

    if not admin_override and not is_command_allowed(command):
        logger.warning(f"Blocked command attempt: {command[:100]}")
        raise HTTPException(
            status_code=403,
            detail=f"Command not allowed. Allowed prefixes: {Config.ALLOWED_COMMANDS}"
        )

    # Validate user (only allow HANA user for security)
    allowed_users = [Config.HANA_USER, "root"]
    if user not in allowed_users:
        raise HTTPException(
            status_code=403,
            detail=f"User '{user}' not allowed. Allowed users: {allowed_users}"
        )

    # Log the execution
    if admin_override:
        logger.warning(f"Executing command as {user} with ADMIN OVERRIDE from {request.client.host}: {command[:200]}")
    else:
        logger.info(f"Executing command as {user} from {request.client.host}: {command[:100]}")

    # Execute command as specified user
    start_time = datetime.now()
    try:
        # Use sudo -i -u to get full login environment (PATH, HANA_HOME, etc.)
        full_command = f"sudo -i -u {shlex.quote(user)} bash -c {shlex.quote(command)}"

        cmd_result = await _to_thread(
            _run_subprocess_safe, full_command, timeout, True, cmd_request.working_dir,
            _timeout=timeout + 30, _description=f"execute_as_{user}:{command[:50]}"
        )

        execution_time = (datetime.now() - start_time).total_seconds()

        response = CommandResponse(
            status=cmd_result.get("status", "error"),
            exit_code=cmd_result.get("exit_code", 1),
            stdout=cmd_result.get("output", ""),
            stderr=cmd_result.get("error", "") or "",
            execution_time=execution_time,
            timestamp=datetime.now().isoformat()
        )

        logger.info(f"Command completed as {user}: exit_code={response.exit_code}, time={execution_time:.2f}s")

        return response

    except subprocess.TimeoutExpired:
        logger.error(f"Command timeout as {user}: {command[:100]}")
        raise HTTPException(status_code=408, detail=f"Command timeout after {timeout}s")

    except Exception as e:
        logger.error(f"Command execution as {user} failed: {e}")
        raise HTTPException(status_code=500, detail=f"Execution error: {str(e)}")


# ============================================================================
# Startup Configuration
# ============================================================================

@app.on_event("startup")
async def startup_event():
    """Log startup information"""
    logger.info("=" * 60)
    logger.info("Remote Execution Server with Diagnostics & Healing")
    logger.info("=" * 60)
    logger.info(f"Host: {Config.HOST}:{Config.PORT}")
    logger.info(f"API Key configured: Yes (base64 secure key)")
    logger.info(f"HANA SID: {Config.HANA_SID}")
    logger.info(f"HANA Instance: {Config.HANA_INSTANCE_NR}")
    logger.info(f"Allowed commands: {len(Config.ALLOWED_COMMANDS)} prefixes")
    logger.info("=" * 60)

# ============================================================================
# Main
# ============================================================================

if __name__ == "__main__":
    logger.info("Using pre-configured secure base64 API key")
    logger.info("Server ready with built-in diagnostics and healing")

    # Start server
    uvicorn.run(
        app,
        host=Config.HOST,
        port=Config.PORT,
        log_level="info"
    )
