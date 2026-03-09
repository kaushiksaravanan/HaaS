"""
HANA Client Tools — ADK-compatible tool functions.
Each function is a standalone tool that can be passed to google.adk.agents.Agent.
Routes ALL queries through the remote_exec_server running on the HANA host.
The remote server uses local hdbsql + userstore keys — no password needed.
PRD Sections: 7, 8, 13

Connection Strategy (via Remote Exec Server):
  1. HTTP call to remote_exec_server /hana/sql for SELECT queries
  2. HTTP call to remote_exec_server /hana/info for connection checks
  3. HTTP call to remote_exec_server /hana/metrics for realtime metrics
  NEVER returns mock data — always returns real results or explicit errors.
"""

import os
import time
import logging
import requests
from typing import Optional

logger = logging.getLogger(__name__)

# ──────────────────────────────────────────────
# Remote Exec Server connection config
# ──────────────────────────────────────────────
_REMOTE_EXEC_URL = os.getenv("REMOTE_EXEC_URL", "http://10.238.36.146:9999")
_REMOTE_EXEC_API_KEY = os.getenv("REMOTE_EXEC_API_KEY", "REMOTE_EXEC_KEY_REVOKED_PLACEHOLDER_0000000000000000")
_REQUEST_TIMEOUT = int(os.getenv("HANA_CONNECT_TIMEOUT", "15"))

# Connection state tracking (for force-reconnect and status)
_last_connect_attempt = 0
_last_connect_failed = False
_RECONNECT_COOLDOWN = 10  # seconds between reconnect attempts after failure
_cached_db_info = None  # Cache connection info to avoid repeated calls


def _remote_headers():
    """Standard headers for remote exec server calls."""
    return {"X-API-Key": _REMOTE_EXEC_API_KEY}


def _get_connection(force_reconnect: bool = False):
    """Check connectivity to HANA via remote exec server.
    Returns a truthy dict on success, None on failure."""
    global _last_connect_attempt, _last_connect_failed, _cached_db_info

    # Return cached info if recent and not forcing
    if not force_reconnect and _cached_db_info is not None:
        if time.time() - _last_connect_attempt < _RECONNECT_COOLDOWN:
            return _cached_db_info if not _last_connect_failed else None

    # Cooldown to prevent hammering
    now = time.time()
    if not force_reconnect and _last_connect_failed:
        if now - _last_connect_attempt < _RECONNECT_COOLDOWN:
            return None

    _last_connect_attempt = now

    try:
        resp = requests.get(
            f"{_REMOTE_EXEC_URL}/hana/info",
            headers=_remote_headers(),
            timeout=_REQUEST_TIMEOUT,
        )
        if resp.status_code == 200:
            data = resp.json()
            db_info = data.get("database", {})
            if db_info:
                _last_connect_failed = False
                _cached_db_info = db_info
                logger.info(f"HANA reachable via remote exec: {db_info.get('DATABASE_NAME', '?')}")
                return db_info
        _last_connect_failed = True
        _cached_db_info = None
        logger.warning(f"Remote exec /hana/info returned {resp.status_code}")
        return None
    except Exception as e:
        _last_connect_failed = True
        _cached_db_info = None
        logger.warning(f"Remote exec server unreachable: {e}")
        return None


# ──────────────────────────────────────────────
# ADK Tool Functions — via Remote Exec Server
# ──────────────────────────────────────────────


def query_hana(query: str) -> dict:
    """Execute a read-only SQL query on SAP HANA via the remote exec server.
    NEVER returns mock data.

    Args:
        query (str): The SQL SELECT query to execute on HANA.

    Returns:
        dict: status and list of result rows, or error message.
    """
    try:
        resp = requests.get(
            f"{_REMOTE_EXEC_URL}/hana/sql",
            params={"query": query},
            headers=_remote_headers(),
            timeout=_REQUEST_TIMEOUT + 15,
        )
        if resp.status_code == 200:
            data = resp.json()
            # Remote /hana/sql returns {timestamp, query, columns, rows, row_count} on success — no "status" field
            rows = data.get("rows", [])
            return {
                "status": "success",
                "source": "live",
                "rows": rows,
                "row_count": data.get("row_count", len(rows)),
            }
        elif resp.status_code == 403:
            return {
                "status": "error",
                "error_message": "Only SELECT queries are allowed",
            }
        else:
            return {
                "status": "error",
                "error_message": f"Remote exec returned HTTP {resp.status_code}: {resp.text[:200]}",
            }
    except requests.exceptions.Timeout:
        return {
            "status": "error",
            "error_message": f"Timeout querying HANA via remote exec at {_REMOTE_EXEC_URL}",
        }
    except requests.exceptions.ConnectionError:
        return {
            "status": "error",
            "error_message": f"Cannot reach remote exec server at {_REMOTE_EXEC_URL}. Is it running?",
        }
    except Exception as e:
        return {"status": "error", "error_message": str(e)}


def execute_hana_sql(statement: str) -> dict:
    """Execute a SQL statement on SAP HANA via remote exec server /execute.
    For write operations, sends the statement via the command execution endpoint.

    Args:
        statement (str): The SQL statement to execute.

    Returns:
        dict: status indicating success or failure with details.
    """
    try:
        # Use hdbsql via /execute for write operations
        resp = requests.post(
            f"{_REMOTE_EXEC_URL}/execute",
            json={
                "command": f'hdbsql -U SYSTEM -j -a -x "{statement}"',
                "timeout": _REQUEST_TIMEOUT + 15,
                "admin_override": True,
            },
            headers=_remote_headers(),
            timeout=_REQUEST_TIMEOUT + 20,
        )
        if resp.status_code == 200:
            data = resp.json()
            stderr = data.get("stderr", "")
            if data.get("return_code", data.get("exit_code", 1)) == 0:
                return {
                    "status": "success",
                    "source": "live",
                    "message": "Statement executed successfully",
                    "output": data.get("stdout", "") or data.get("output", ""),
                }
            return {
                "status": "error",
                "error_message": stderr or data.get("stdout", "") or "Statement execution failed",
            }
        return {
            "status": "error",
            "error_message": f"Remote exec returned HTTP {resp.status_code}",
        }
    except Exception as e:
        return {"status": "error", "error_message": str(e)}


def check_hana_connection() -> dict:
    """Check if SAP HANA database connection is alive via the remote exec server.
    Performs a real connection test — never returns mock status.

    Returns:
        dict: connection status, HANA version, database name, and host details.
    """
    remote_url = _REMOTE_EXEC_URL

    try:
        resp = requests.get(
            f"{remote_url}/hana/info",
            headers=_remote_headers(),
            timeout=_REQUEST_TIMEOUT,
        )
        if resp.status_code == 200:
            data = resp.json()
            db = data.get("database", {})
            if db:
                return {
                    "status": "connected",
                    "source": "live",
                    "version": db.get("VERSION", "unknown"),
                    "database": db.get("DATABASE_NAME", "unknown"),
                    "host": remote_url,
                    "port": "via remote exec",
                }
        return {
            "status": "disconnected",
            "error": f"Remote exec /hana/info returned {resp.status_code}",
            "host": remote_url,
            "port": "via remote exec",
        }
    except requests.exceptions.ConnectionError:
        return {
            "status": "disconnected",
            "error": f"Cannot reach remote exec server at {remote_url}",
            "host": remote_url,
            "port": "via remote exec",
        }
    except Exception as e:
        return {
            "status": "disconnected",
            "error": str(e),
            "host": remote_url,
            "port": "via remote exec",
        }


def get_remote_hana_metrics() -> dict:
    """Fetch real-time HANA metrics directly from the remote exec server's /hana/metrics.
    Returns pre-aggregated metrics (CPU, memory, connections, TPS, etc.)."""
    try:
        resp = requests.get(
            f"{_REMOTE_EXEC_URL}/hana/metrics",
            headers=_remote_headers(),
            timeout=_REQUEST_TIMEOUT,
        )
        if resp.status_code == 200:
            data = resp.json()
            return {"status": "success", "metrics": data.get("metrics", {})}
        return {"status": "error", "error_message": f"HTTP {resp.status_code}"}
    except Exception as e:
        return {"status": "error", "error_message": str(e)}


def execute_remote_command(command: str, timeout: int = 30, admin_override: bool = False) -> dict:
    """Execute a shell command on the remote HANA host via the HTTP remote exec server.

    Args:
        command (str): Shell command to execute on the remote host.
        timeout (int): Command timeout in seconds.
        admin_override (bool): If True, bypass command allowlist.

    Returns:
        dict: status, stdout, stderr, exit_code from the command execution.
    """
    try:
        resp = requests.post(
            f"{_REMOTE_EXEC_URL}/execute",
            json={
                "command": command,
                "timeout": timeout,
                "admin_override": admin_override,
            },
            headers=_remote_headers(),
            timeout=timeout + 10,
        )
        if resp.status_code == 200:
            data = resp.json()
            return {
                "status": data.get("status", "success"),
                "source": "remote_exec",
                "stdout": data.get("output", data.get("stdout", "")),
                "stderr": data.get("stderr", ""),
                "exit_code": data.get("exit_code", 0),
                "output": data.get("output", data.get("stdout", "")),
            }
        return {
            "status": "error",
            "error_message": f"Remote exec returned HTTP {resp.status_code}: {resp.text[:200]}",
        }
    except requests.exceptions.Timeout:
        return {"status": "error", "error_message": f"Command timed out after {timeout}s"}
    except requests.exceptions.ConnectionError:
        return {"status": "error", "error_message": f"Cannot reach remote exec server at {_REMOTE_EXEC_URL}"}
    except Exception as e:
        return {"status": "error", "error_message": str(e)}
