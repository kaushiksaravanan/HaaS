"""
HANA Sentinel — FastAPI REST API Control Plane.
PRD Section 14 — All endpoints with OpenTelemetry trace correlation.
"""

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import Optional, Dict, Any, List
from datetime import datetime
import uuid
import os
import json
import asyncio
import logging
import threading

logger = logging.getLogger(__name__)

from .models import (
    ActionCertificate,
    PolicyEngine,
    RiskBudget,
)
from .tools.hana_tools import query_hana, check_hana_connection, _get_connection, execute_remote_command
from .tools.rag_tools import rag_query
from .tools.instance_diagnostics import run_instance_diagnostic
from .tools.gcp_snapshot_tools import create_instance_snapshot, list_instance_snapshots
from .tools.instance_healing_tools import execute_healing_script, verify_healing_execution
from .tools.instance_logger import get_instance_logger

app = FastAPI(
    title="HANA Sentinel API",
    description="Autonomous Policy-Driven Multi-Agent AI for SAP HANA Operations",
    version="2.0.0",
)

# Mount static files for frontend
frontend_build_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "frontend", "dist")
if os.path.exists(frontend_build_path):
    app.mount("/assets", StaticFiles(directory=os.path.join(frontend_build_path, "assets")), name="assets")

# ──────────────────────────────────────────────
# In-memory stores (production: PostgreSQL + pgvector)
# ──────────────────────────────────────────────
_certificates: Dict[str, ActionCertificate] = {}
_risk_budgets: Dict[str, RiskBudget] = {}
_instance_diagnostics: Dict[str, dict] = {}
_instance_healing_proposals: Dict[str, dict] = {}
_instance_snapshots: Dict[str, dict] = {}
_restricted_command_approvals: Dict[str, dict] = {}

# ──────────────────────────────────────────────
# Persistent diagnostic history (JSON file)
# ──────────────────────────────────────────────
_DIAG_HISTORY_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)), "logs", "instance", "diagnostic_history.json")


def _load_diagnostic_history():
    """Load diagnostic history from disk into memory on startup."""
    global _instance_diagnostics
    try:
        if os.path.exists(_DIAG_HISTORY_FILE):
            with open(_DIAG_HISTORY_FILE, "r") as f:
                _instance_diagnostics = json.load(f)
            logger.info(f"Loaded {len(_instance_diagnostics)} diagnostics from history")
    except Exception as exc:
        logger.warning(f"Failed to load diagnostic history: {exc}")


def _save_diagnostic_history():
    """Persist current diagnostics to disk."""
    try:
        os.makedirs(os.path.dirname(_DIAG_HISTORY_FILE), exist_ok=True)
        with open(_DIAG_HISTORY_FILE, "w") as f:
            json.dump(_instance_diagnostics, f, default=str)
    except Exception as exc:
        logger.warning(f"Failed to save diagnostic history: {exc}")


def _get_diagnostic_context(max_entries: int = 5) -> str:
    """Build a concise diagnostic history summary for LLM context."""
    if not _instance_diagnostics:
        return ""
    # Sort by timestamp descending, take the most recent entries
    sorted_diags = sorted(
        _instance_diagnostics.values(),
        key=lambda x: x.get("timestamp", ""),
        reverse=True,
    )[:max_entries]

    lines = ["=== Recent Diagnostic History (vlgdbzo3) ==="]
    for d in sorted_diags:
        ts = d.get("timestamp", "unknown")
        status = d.get("overall_status", "unknown")
        issues = d.get("issues_detected", [])
        issue_count = d.get("issue_count", 0)
        diag_id = d.get("diagnostic_id", "unknown")
        lines.append(f"\n[{ts}] Status: {status.upper()} | Issues: {issue_count} | ID: {diag_id}")
        if issues:
            for issue in issues[:5]:
                lines.append(f"  - {issue}")
        # Include key check summaries
        checks = d.get("checks", {})
        for check_name, check_data in checks.items():
            if isinstance(check_data, dict):
                severity = check_data.get("severity", "")
                msg = check_data.get("message", "")
                if severity in ("warning", "critical") or check_name in ("memory_usage", "disk_usage", "backup_status"):
                    short_msg = (msg[:120] + "...") if len(str(msg)) > 120 else msg
                    lines.append(f"  {check_name}: [{severity}] {short_msg}")
    return "\n".join(lines)


# Load history on import
_load_diagnostic_history()


# ──────────────────────────────────────────────
# WebSocket Connection Manager
# ──────────────────────────────────────────────
class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    async def broadcast(self, message: dict):
        dead_connections = []
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except Exception:
                dead_connections.append(connection)

        # Clean up dead connections
        for connection in dead_connections:
            self.disconnect(connection)

manager = ConnectionManager()


# ──────────────────────────────────────────────
# Request/Response Models
# ──────────────────────────────────────────────
class RAGQueryRequest(BaseModel):
    question: str


class AgentChatRequest(BaseModel):
    message: str
    conversation_id: Optional[str] = None
    admin_mode: bool = False
    use_browser: bool = False  # When True, always browse SAP docs for answers
    autonomous_browser: bool = False  # When True, use browser-use agent (like Manus)
    voice_mode: bool = False  # When True, return voice-friendly summaries instead of markdown


# ──────────────────────────────────────────────
# Agent Endpoints
# ──────────────────────────────────────────────
# Agent registry - maps agent IDs to their module paths and metadata
# Status is determined at runtime by checking if the agent can be instantiated
AGENT_DEFINITIONS = {
    "health_agent": {
        "name": "Health Monitor Agent",
        "module": "adk_app.agents.health_agent",
        "class": "HealthAgent",
        "risk_tier": "low",
        "description": "Monitors SAP HANA system health including memory, disk, and services"
    },
    "backup_agent": {
        "name": "Backup Agent",
        "module": "adk_app.agents.backup_agent",
        "class": "BackupAgent",
        "risk_tier": "medium",
        "description": "Manages HANA backup operations and status checks"
    },
    "recovery_agent": {
        "name": "Recovery Agent",
        "module": "adk_app.agents.recovery_agent",
        "class": "RecoveryAgent",
        "risk_tier": "high",
        "description": "Handles system recovery and restoration operations"
    },
    "sql_tuning_agent": {
        "name": "SQL Tuning Agent",
        "module": "adk_app.agents.sql_tuning_agent",
        "class": "SQLTuningAgent",
        "risk_tier": "medium",
        "description": "Analyzes and optimizes SQL query performance"
    },
    "capacity_agent": {
        "name": "Capacity Agent",
        "module": "adk_app.agents.capacity_agent",
        "class": "CapacityAgent",
        "risk_tier": "medium",
        "description": "Monitors and predicts capacity requirements"
    },
    "browser_agent": {
        "name": "Browser-Use Agent",
        "module": "adk_app.agents.browser_agent",
        "class": "BrowserUseAgent",
        "risk_tier": "medium",
        "description": "Automates browser-based tasks for SAP support"
    },
    "instance_monitor_agent": {
        "name": "VM Monitor Agent",
        "module": "adk_app.agents.instance_monitor_agent",
        "class": "InstanceMonitorAgent",
        "risk_tier": "low",
        "description": "Monitors GCP instance health and diagnostics"
    },
    "instance_backup_agent": {
        "name": "VM Backup Agent",
        "module": "adk_app.agents.instance_backup_agent",
        "class": "InstanceBackupAgent",
        "risk_tier": "medium",
        "description": "Manages GCP instance snapshots and backups"
    },
    "instance_healing_agent": {
        "name": "Healing Agent",
        "module": "adk_app.agents.instance_healing_agent",
        "class": "InstanceHealingAgent",
        "risk_tier": "high",
        "description": "Executes remediation scripts on instances"
    },
}


def _check_agent_status(agent_id: str) -> str:
    """Check if an agent module can be loaded."""
    if agent_id not in AGENT_DEFINITIONS:
        return "unknown"
    try:
        agent_def = AGENT_DEFINITIONS[agent_id]
        module_name = agent_def["module"]
        # Try to import the module to verify it exists
        import importlib
        importlib.import_module(module_name)
        return "available"
    except Exception:
        return "unavailable"


@app.get("/api/v1/agents")
def list_agents():
    """List all registered agents with real-time status."""
    agents = []
    for agent_id, agent_def in AGENT_DEFINITIONS.items():
        agents.append({
            "id": agent_id,
            "name": agent_def["name"],
            "status": _check_agent_status(agent_id),
            "risk_tier": agent_def["risk_tier"],
            "description": agent_def["description"],
        })
    return {"agents": agents}


@app.get("/api/v1/agents/graph")
def get_agent_graph():
    """Return the full agent graph structure for the flow visualization.

    Introspects the real agent definitions from adk_app.agent to build
    nodes (supervisor, sub-agents, tool groups) and edges dynamically.
    """
    try:
        from .agent import root_agent
    except Exception as exc:
        logger.warning(f"Failed to import root_agent for graph: {exc}")
        return {"nodes": [], "edges": [], "quick_actions": {}}

    # ── colour palette for agents (cycle through) ──
    _COLORS = [
        "#10b981", "#3b82f6", "#f59e0b", "#06b6d4",
        "#ec4899", "#14b8a6", "#8b5cf6", "#f97316",
        "#6366f1", "#ef4444", "#22d3ee", "#a855f7",
        "#84cc16",
    ]

    # ── Classify tool functions into named groups ──
    _TOOL_GROUP_RULES = [
        # (substring in module path or func name, group_id, label, description)
        ("hana_tools",    "hana_tools",   "HANA Tools",   "Direct HANA connection & SQL"),
        ("hana_client",   "hana_tools",   "HANA Tools",   "Direct HANA connection & SQL"),
        ("instance_diagnostics", "instance_diag", "Instance Diagnostics", "Diagnostic checks via HTTP"),
        ("instance_healing",     "instance_heal", "Instance Healing",     "Healing scripts via HTTP"),
        ("gcp_snapshot",  "gcp_snapshots", "GCP Snapshots", "VM snapshot management"),
        ("instance_logger","instance_log", "Instance Logger","Instance activity logging"),
        ("rag_tools",     "rag_tools",    "RAG Tools",     "Knowledge base queries"),
        ("log_preprocessor","log_preproc","Log Preprocessor","Log analysis & HDB storage"),
        ("browser",       "browser_tools","Browser Tools",  "Web automation & verification"),
        ("remote",        "remote_exec",  "Remote Exec",   "OS-level operations via HTTP"),
        ("http_command",  "remote_exec",  "Remote Exec",   "OS-level operations via HTTP"),
        ("diagnostic",    "instance_diag","Instance Diagnostics", "Diagnostic checks via HTTP"),
        ("snapshot",      "gcp_snapshots","GCP Snapshots", "VM snapshot management"),
        ("verify",        "browser_tools","Browser Tools",  "Web automation & verification"),
        ("healing",       "instance_heal","Instance Healing","Healing scripts via HTTP"),
    ]

    def _classify_tool(func) -> tuple:
        """Return (group_id, group_label, group_desc) for a tool function."""
        module = getattr(func, "__module__", "") or ""
        name = getattr(func, "__name__", "") or ""
        for substr, gid, label, desc in _TOOL_GROUP_RULES:
            if substr in module or substr in name:
                return gid, label, desc
        return "other_tools", "Other Tools", "Miscellaneous tools"

    # ── Build supervisor node ──
    nodes = []
    edges = []
    tool_groups = {}          # group_id -> {label, desc}
    agent_tool_links = {}     # agent_id -> set of group_ids

    nodes.append({
        "id": "supervisor",
        "label": root_agent.name.replace("_", " ").title() if hasattr(root_agent, "name") else "Supervisor",
        "description": (root_agent.description or "Orchestrates all agents")[:120],
        "color": "#8b5cf6",
        "type": "supervisor",
        "risk_tier": "orchestrator",
        "status": "active",
        "tools": [],
    })

    # ── Build sub-agent nodes from the actual root_agent.sub_agents ──
    sub_agents = getattr(root_agent, "sub_agents", []) or []
    for idx, sa in enumerate(sub_agents):
        agent_id = getattr(sa, "name", f"agent_{idx}")
        color = _COLORS[idx % len(_COLORS)]

        # Collect the tool functions attached to this agent
        tools_list = getattr(sa, "tools", []) or []
        tool_names = []
        linked_groups = set()
        for t in tools_list:
            fname = getattr(t, "__name__", str(t))
            tool_names.append(fname)
            gid, glabel, gdesc = _classify_tool(t)
            linked_groups.add(gid)
            tool_groups[gid] = {"label": glabel, "description": gdesc}

        agent_tool_links[agent_id] = linked_groups

        # Lookup runtime status from AGENT_DEFINITIONS if present
        agent_def = AGENT_DEFINITIONS.get(agent_id, {})
        risk_tier = agent_def.get("risk_tier", "medium")
        status = _check_agent_status(agent_id) if agent_id in AGENT_DEFINITIONS else "available"

        nodes.append({
            "id": agent_id,
            "label": agent_def.get("name", sa.name.replace("_", " ").title()),
            "description": (agent_def.get("description") or (sa.description or "")[:120]),
            "color": color,
            "type": "agent",
            "risk_tier": risk_tier,
            "status": "active" if status == "available" else "error" if status == "unavailable" else "idle",
            "tools": tool_names,
        })

        # Edge: supervisor -> agent
        edges.append({
            "id": f"e-sup-{agent_id}",
            "source": "supervisor",
            "target": agent_id,
        })

    # ── Build tool-group nodes ──
    for gid, ginfo in tool_groups.items():
        nodes.append({
            "id": gid,
            "label": ginfo["label"],
            "description": ginfo["description"],
            "color": "#6366f1",
            "type": "tool_group",
            "risk_tier": "tool",
            "status": "idle",
            "tools": [],
        })

    # ── Edges: agent -> tool-group ──
    for agent_id, groups in agent_tool_links.items():
        for gid in groups:
            edges.append({
                "id": f"e-{agent_id}-{gid}",
                "source": agent_id,
                "target": gid,
            })

    # ── Quick actions (derive from agent descriptions + sensible defaults) ──
    _DEFAULT_QUICK_ACTIONS = {
        "supervisor": [
            {"label": "Status summary", "prompt": "Give me a status summary of all agents and system health"},
            {"label": "Full diagnostics", "prompt": "Run a full diagnostic check on the HANA system"},
        ],
    }

    _KEYWORD_QUICK_ACTIONS = {
        "health": [
            {"label": "Health check", "prompt": "Run a health check on the HANA system"},
            {"label": "Check services", "prompt": "Check all HANA service statuses"},
            {"label": "Memory analysis", "prompt": "Analyze current memory usage on the HANA system"},
        ],
        "backup": [
            {"label": "Backup status", "prompt": "Show the current backup status and last successful backup"},
            {"label": "List backups", "prompt": "List all recent HANA backups with their status"},
        ],
        "recovery": [
            {"label": "Recovery readiness", "prompt": "Check disaster recovery readiness and latest recovery points"},
            {"label": "List snapshots", "prompt": "Show all available snapshots for recovery"},
        ],
        "sql_tuning": [
            {"label": "Top queries", "prompt": "Show the top expensive SQL queries currently running"},
            {"label": "Index suggestions", "prompt": "Analyze the system for index optimization opportunities. First query these views and collect all data: 1) SELECT TOP 20 STATEMENT_STRING, EXECUTION_COUNT, TOTAL_EXECUTION_TIME, AVG_EXECUTION_TIME FROM M_SQL_PLAN_CACHE ORDER BY TOTAL_EXECUTION_TIME DESC 2) SELECT SCHEMA_NAME, TABLE_NAME, INDEX_NAME, INDEX_TYPE, CONSTRAINT FROM INDEXES WHERE SCHEMA_NAME NOT LIKE '_SYS%' ORDER BY SCHEMA_NAME, TABLE_NAME 3) SELECT TOP 20 STATEMENT_STRING, DURATION_MICROSEC, CPU_TIME, LOCK_WAIT_DURATION FROM M_EXPENSIVE_STATEMENTS ORDER BY DURATION_MICROSEC DESC 4) SELECT SCHEMA_NAME, TABLE_NAME, RECORD_COUNT, TABLE_SIZE FROM M_CS_TABLES WHERE SCHEMA_NAME NOT LIKE '_SYS%' ORDER BY TABLE_SIZE DESC LIMIT 30. Then based on ALL collected data, suggest specific CREATE INDEX statements with reasoning for each, showing which slow queries each index would improve."},
        ],
        "capacity": [
            {"label": "Disk usage", "prompt": "Show current disk usage and capacity forecast"},
            {"label": "Growth trend", "prompt": "Analyze data growth trend for the last 30 days"},
        ],
        "browser": [
            {"label": "Search SAP notes", "prompt": "Search SAP notes for recent HANA patches and fixes"},
            {"label": "Find docs", "prompt": "Find SAP documentation for HANA backup and recovery best practices"},
        ],
        "rag": [
            {"label": "Search knowledge", "prompt": "Search our knowledge base for recent SAP HANA issues"},
            {"label": "Ingest note", "prompt": "Ingest a new SAP note into the knowledge base"},
        ],
        "verifier": [
            {"label": "Verify HANA cockpit", "prompt": "Verify HANA Cockpit shows healthy system status"},
            {"label": "Cross-validate", "prompt": "Cross-validate system health between browser and SQL data"},
        ],
        "monitoring": [
            {"label": "Container health", "prompt": "Check Docker container health status"},
            {"label": "HDB storage", "prompt": "Check HDB storage paths and usage"},
        ],
        "instance_monitor": [
            {"label": "Run diagnostics", "prompt": "Run a full diagnostic check on the HANA instance"},
            {"label": "Check processes", "prompt": "Check HANA process status on the instance"},
        ],
        "instance_backup": [
            {"label": "Create snapshot", "prompt": "Create a new VM snapshot of the HANA instance"},
            {"label": "List snapshots", "prompt": "List all GCP VM snapshots"},
        ],
        "instance_healing": [
            {"label": "List healing options", "prompt": "Show available healing scripts and their risk levels"},
            {"label": "Check healing status", "prompt": "Check the status of recent healing operations"},
        ],
    }

    quick_actions = dict(_DEFAULT_QUICK_ACTIONS)
    for sa in sub_agents:
        agent_id = getattr(sa, "name", "")
        # Match by keyword in agent_id
        for keyword, actions in _KEYWORD_QUICK_ACTIONS.items():
            if keyword in agent_id:
                quick_actions[agent_id] = actions
                break
        if agent_id not in quick_actions:
            # Generic fallback
            quick_actions[agent_id] = [
                {"label": "Status", "prompt": f"What is the current status of {agent_id.replace('_', ' ')}?"},
            ]

    return {
        "nodes": nodes,
        "edges": edges,
        "quick_actions": quick_actions,
    }


@app.get("/api/v1/agents/{agent_id}/decisions")
def get_agent_decisions(agent_id: str):
    """Agent decision history (filtered from certificates)."""
    decisions = [
        cert.model_dump()
        for cert in _certificates.values()
        if cert.created_by_agent == agent_id
    ]
    return {"agent_id": agent_id, "decisions": decisions}


# ──────────────────────────────────────────────
# RAG Query Endpoint
# ──────────────────────────────────────────────
@app.post("/api/v1/rag/query")
def query_rag(req: RAGQueryRequest):
    """Query RAG knowledge base."""
    result = rag_query(req.question)
    return result


# Frontend uses /api/v1/tools/rag — alias for rag/query
@app.post("/api/v1/tools/rag")
def query_rag_alias(req: RAGQueryRequest):
    """Query RAG knowledge base (frontend alias)."""
    return query_rag(req)


# ──────────────────────────────────────────────
# Configuration Endpoints
# ──────────────────────────────────────────────
@app.post("/api/v1/config/global-ini/check")
def validate_global_ini():
    """Validate global.ini entries via remote exec server."""
    sid = os.getenv("HANA_SID", os.getenv("GCP_TOOLKIT_HANA_SID", ""))
    ini_path = os.getenv(
        "GLOBAL_INI_PATH", f"/usr/sap/{sid}/SYS/global/hdb/custom/config/global.ini"
    )
    result = execute_remote_command(f"cat {ini_path}", admin_override=True)
    if result.get("status") != "success":
        return {"status": "error", "error_message": "Could not read global.ini"}
    content = result.get("stdout", "")
    req_str = os.getenv("GLOBAL_INI_REQUIRED_ENTRIES", "")
    if req_str:
        required_entries = {}
        for pair in req_str.split(","):
            if "=" in pair:
                k, v = pair.split("=", 1)
                required_entries[k.strip()] = v.strip()
    else:
        base = os.getenv("HANA_DATA_PATH", f"/hdb/{sid}")
        required_entries = {
            "basepath_databackup": f"{base}/backup/data",
            "basepath_logbackup": f"{base}/backup/log",
        }
    present = {k: v for k, v in required_entries.items() if k in content}
    missing = {k: v for k, v in required_entries.items() if k not in content}
    return {"status": "compliant" if not missing else "non_compliant", "present": present, "missing": missing}


# ──────────────────────────────────────────────
# System Health Quick Check
# ──────────────────────────────────────────────
@app.get("/api/v1/health")
def system_health():
    """Quick system health check."""
    try:
        conn = check_hana_connection()
        db_connected = conn.get("status") == "connected"
    except Exception:
        conn = {"status": "error", "message": "Connection check failed"}
        db_connected = False

    try:
        instance_nr = os.getenv("HANA_INSTANCE_NR", os.getenv("GCP_TOOLKIT_INSTANCE_NUMBER", ""))
        proc_result = execute_remote_command(f"sapcontrol -nr {instance_nr} -function GetProcessList", admin_override=True)
        processes = {"status": proc_result.get("status", "error"), "output": proc_result.get("stdout", "")}
    except Exception:
        processes = {"status": "error"}

    try:
        sid = os.getenv("HANA_SID", os.getenv("GCP_TOOLKIT_HANA_SID", ""))
        ini_path = os.getenv("GLOBAL_INI_PATH", f"/usr/sap/{sid}/SYS/global/hdb/custom/config/global.ini")
        ini_result = execute_remote_command(f"cat {ini_path}", admin_override=True)
        ini = {"status": "success" if ini_result.get("status") == "success" else "error"}
    except Exception:
        ini = {"status": "error"}

    sid = os.getenv("GCP_TOOLKIT_HANA_SID", os.getenv("HANA_SID", ""))

    return {
        "status": "healthy" if db_connected else "degraded",
        "database_connected": db_connected,
        "hana_connection": conn,
        "sapcontrol": processes,
        "global_ini": ini,
        "agents_registered": len(AGENT_DEFINITIONS),
        "timestamp": datetime.utcnow().isoformat(),
    }


_reconnect_status: Dict[str, Any] = {"in_progress": False, "result": None}
_reconnect_lock = threading.Lock()


def _reconnect_background():
    """Background thread that performs the actual reconnection attempt."""
    global _cached_metrics
    try:
        _get_connection(force_reconnect=True)
        conn = check_hana_connection()
        db_connected = conn.get("status") == "connected"
        with _metrics_lock:
            _cached_metrics = None
        with _reconnect_lock:
            _reconnect_status["result"] = {
                "status": "connected" if db_connected else "disconnected",
                "database_connected": db_connected,
                "details": conn,
                "timestamp": datetime.utcnow().isoformat(),
            }
            _reconnect_status["in_progress"] = False
    except Exception as e:
        with _reconnect_lock:
            _reconnect_status["result"] = {
                "status": "error",
                "database_connected": False,
                "details": {"error": str(e)},
                "timestamp": datetime.utcnow().isoformat(),
            }
            _reconnect_status["in_progress"] = False


@app.post("/api/v1/force-reconnect")
def force_reconnect():
    """Kick off a background reconnection attempt to the HANA database.
    Returns immediately; poll GET /api/v1/force-reconnect for the result."""
    with _reconnect_lock:
        if _reconnect_status["in_progress"]:
            return {"status": "in_progress", "message": "Reconnection already in progress"}
        _reconnect_status["in_progress"] = True
        _reconnect_status["result"] = None

    thread = threading.Thread(target=_reconnect_background, daemon=True)
    thread.start()

    return {"status": "in_progress", "message": "Reconnection started"}


@app.get("/api/v1/force-reconnect/auto")
def auto_reconnect_if_needed():
    """Auto-reconnect if DB is disconnected. Called by frontend on load.
    Unlike force-reconnect, this is idempotent and only acts when needed."""
    global _startup_reconnect_done

    # If already connected, return immediately
    with _metrics_lock:
        if _cached_metrics and _cached_metrics.get("database_connected"):
            return {"status": "already_connected", "database_connected": True}

    # Trigger reconnect only once per server lifetime until connected
    with _reconnect_lock:
        if _reconnect_status["in_progress"]:
            return {"status": "in_progress", "message": "Reconnection already in progress"}
        _reconnect_status["in_progress"] = True
        _reconnect_status["result"] = None

    thread = threading.Thread(target=_reconnect_background, daemon=True)
    thread.start()
    _startup_reconnect_done = True

    return {"status": "in_progress", "message": "Auto-reconnection started"}


@app.get("/api/v1/force-reconnect")
def force_reconnect_status():
    """Poll for the result of a force-reconnect attempt."""
    with _reconnect_lock:
        if _reconnect_status["in_progress"]:
            return {"status": "in_progress", "message": "Reconnection in progress"}
        if _reconnect_status["result"]:
            return _reconnect_status["result"]
    return {"status": "idle", "message": "No reconnection attempted"}


# ──────────────────────────────────────────────
# Agent Chat Interface (Google ADK Integration)
# ──────────────────────────────────────────────
_conversations: Dict[str, List[Dict[str, Any]]] = {}


@app.post("/api/v1/agent/chat")
def agent_chat(req: AgentChatRequest):
    """Chat with the HANA Sentinel agent using Google ADK."""
    conversation_id = req.conversation_id or str(uuid.uuid4())
    
    if conversation_id not in _conversations:
        _conversations[conversation_id] = []
    
    # Add user message to conversation
    _conversations[conversation_id].append({
        "role": "user",
        "content": req.message,
        "timestamp": datetime.utcnow().isoformat()
    })

    try:
        result = generate_agent_response(
            req.message,
            admin_mode=req.admin_mode,
            use_browser=req.use_browser,
            autonomous_browser=req.autonomous_browser,
            voice_mode=req.voice_mode,
        )
    except Exception as e:
        logger.exception(f"generate_agent_response failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

    response_text = result.get("response", "")
    sources = result.get("sources", [])
    browser_active = result.get("browser_active", False)
    
    # Add assistant response to conversation
    _conversations[conversation_id].append({
        "role": "assistant", 
        "content": response_text,
        "timestamp": datetime.utcnow().isoformat()
    })
    
    resp = {
        "conversation_id": conversation_id,
        "response": response_text,
        "sources": sources,
        "timestamp": datetime.utcnow().isoformat()
    }
    if browser_active:
        resp["browser_active"] = True
    return resp


class BrowseRequest(BaseModel):
    query: str


@app.post("/api/v1/agent/browse")
def agent_browse(req: BrowseRequest):
    """Browse SAP documentation for a given query."""
    result = _browse_and_answer(req.query)
    return {
        "response": result.get("response", ""),
        "sources": result.get("sources", []),
        "timestamp": datetime.utcnow().isoformat(),
    }


@app.get("/api/v1/agent/conversation/{conversation_id}")
def get_conversation(conversation_id: str):
    """Get full conversation history."""
    if conversation_id not in _conversations:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return {
        "conversation_id": conversation_id,
        "messages": _conversations[conversation_id]
    }


def _extract_command_with_llm(user_text: str, model: Optional[str] = None) -> Optional[str]:
    """Use configured LLM to classify intent and extract a shell command if appropriate."""
    try:
        from .aicore_client import get_aicore_client

        client = get_aicore_client()
        if not client.is_configured():
            logger.warning("LLM command extraction skipped — AI Core not configured")
            return None

        system_prompt = (
            "You are an expert Linux/SAP HANA administrator managing a LIVE production server. "
            "The user is an ops engineer talking to you via voice. They want LIVE system data, not definitions.\n\n"
            "First decide: is the user asking a THEORETICAL KNOWLEDGE QUESTION or wanting to CHECK the LIVE system?\n\n"
            "KNOWLEDGE QUESTIONS (return NO_COMMAND):\n"
            "  - Pure theory/concepts: 'what is HANA replication?', 'explain column store'\n"
            "  - SAP Note lookups: 'sap note 2222222'\n"
            "  - Best practices/architecture: 'how does HANA backup work?'\n\n"
            "LIVE SYSTEM CHECKS (return the shell command):\n"
            "  - Explicit: 'ls -ltr', 'df -h', 'run uptime'\n"
            "  - Questions about CURRENT state → these are commands, NOT knowledge:\n"
            "    'what is the server uptime' → uptime\n"
            "    'what is the uptime' → uptime\n"
            "    'how much disk space' → df -h\n"
            "    'how much memory is used' → free -h\n"
            "    'what processes are running' → ps aux\n"
            "    'is the server running' → uptime\n"
            "    'check cpu' → top -bn1 | head -20\n"
            "    'server status' → uptime\n"
            "  - System admin tasks: 'restart indexserver', 'list files in /hana/shared'\n\n"
            "IMPORTANT: When the user mentions uptime, disk, memory, cpu, process, load, " 
            "swap, space, running, status of a SERVER — they want the LIVE data, not a definition.\n\n"
            "HANA SQL queries: Use hdbsql with userstore key DEFAULT, e.g.:\n"
            "  hdbsql -U DEFAULT \"SELECT * FROM M_SERVICES\"\n"
            "  hdbsql -U DEFAULT \"SELECT * FROM M_SNAPSHOTS\"\n"
            "Never use placeholder <user> — always use -U DEFAULT.\n\n"
            "Rules:\n"
            "- If LIVE SYSTEM CHECK → return ONLY the raw shell command, no backticks, no explanation\n"
            "- If KNOWLEDGE QUESTION → return exactly: NO_COMMAND\n"
            "- When in doubt about system state questions, prefer running the command"
        )
        prompt = f"User message: {user_text.strip()}"

        llm_response = client.generate_text(
            prompt=prompt,
            system_prompt=system_prompt,
            temperature=0.0,
            max_tokens=120,
            model=model,
        )
        if not llm_response:
            logger.warning("LLM returned empty response for command extraction")
            return None

        cmd = llm_response.strip().splitlines()[0].strip()
        # Strip markdown backticks if the model wraps them
        if cmd.startswith("`") and cmd.endswith("`"):
            cmd = cmd[1:-1].strip()
        if cmd.startswith("```"):
            cmd = cmd.lstrip("`").rstrip("`").strip()

        if cmd.upper().startswith("NO_COMMAND"):
            return None

        logger.info(f"LLM extracted command: {cmd}")
        return cmd
    except Exception as exc:
        logger.error(f"LLM command extraction failed: {exc}")
        return None


def _extract_command_heuristic(message: str, msg_lower: str) -> str:
    """Best-effort command extraction for non-LLM fallback paths."""
    import re

    # 1. Strip conversational prefixes that wrap a real command
    prefix_patterns = [
        r"^(?:what\s+is|what's)\s+",           # "what is ls -ltr"
        r"^(?:can you|could you|please)\s+",     # "can you run df -h"
        r"^(?:i want to|i'd like to)\s+",        # "i want to see uptime"
        r"^(?:help me|try)\s+",                  # "try ls /tmp"
        r"^(?:show me|show)\s+",                 # "show me free -h"
    ]
    stripped = msg_lower
    for pat in prefix_patterns:
        stripped = re.sub(pat, "", stripped, count=1).strip()

    # 2. Strip action verbs that precede the actual command
    action_keywords = ["run ", "execute ", "exec ", "check ", "do "]
    for kw in action_keywords:
        if stripped.startswith(kw):
            stripped = stripped[len(kw):].strip()
            break

    # Map back to original casing using the offset in msg_lower
    offset = msg_lower.find(stripped)
    command = message[offset:].strip() if offset >= 0 else stripped

    # 3. Remove trailing filler phrases
    filler = ["in the server", "on the server", "on this machine",
              "for me", "please", "command"]
    for f in filler:
        command = re.sub(rf"\s*{re.escape(f)}\s*$", "", command, flags=re.IGNORECASE).strip()

    # 4. If result is still too long to be a real command, try to find a
    #    known shell command inside the text and return that + its args
    shell_commands = [
        "sapcontrol", "hdbsql", "hdbuserstore", "hdb ",
        "df ", "df\n", "free ", "free\n", "ps ", "ls ", "cat ",
        "uptime", "whoami", "hostname", "date", "uname",
        "top", "tail ", "head ", "grep ", "find ", "du ",
        "systemctl ", "journalctl ",
    ]
    if len(command.split()) > 10:
        for cmd in shell_commands:
            idx = msg_lower.find(cmd.strip())
            if idx >= 0:
                # Take from that command to end of message
                command = message[idx:].strip()
                break

    return command


def _answer_with_llm(question: str, model: Optional[str] = None) -> dict:
    """Answer a knowledge question using only the LLM (no web browsing)."""
    try:
        from .aicore_client import get_aicore_client

        client = get_aicore_client()
        if client.is_configured():
            diag_context = _get_diagnostic_context()
            system_prompt = (
                "You are an SAP HANA expert assistant. Answer the user's question concisely "
                "and accurately. If you are not sure about something, say so."
            )
            if diag_context:
                system_prompt += (
                    "\n\nRecent diagnostic history from this system:\n" + diag_context
                )
            answer = client.generate_text(
                prompt=question,
                system_prompt=system_prompt,
                temperature=0.3,
                max_tokens=1024,
                model=model,
            )
            if answer:
                return {"response": answer.strip(), "sources": []}
    except Exception as exc:
        logger.warning(f"LLM-only answer failed: {exc}")

    return {
        "response": "I couldn't retrieve an answer right now. Please try again or rephrase your question.",
        "sources": [],
    }


def _is_knowledge_question(msg_lower: str) -> bool:
    """Detect if the user message is a knowledge/documentation question."""
    import re

    # SAP Note pattern: "SAP Note 123456" or "note 123456" or "sap notes 2222222" or just "123456" (6-7 digit number)
    sap_note_pattern = r'\b(?:sap\s*)?notes?\s*\d{5,7}\b|\b\d{6,7}\b'
    if re.search(sap_note_pattern, msg_lower):
        return True

    # Questions ending with '?' are almost always knowledge questions
    if msg_lower.strip().endswith('?'):
        return True

    knowledge_patterns = [
        "what is ", "what are ", "what does ", "what's ",
        "how to ", "how do ", "how can ",
        "can i ", "can this ", "can you explain",
        "is it possible", "is there a way",
        "explain ", "describe ", "tell me about ",
        "difference between", "meaning of ",
        "why does ", "why is ", "why do ",
        "when should ", "when to ",
        "best practice", "recommend",
        "documentation", "sap note", "sap notes",
        "browse ", "search ", "look up ", "find info",
        "commands for", "command for", "clean", "cleanup", "housekeeping",
    ]
    return any(p in msg_lower for p in knowledge_patterns)


def _browse_and_answer(question: str, use_autonomous_browser: bool = False) -> dict:
    """Browse web and generate an LLM-powered answer.

    Args:
        question: The question to answer
        use_autonomous_browser: If True, use Playwright browser with screenshots (Manus-style)

    Returns:
        {"response": str, "sources": list[dict], "use_playwright": bool}
    """
    sources = []
    context = ""

    # Try browser-use agent (headless, no GUI)
    if use_autonomous_browser:
        try:
            from .agents.browser_agent import BrowserUseAgent
            browser_agent = BrowserUseAgent(headless=False)
            logger.info(f"Using browser-use agent for: {question[:50]}...")

            # SAP knowledge sources to search (ordered by relevance)
            sap_sources = [
                ("https://userapps.support.sap.com/sap/support/knowledge/en", "SAP Knowledge Base Articles (KBA)"),
                ("https://me.sap.com/notes", "SAP Notes"),
                ("https://help.sap.com/docs/SAP_HANA_PLATFORM", "SAP HANA Help Portal"),
                ("https://community.sap.com/t5/technology-blogs-by-sap/bg-p/technology-blog-sap", "SAP Community Blogs"),
                ("https://community.sap.com/t5/technology-q-a/qa-p/technology-questions", "SAP Community Q&A"),
                ("https://help.sap.com/docs/SAP_HANA_PLATFORM/009e68bc5f3c440cb31823a3ec4bb95b", "SAP HANA Administration Guide"),
                ("https://help.sap.com/docs/SAP_HANA_PLATFORM/4fe29514fd584807ac9f2a04f6754767", "SAP HANA Troubleshooting Guide"),
                ("https://help.sap.com/docs/SAP_HANA_PLATFORM/6b94445c94ae495c83a19646e7c3fd56", "SAP HANA SQL Reference"),
            ]

            source_instructions = "\n".join(
                f"  {i+1}. {name}: {url}" for i, (url, name) in enumerate(sap_sources)
            )
            browser_task = (
                f"Search for information about: {question}\n\n"
                f"Search these SAP knowledge sources in order. Stop once you find relevant content:\n"
                f"{source_instructions}\n"
                f"  {len(sap_sources)+1}. If none of the above have results, search the web broadly."
            )
            result = browser_agent.run_task(browser_task)
            if result and "failed" not in result.lower():
                context = result
                for url, title in sap_sources:
                    sources.append({
                        "url": url,
                        "title": title,
                        "status": "searched",
                        "source": "browser_use",
                    })
                logger.info("Browser-use agent returned results (SAP KBs + web)")
        except ImportError:
            logger.warning("browser-use library not installed, falling back to web scraping")
        except Exception as exc:
            logger.warning(f"Browser-use agent failed: {exc}, falling back to web scraping")

    # Fall back to web scraping if autonomous browser didn't work
    if not context:
        from .tools.web_browse_tools import browse_for_answer

        # Enable full web search (Google, DuckDuckGo, etc.)
        browse_result = browse_for_answer(question, use_web_search=True)
        sources = browse_result.get("sources", [])
        context = browse_result.get("answer_context", "")

    # Built-in knowledge for common HANA topics when browsing fails
    q_lower = question.lower()
    builtin_context = ""
    if not context and ("clean" in q_lower or "housekeep" in q_lower or "usage" in q_lower):
        builtin_context = _get_hana_cleaning_commands()

    if not context and not builtin_context:
        return {
            "response": (
                "I searched SAP documentation but couldn't find relevant pages for your question. "
                "Try rephrasing or check [SAP Help Portal](https://help.sap.com) directly."
            ),
            "sources": sources,
        }

    final_context = context or builtin_context

    # Use LLM to synthesize an answer from the browsed content
    try:
        from .aicore_client import get_aicore_client

        client = get_aicore_client()
        if client.is_configured():
            system_prompt = (
                "You are an SAP HANA expert assistant. Answer the user's question based ONLY on "
                "the documentation excerpts provided below. Cite the source URL when referencing "
                "specific information. If the documentation doesn't fully answer the question, "
                "say so and suggest where to look further.\n\n"
                f"Documentation excerpts:\n{final_context}"
            )
            answer = client.generate_text(
                prompt=question,
                system_prompt=system_prompt,
                temperature=0.3,
                max_tokens=1024,
            )
            if answer:
                return {"response": answer.strip(), "sources": sources}
    except Exception as exc:
        logger.warning(f"LLM answer synthesis failed: {exc}")

    # Fallback: return raw context snippets or built-in content
    if sources:
        snippets = "\n\n".join(
            f"**{s['title']}** — [{s['url']}]({s['url']})"
            for s in sources if s.get("title")
        )
        return {
            "response": f"Here's what I found in SAP documentation:\n\n{snippets}",
            "sources": sources,
        }
    elif builtin_context:
        return {
            "response": builtin_context,
            "sources": [{"url": "built-in", "title": "HANA Sentinel Knowledge Base", "status": "ok"}],
        }
    return {
        "response": "No relevant information found.",
        "sources": [],
    }


def _get_hana_cleaning_commands() -> str:
    """Return built-in HANA cleaning/housekeeping commands reference."""
    return """## SAP HANA Cleaning & Housekeeping Commands

### 1. Trace File Cleanup
```sql
-- Remove old trace files (keeps last 7 days)
ALTER SYSTEM REMOVE TRACES OLDER THAN 7 DAYS;

-- Remove specific trace type
ALTER SYSTEM REMOVE TRACES ('INDEXSERVER', 'ALERT');
```

### 2. Backup Catalog Cleanup
```sql
-- Delete backup catalog entries older than specified timestamp
BACKUP CATALOG DELETE ALL BEFORE TIMESTAMP '2024-01-01 00:00:00';

-- Delete backup catalog for specific backup type
BACKUP CATALOG DELETE COMPLETE DATA BACKUP BEFORE TIMESTAMP '2024-01-01 00:00:00';
```

### 3. Log Segment Cleanup
```sql
-- Free log segments after backup
ALTER SYSTEM RECLAIM LOG;
```

### 4. Statistics Cleanup
```sql
-- Clear old statistics data
ALTER SYSTEM CLEAR STATISTICS ALERTS;

-- Remove old expensive statement traces
ALTER SYSTEM CLEAR SQL PLAN CACHE;
```

### 5. Temporary Tables Cleanup
```sql
-- Remove orphaned temporary tables
CALL SYS.CLEANUP_ORPHANED_TEMPS();
```

### 6. Memory Cleanup
```sql
-- Release unused memory
ALTER SYSTEM RECLAIM DATAVOLUME;

-- Clear statement memory
ALTER SYSTEM CLEAR SQL PLAN CACHE;
```

### 7. Audit Log Cleanup
```sql
-- Delete audit log entries older than retention period
DELETE FROM SYS.AUDIT_LOG WHERE TIMESTAMP < ADD_DAYS(CURRENT_TIMESTAMP, -90);
```

### 8. Shell Commands for File Cleanup
```bash
# Clean old trace files from filesystem
find /hana/shared/<SID>/HDB<NR>/<hostname>/trace -name "*.trc" -mtime +7 -delete

# Clean old backup files (if stored locally)
find /hana/backup -name "*.bak" -mtime +30 -delete

# Check disk usage
df -h /hana/data /hana/log /hana/shared
```

### 9. Housekeeping Task Scheduling
```sql
-- Enable automatic trace cleanup
ALTER SYSTEM ALTER CONFIGURATION ('global.ini', 'SYSTEM')
SET ('persistence', 'log_mode') = 'overwrite' WITH RECONFIGURE;

-- Set trace file retention
ALTER SYSTEM ALTER CONFIGURATION ('global.ini', 'SYSTEM')
SET ('trace', 'maxfiles') = '20' WITH RECONFIGURE;
```

**Important:** Always ensure you have valid backups before running cleanup commands. Some commands may require SYSTEM privilege.
"""


def _summarize_output_for_voice(command: str, output: str, model: Optional[str] = None) -> str:
    """Use the LLM to create a brief spoken-word summary of command output."""
    try:
        from .aicore_client import get_aicore_client
        client = get_aicore_client()
        if not client.is_configured():
            return None
        system_prompt = (
            "You are a voice assistant summarizing Linux/SAP HANA command output for a spoken response. "
            "Be BRIEF (2-4 sentences max). Report key numbers and status. "
            "Do NOT say 'the output shows' or 'the command returned'. "
            "Speak naturally as if reporting live system status to an engineer. "
            "Example: 'The server has been up for 45 days. Load average is 0.25. Two users are logged in.'"
        )
        prompt = f"Command: {command}\nOutput:\n{output[:2000]}\n\nSummarize this for a spoken voice response:"
        summary = client.generate_text(
            prompt=prompt,
            system_prompt=system_prompt,
            temperature=0.2,
            max_tokens=200,
            model=model,
        )
        if summary and summary.strip():
            return summary.strip()
    except Exception as exc:
        logger.warning(f"Voice summary failed: {exc}")
    return None


def generate_agent_response(message: str, admin_mode: bool = False, use_browser: bool = False, autonomous_browser: bool = False, voice_mode: bool = False) -> dict:
    """Generate agent response based on user message.
    Supports direct command execution and knowledge browsing.

    Args:
        message: User's message
        admin_mode: If True, allow unrestricted command execution
        use_browser: If True, always browse web for answers
        autonomous_browser: If True, use browser-use agent for autonomous browsing (like Manus)
        voice_mode: If True, return voice-friendly summaries instead of markdown

    Returns:
        {"response": str, "sources": list} — sources is empty for non-browse responses
    """
    from .tools.http_command_executor import get_http_executor, execute_hana_command

    # Voice mode uses Sonnet model for higher quality spoken responses
    _voice_model = os.getenv("VOICE_LLM_MODEL", "anthropic--claude-4.6-sonnet") if voice_mode else None

    # Inject diagnostic history context into the message for the LLM
    diag_context = _get_diagnostic_context()
    original_message = message
    if diag_context:
        message = f"{message}\n\n[System context — recent diagnostics]\n{diag_context}"

    msg_lower = original_message.lower()

    # Check for explicit command execution requests
    command_keywords = ["run ", "execute ", "exec ", "show me ", "check "]
    # Base command names (no trailing spaces) — matched with word-boundary logic
    shell_commands = ["uptime", "df", "free", "top", "ps", "cat", "ls", "du",
                      "whoami", "hostname", "date", "uname", "grep", "find", "tail",
                      "head", "sapcontrol", "hdb", "hdbsql", "hdbuserstore", "echo",
                      "pwd", "id", "mount", "lsblk", "systemctl", "journalctl"]

    is_command_request = any(kw in msg_lower for kw in command_keywords)

    def _starts_with_command(text, cmd):
        """Check if text starts with cmd as a whole word."""
        return text == cmd or text.startswith(cmd + " ") or text.startswith(cmd + "\n")

    has_shell_command = any(_starts_with_command(msg_lower.strip(), cmd) for cmd in shell_commands)

    # Detect if the question mentions a system-checkable concept even if phrased as a question
    system_check_keywords = [
        "uptime", "disk", "memory", "cpu", "process", "load", "usage",
        "running", "disk space", "free space", "swap", "filesystem",
        "mount", "partition", "service", "port", "network", "connection",
        "backup status", "hana status", "instance", "restart",
        "snapshot",
    ]
    mentions_system_check = any(kw in msg_lower for kw in system_check_keywords)

    def _resp(text, sources=None):
        return {"response": text, "sources": sources or []}

    # ── Read-only safety filter ──────────────────────────────
    # Block destructive/write commands regardless of admin_mode.
    # Only read-only inspection commands are allowed via voice/chat.
    _DANGEROUS_PATTERNS = [
        r'\brm\b', r'\brmdir\b', r'\bunlink\b',
        r'\bmkdir\b', r'\btouch\b', r'\bchmod\b', r'\bchown\b', r'\bchgrp\b',
        r'\bmv\b', r'\bcp\b',
        r'\bdd\b', r'\bmkfs\b', r'\bfdisk\b', r'\bparted\b',
        r'\bkill\b', r'\bkillall\b', r'\bpkill\b',
        r'\breboot\b', r'\bshutdown\b', r'\bpoweroff\b', r'\bhalt\b', r'\binit\b',
        r'\bapt\b', r'\byum\b', r'\bdnf\b', r'\bzypper\b', r'\bpip\b',
        r'\bcurl\b.*-[dXP]', r'\bwget\b',  # curl with POST/PUT/DELETE, wget downloads
        r'\bsed\b.*-i', r'\btruncate\b',  # in-place sed edits
        r'\btee\b', r'(?<![<\w])\s*>', r'>>',  # shell redirections (but not <user> or SQL >)
        r'\bDROP\b', r'\bDELETE\b', r'\bTRUNCATE\b', r'\bALTER\b', r'\bINSERT\b', r'\bUPDATE\b', r'\bCREATE\b',
        r'\bHDB\s+stop\b', r'\bHDB\s+kill\b',
        r'\bStopSystem\b', r'\bStopService\b', r'\bRestartService\b', r'\bRestartSystem\b',
    ]

    def _is_read_only(cmd: str) -> bool:
        """Return True if the command is safe (read-only)."""
        import re as _re
        # hdbsql with SELECT-only queries is always safe
        if cmd.strip().startswith("hdbsql"):
            has_select = _re.search(r'\bSELECT\b', cmd, _re.IGNORECASE)
            _dangerous_sql = [r'\bDROP\b', r'\bDELETE\b', r'\bTRUNCATE\b', r'\bALTER\b',
                              r'\bINSERT\b', r'\bUPDATE\b', r'\bCREATE\b', r'\bGRANT\b', r'\bREVOKE\b']
            has_dangerous = any(_re.search(p, cmd, _re.IGNORECASE) for p in _dangerous_sql)
            if has_select and not has_dangerous:
                return True
        for pat in _DANGEROUS_PATTERNS:
            if _re.search(pat, cmd, _re.IGNORECASE):
                return False
        return True

    def _is_remote_forbidden(result: dict) -> bool:
        """Check if executor result is a remote server 403/forbidden."""
        err = (result.get("error", "") or "").lower()
        return "403" in err or "not allowed" in err or "forbidden" in err

    def _reject_write(cmd: str):
        """Return a rejection response for blocked commands and queue for approval."""
        # Fire-and-forget: queue the command for approval with enrichment
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                asyncio.ensure_future(_queue_restricted_command(cmd, source="chat", user_request=original_message))
            else:
                import threading
                _orig = original_message
                threading.Thread(
                    target=lambda: asyncio.run(_queue_restricted_command(cmd, source="chat", user_request=_orig)),
                    daemon=True,
                ).start()
        except Exception:
            # Best-effort — don't break the chat response
            import threading
            _orig = original_message
            threading.Thread(
                target=lambda: asyncio.run(_queue_restricted_command(cmd, source="chat", user_request=_orig)),
                daemon=True,
            ).start()

        if voice_mode:
            return _resp(f"Sorry, the command {cmd.split()[0]} is blocked because it can modify the system. It has been queued for admin approval in the Healing Approvals page.")
        return _resp(
            f"**Blocked:** `{cmd}`\n\n"
            "This command is restricted and cannot be executed directly. "
            "It has been **queued for approval** in the [Healing Approvals](/instance-approvals) page "
            "with AI analysis and SAP documentation references. "
            "An administrator can review and approve it there."
        )

    # ── Autonomous browser short-circuit ─────────────────────
    # When autonomous browser is ON for a knowledge query, the WebSocket
    # /ws/browser-stream handles all Playwright execution and streaming.
    # Return a placeholder so the frontend knows to wait for the WS result.
    if autonomous_browser and not has_shell_command and not is_command_request and not mentions_system_check:
        return {
            "response": "Browsing the web for an answer...",
            "sources": [],
            "browser_active": True,
        }

    # Dynamic instance number for sapcontrol commands
    _inst_nr = os.getenv("HANA_INSTANCE_NR", os.getenv("GCP_TOOLKIT_INSTANCE_NUMBER", "02"))

    # ── Agent-aware intent routing ───────────────────────────
    # Routes known agent prompts to proper HANA SQL queries or combined
    # checks BEFORE the crude keyword→shell-command fallback.
    # This ensures "backup status" queries M_BACKUP_CATALOG instead of
    # running `ls /hana/backup/`, "top queries" queries M_SQL_PLAN_CACHE
    # instead of running `uptime`, etc.
    _AGENT_INTENT_ROUTES = [
        # ── Supervisor (checked first — prompts overlap with other agents) ──
        {
            "keywords": ["status summary", "all agents"],
            "type": "multi",
            "commands": [
                {"type": "api", "endpoint": "/hana/services", "label": "HANA Services"},
                {"type": "api", "endpoint": "/hana/metrics", "label": "HANA Metrics"},
                {"type": "api", "endpoint": "/operational/backup-status", "label": "Backup Status"},
                {"type": "api", "endpoint": "/hana/alerts", "label": "Alerts"},
            ],
            "label": "Agent Status Summary",
        },
        {
            "keywords": ["full diagnostic", "full diagnostics", "diagnostic check"],
            "type": "api",
            "endpoint": "/diagnostics",
            "label": "Full System Diagnostics",
        },
        # ── Backup Agent ─────────────────────────────────────
        {
            "keywords": ["backup status", "last successful backup", "last backup"],
            "type": "api",
            "endpoint": "/operational/backup-status",
            "label": "HANA Backup Status",
        },
        {
            "keywords": ["list backups", "list all recent", "recent hana backups", "recent backups"],
            "type": "hana_sql",
            "query": (
                "SELECT TOP 20 BACKUP_ID, ENTRY_TYPE_NAME, STATE_NAME, "
                "SYS_START_TIME, SYS_END_TIME, COMMENT, MESSAGE "
                "FROM M_BACKUP_CATALOG "
                "ORDER BY SYS_END_TIME DESC"
            ),
            "label": "Recent HANA Backups",
        },
        # ── Health Agent ──────────────────────────────────────
        {
            "keywords": ["health check", "run a health check", "system health"],
            "type": "api",
            "endpoint": "/observability/system-health",
            "label": "System Health Check",
        },
        {
            "keywords": ["check services", "service status", "hana service"],
            "type": "api",
            "endpoint": "/hana/services",
            "label": "HANA Service Status",
        },
        {
            "keywords": ["memory analysis", "memory usage", "analyze memory", "analyze current memory"],
            "type": "api",
            "endpoint": "/observability/resource-utilization",
            "label": "Memory & Resource Utilization",
        },
        # ── SQL Tuning Agent ──────────────────────────────────
        {
            "keywords": ["top queries", "expensive queries", "expensive sql", "top expensive"],
            "type": "api",
            "endpoint": "/hana/expensive-queries",
            "label": "Top Expensive SQL Queries",
        },
        {
            "keywords": ["index suggestion", "index optimization", "index opportunities"],
            "type": "multi",
            "commands": [
                {
                    "type": "api",
                    "endpoint": "/hana/expensive-queries?top_n=20",
                    "label": "Slow Queries",
                },
                {
                    "type": "hana_sql",
                    "query": (
                        "SELECT SCHEMA_NAME, TABLE_NAME, INDEX_NAME, INDEX_TYPE, CONSTRAINT "
                        "FROM INDEXES "
                        "WHERE SCHEMA_NAME NOT LIKE '_SYS%' "
                        "ORDER BY SCHEMA_NAME, TABLE_NAME"
                    ),
                    "label": "Existing Indexes",
                },
            ],
            "label": "Index Analysis",
        },
        {
            "keywords": ["active transaction", "running transaction"],
            "type": "api",
            "endpoint": "/hana/transactions",
            "label": "Active Transactions",
        },
        {
            "keywords": ["blocking", "blocked", "lock wait"],
            "type": "api",
            "endpoint": "/hana/blocking",
            "label": "Blocked Transactions",
        },
        # ── Capacity Agent ────────────────────────────────────
        {
            "keywords": ["disk usage", "disk capacity", "capacity forecast"],
            "type": "api",
            "endpoint": "/capacity/growth-analysis",
            "label": "Disk Usage & Capacity",
        },
        {
            "keywords": ["growth trend", "data growth", "growth for the last"],
            "type": "api",
            "endpoint": "/capacity/growth-analysis",
            "label": "Growth Analysis",
        },
        # ── Recovery Agent ────────────────────────────────────
        {
            "keywords": ["recovery readiness", "disaster recovery", "recovery points"],
            "type": "hana_sql",
            "query": (
                "SELECT TOP 5 BACKUP_ID, ENTRY_TYPE_NAME, STATE_NAME, "
                "SYS_START_TIME, SYS_END_TIME, MESSAGE "
                "FROM M_BACKUP_CATALOG "
                "WHERE ENTRY_TYPE_NAME = 'complete data backup' AND STATE_NAME = 'successful' "
                "ORDER BY SYS_END_TIME DESC"
            ),
            "label": "Recovery Points (Latest Successful Backups)",
        },
        {
            "keywords": ["list snapshots", "available snapshots", "show all available snapshots"],
            "type": "hana_sql",
            "query": (
                "SELECT TOP 20 BACKUP_ID, ENTRY_TYPE_NAME, STATE_NAME, "
                "SYS_START_TIME, SYS_END_TIME, COMMENT "
                "FROM M_BACKUP_CATALOG "
                "WHERE ENTRY_TYPE_NAME LIKE '%snap%' OR ENTRY_TYPE_NAME LIKE '%data%' "
                "ORDER BY SYS_END_TIME DESC"
            ),
            "label": "Available Snapshots & Data Backups",
        },
        # ── Browser Agent (search patterns) ───────────────────
        {
            "keywords": ["search sap notes", "sap notes for"],
            "type": "browse",
            "label": "SAP Notes Search",
        },
        {
            "keywords": ["find docs", "find sap documentation", "sap documentation"],
            "type": "browse",
            "label": "SAP Documentation Search",
        },
        # ── Alerts ────────────────────────────────────────────
        {
            "keywords": ["alert", "database alert", "hana alert"],
            "type": "api",
            "endpoint": "/hana/alerts",
            "label": "HANA Alerts",
        },
        # ── RAG / Knowledge Base ──────────────────────────────
        {
            "keywords": ["search knowledge", "knowledge base", "search kb", "rag query", "search the knowledge base"],
            "type": "rag",
            "label": "Knowledge Base Search",
        },
        # ── Version / Info ────────────────────────────────────
        {
            "keywords": ["version", "hana version", "database version"],
            "type": "api",
            "endpoint": "/operational/version-info",
            "label": "HANA Version & Configuration",
        },
    ]

    def _execute_intent_route(route, voice_mode_flag=False):
        """Execute an agent intent route — API endpoint, HANA SQL, shell, browse, or multi-step."""
        import requests as _requests
        from .tools.hana_tools import query_hana as _query_hana, _REMOTE_EXEC_URL, _remote_headers

        if route["type"] == "api":
            # Call a dedicated remote_exec_server_v2 endpoint directly
            endpoint = route["endpoint"]
            label = route.get("label", endpoint)
            try:
                url = f"{_REMOTE_EXEC_URL}{endpoint}"
                resp = _requests.get(url, headers=_remote_headers(), timeout=60)
                if resp.status_code == 200:
                    data = resp.json()
                    return _resp(f"**{label}**\n\n```json\n{json.dumps(data, indent=2, default=str)}\n```")
                else:
                    return _resp(f"**{label}** — Error: HTTP {resp.status_code}: {resp.text[:300]}")
            except _requests.exceptions.ConnectionError:
                return _resp(f"**{label}** — Error: Cannot reach remote server at {_REMOTE_EXEC_URL}")
            except Exception as e:
                return _resp(f"**{label}** — Error: {str(e)}")

        elif route["type"] == "hana_sql":
            result = _query_hana(route["query"])
            label = route.get("label", "Query Result")
            if result.get("status") == "success":
                rows = result.get("rows", [])
                if not rows:
                    return _resp(f"**{label}**\n\nNo results returned.")
                # Format rows as markdown table
                if isinstance(rows[0], dict):
                    headers = list(rows[0].keys())
                    table_lines = ["| " + " | ".join(str(h) for h in headers) + " |"]
                    table_lines.append("| " + " | ".join("---" for _ in headers) + " |")
                    for row in rows:
                        table_lines.append("| " + " | ".join(str(row.get(h, "")) for h in headers) + " |")
                    table = "\n".join(table_lines)
                else:
                    table = "```\n" + "\n".join(str(r) for r in rows) + "\n```"
                return _resp(f"**{label}**\n\n{table}")
            else:
                err = result.get("error_message", "Unknown error")
                return _resp(f"**{label}** — Error: {err}")

        elif route["type"] == "shell":
            from .tools.http_command_executor import get_http_executor as _get_executor
            ex = _get_executor()
            if not ex.is_configured():
                return _resp(f"**{route.get('label', 'Shell')}** — Error: Remote exec server not configured.")
            res = ex.execute_command(route["command"], timeout=60, admin_override=True)
            label = route.get("label", route["command"])
            output = res.get("output", "").strip()
            if res.get("status") == "success" or res.get("exit_code") == 0:
                return _resp(f"**{label}**\n```\n{output or '(no output)'}\n```")
            error = res.get("error", "") or output
            return _resp(f"**{label}** — Error:\n```\n{error}\n```")

        elif route["type"] == "browse":
            # Delegate to the browser/knowledge pipeline
            label = route.get("label", "Browser Search")
            try:
                browse_result = _browse_and_answer(original_message, use_autonomous_browser=False)
                if browse_result.get("response"):
                    return _resp(f"**{label}**\n\n{browse_result['response']}", browse_result.get("sources"))
            except Exception as exc:
                logger.warning(f"Browse route failed for {label}: {exc}")
            return _resp(f"**{label}** — Could not retrieve results. Try rephrasing your question.")

        elif route["type"] == "rag":
            label = route.get("label", "Knowledge Base")
            result = rag_query(original_message)
            if result.get("status") == "success" and result.get("sources"):
                sources_list = ", ".join(os.path.basename(s) for s in result["sources"])
                return _resp(
                    f"**{label}**\n\n{result['answer']}\n\n*Sources: {sources_list}*"
                )
            elif result.get("status") == "success":
                return _resp(f"**{label}**\n\n{result.get('answer', 'No matching documents found.')}")
            else:
                return _resp(f"**{label}** — {result.get('error_message', 'Knowledge base search failed.')}")

        elif route["type"] == "multi":
            parts = []
            for sub_cmd in route.get("commands", []):
                sub_result = _execute_intent_route(sub_cmd, voice_mode_flag)
                if sub_result:
                    parts.append(sub_result["response"])
            combined = "\n\n---\n\n".join(parts) if parts else "No results."
            top_label = route.get("label", "Results")
            return _resp(f"## {top_label}\n\n{combined}")

        return None

    # Try to match the message against known agent intents
    _matched_intent = None
    for _route in _AGENT_INTENT_ROUTES:
        for _kw in _route["keywords"]:
            if _kw in msg_lower:
                _matched_intent = _route
                break
        if _matched_intent:
            break

    if _matched_intent:
        _intent_result = _execute_intent_route(_matched_intent, voice_mode)
        if _intent_result:
            logger.info(f"Agent intent routed: '{_matched_intent.get('label')}' for message: {original_message[:80]}")
            return _intent_result

    # In admin mode, let the LLM decide first — it can distinguish
    # "what is the server uptime?" (command) from "what is HANA replication?" (knowledge)
    if admin_mode:
        # Let the LLM decide if this is a command or a knowledge question
        command = _extract_command_with_llm(original_message, model=_voice_model)

        if not command and mentions_system_check:
            # LLM said NO_COMMAND but user mentioned system keywords like uptime/disk/memory
            # Fall back to a direct command mapping — they almost certainly want live data
            _system_keyword_commands = {
                "uptime": "uptime",
                "disk": "df -h",
                "disk space": "df -h",
                "free space": "df -h",
                "memory": "free -h",
                "swap": "free -h",
                "cpu": "top -bn1 | head -20",
                "load": "uptime",
                "process": "ps aux --sort=-%mem | head -20",
                "running": "uptime",
                "filesystem": "df -h",
                "mount": "mount | grep -v cgroup",
                "partition": "df -h",
                "port": "ss -tlnp",
                "network": "ss -tlnp",
                "connection": "ss -tlnp",
                "hana status": f"sapcontrol -nr {_inst_nr} -function GetProcessList",
                "instance": f"sapcontrol -nr {_inst_nr} -function GetProcessList",
                "backup status": f"sapcontrol -nr {_inst_nr} -function GetProcessList",
                "usage": "df -h; free -h",
                "service": f"sapcontrol -nr {_inst_nr} -function GetProcessList",
                "snapshot": f"sapcontrol -nr {_inst_nr} -function GetProcessList",
            }
            for kw, cmd in _system_keyword_commands.items():
                if kw in msg_lower:
                    command = cmd
                    logger.info(f"System keyword fallback: '{kw}' → {cmd}")
                    break

        if not command:
            # Truly a knowledge question — try RAG first, then browse, then LLM
            rag_result = rag_query(message)
            if rag_result.get("status") == "success" and rag_result.get("sources"):
                sources_list = ", ".join(os.path.basename(s) for s in rag_result["sources"])
                return _resp(f"{rag_result['answer']}\n\n*Sources: {sources_list}*")
            try:
                browse_answer = _browse_and_answer(message, use_autonomous_browser=False)
                if browse_answer.get("response") and "couldn't find" not in browse_answer.get("response", ""):
                    return browse_answer
            except Exception as exc:
                logger.warning(f"Browse failed in admin mode fallback: {exc}")
            return _answer_with_llm(message, model=_voice_model)

        executor = get_http_executor()
        if not executor.is_configured():
            return _resp("Error: Remote execution server not configured. Check REMOTE_EXEC_URL and REMOTE_EXEC_API_KEY in .env")

        if not _is_read_only(command):
            return _reject_write(command)

        result = executor.execute_command(command, timeout=60, admin_override=True)

        if result.get("status") == "success" or result.get("exit_code") == 0:
            output = result.get("output", "").strip()
            if output:
                if voice_mode:
                    summary = _summarize_output_for_voice(command, output, model=_voice_model)
                    if summary:
                        return _resp(summary)
                    return _resp(f"Ran {command}. Result: {output[:500]}")
                return _resp(f"**Admin Command:** `{command}`\n\n**Output:**\n```\n{output}\n```")
            msg = f"Command {command} executed successfully with no output." if voice_mode else f"**Admin Command:** `{command}`\n\nCommand executed successfully (no output)."
            return _resp(msg)

        error = result.get("error", "") or result.get("output", "")
        if _is_remote_forbidden(result):
            return _reject_write(command)
        if voice_mode:
            return _resp(f"The command {command} failed. Error: {error[:300]}")
        return _resp(f"**Admin Command:** `{command}`\n\n**Error:**\n```\n{error}\n```")

    # Non-admin mode: check for knowledge questions FIRST
    # This ensures "SAP Note 222221" goes to browser, not shell
    if _is_knowledge_question(msg_lower) and not has_shell_command and not mentions_system_check:
        # Try RAG first, then browser, then LLM
        rag_result = rag_query(message)
        if rag_result.get("status") == "success" and rag_result.get("sources"):
            sources_list = ", ".join(os.path.basename(s) for s in rag_result["sources"])
            return _resp(f"{rag_result['answer']}\n\n*Sources: {sources_list}*")
        try:
            return _browse_and_answer(message, use_autonomous_browser=False)
        except Exception as exc:
            logger.warning(f"Browse failed for knowledge question: {exc}")
            return _answer_with_llm(message, model=_voice_model)

    # System check questions (e.g. "what is the server uptime") — map to commands
    # Also handles "check ..." requests that mention system keywords (is_command_request may be True)
    if mentions_system_check and not has_shell_command:
        _system_keyword_commands = {
            "uptime": "uptime",
            "disk": "df -h",
            "disk space": "df -h",
            "free space": "df -h",
            "memory": "free -h",
            "swap": "free -h",
            "cpu": "top -bn1 | head -20",
            "load": "uptime",
            "process": "ps aux --sort=-%mem | head -20",
            "running": "uptime",
            "filesystem": "df -h",
            "mount": "mount | grep -v cgroup",
            "partition": "df -h",
            "port": "ss -tlnp",
            "network": "ss -tlnp",
            "connection": "ss -tlnp",
            "hana status": f"sapcontrol -nr {_inst_nr} -function GetProcessList",
            "instance": f"sapcontrol -nr {_inst_nr} -function GetProcessList",
            "backup status": f"sapcontrol -nr {_inst_nr} -function GetProcessList",
            "usage": "df -h; free -h",
            "service": f"sapcontrol -nr {_inst_nr} -function GetProcessList",
            "restart": "uptime",
            "snapshot": f"sapcontrol -nr {_inst_nr} -function GetProcessList",
        }
        sys_command = None
        for kw, cmd in _system_keyword_commands.items():
            if kw in msg_lower:
                sys_command = cmd
                logger.info(f"Non-admin system keyword: '{kw}' → {cmd}")
                break
        if not sys_command:
            sys_command = _extract_command_with_llm(original_message, model=_voice_model)
        if sys_command:
            if not _is_read_only(sys_command):
                return _reject_write(sys_command)
            executor = get_http_executor()
            if executor.is_configured():
                result = executor.execute_command(sys_command, timeout=60, admin_override=True)
                if result.get("status") == "success" or result.get("exit_code") == 0:
                    output = result.get("output", "").strip()
                    if output:
                        if voice_mode:
                            summary = _summarize_output_for_voice(sys_command, output, model=_voice_model)
                            if summary:
                                return _resp(summary)
                            return _resp(f"Ran {sys_command}. Result: {output[:500]}")
                        return _resp(f"**Command:** `{sys_command}`\n\n**Output:**\n```\n{output}\n```")
                    msg = f"Command {sys_command} ran with no output." if voice_mode else f"**Command:** `{sys_command}`\n\nCommand executed successfully (no output)."
                    return _resp(msg)
                else:
                    error = result.get("error", "") or result.get("output", "")
                    if _is_remote_forbidden(result):
                        return _reject_write(sys_command)
                    if voice_mode:
                        return _resp(f"The command {sys_command} failed. Error: {error[:300]}")
                    return _resp(f"**Command:** `{sys_command}`\n\n**Error:**\n```\n{error}\n```")

    if is_command_request or has_shell_command:
        command = _extract_command_heuristic(original_message, msg_lower)

        # Validate the heuristic produced a real command (starts with a known binary)
        _known_binaries = [
            "sapcontrol", "hdbsql", "hdbuserstore", "hdb",
            "df", "free", "ps", "ls", "cat", "uptime", "whoami", "hostname",
            "date", "uname", "top", "tail", "head", "grep", "find", "du",
            "systemctl", "journalctl", "echo", "pwd", "id", "mount", "lsblk",
            "ss", "wc",
        ]
        cmd_first_word = command.split()[0].lower() if command.strip() else ""
        if cmd_first_word not in _known_binaries:
            # Not a recognisable shell command — fall through to LLM answer
            logger.info(f"Heuristic produced non-command '{command[:60]}', falling through to LLM")
        else:

            if not _is_read_only(command):
                return _reject_write(command)

            # Execute the command
            executor = get_http_executor()
            if not executor.is_configured():
                return _resp("Error: Remote execution server not configured. Check REMOTE_EXEC_URL and REMOTE_EXEC_API_KEY in .env")

            # Determine if it's a HANA command or regular shell command
            hana_commands = ["sapcontrol", "hdb", "hdbsql", "hdbuserstore"]
            is_hana_cmd = any(cmd in command.lower() for cmd in hana_commands)

            if is_hana_cmd:
                result = execute_hana_command(command, timeout=60)
            else:
                result = executor.execute_command(command, timeout=60, admin_override=True)

            if result.get("status") == "success" or result.get("exit_code") == 0:
                output = result.get("output", "").strip()
                if output:
                    if voice_mode:
                        summary = _summarize_output_for_voice(command, output, model=_voice_model)
                        if summary:
                            return _resp(summary)
                        return _resp(f"Ran {command}. Result: {output[:500]}")
                    return _resp(f"**Command:** `{command}`\n\n**Output:**\n```\n{output}\n```")
                else:
                    msg = f"Command {command} executed successfully with no output." if voice_mode else f"**Command:** `{command}`\n\nCommand executed successfully (no output)."
                    return _resp(msg)
            else:
                error = result.get("error", "") or result.get("output", "")
                if _is_remote_forbidden(result):
                    return _reject_write(command)
                if voice_mode:
                    return _resp(f"The command {command} failed. Error: {error[:300]}")
                return _resp(f"**Command:** `{command}`\n\n**Error:**\n```\n{error}\n```")

    # Health/status check — return actual HANA service + connection info
    if "health" in msg_lower or "status" in msg_lower:
        try:
            conn = check_hana_connection()
            conn_str = f"Database: **{conn.get('database', '?')}** — Status: **{conn.get('status', 'unknown')}** — Version: {conn.get('version', '?')}"
            from .tools.hana_tools import query_hana as _qh_health
            svc = _qh_health("SELECT SERVICE_NAME, ACTIVE_STATUS, SQL_PORT FROM M_SERVICES ORDER BY SERVICE_NAME")
            if svc.get("status") == "success" and svc.get("rows"):
                rows = svc["rows"]
                if isinstance(rows[0], dict):
                    headers = list(rows[0].keys())
                    tbl = "| " + " | ".join(headers) + " |\n"
                    tbl += "| " + " | ".join("---" for _ in headers) + " |\n"
                    for r in rows:
                        tbl += "| " + " | ".join(str(r.get(h, "")) for h in headers) + " |\n"
                else:
                    tbl = "\n".join(str(r) for r in rows)
                return _resp(f"**System Health**\n\n{conn_str}\n\n**Services:**\n{tbl}")
            return _resp(f"**System Health**\n\n{conn_str}")
        except Exception as e:
            return _resp(f"Health check error: {str(e)}")

    # Backup inquiries — query the actual backup catalog
    elif "backup" in msg_lower:
        from .tools.hana_tools import query_hana as _qh_backup
        bk = _qh_backup(
            "SELECT TOP 5 BACKUP_ID, ENTRY_TYPE_NAME, STATE_NAME, "
            "SYS_START_TIME, SYS_END_TIME, MESSAGE "
            "FROM M_BACKUP_CATALOG ORDER BY SYS_END_TIME DESC"
        )
        if bk.get("status") == "success" and bk.get("rows"):
            rows = bk["rows"]
            if isinstance(rows[0], dict):
                headers = list(rows[0].keys())
                tbl = "| " + " | ".join(headers) + " |\n"
                tbl += "| " + " | ".join("---" for _ in headers) + " |\n"
                for r in rows:
                    tbl += "| " + " | ".join(str(r.get(h, "")) for h in headers) + " |\n"
            else:
                tbl = "\n".join(str(r) for r in rows)
            return _resp(f"**HANA Backup Catalog (Recent)**\n\n{tbl}")
        err = bk.get("error_message", "Could not reach HANA")
        return _resp(f"Backup catalog query failed: {err}. Check HANA connectivity.")

    # SQL/query help — show top expensive queries by default
    elif "sql" in msg_lower or "query" in msg_lower:
        from .tools.hana_tools import query_hana as _qh_sql
        sq = _qh_sql(
            "SELECT TOP 10 SUBSTR(STATEMENT_STRING, 1, 100) AS QUERY, "
            "EXECUTION_COUNT, ROUND(TOTAL_EXECUTION_TIME/1000000, 2) AS TOTAL_SEC, "
            "ROUND(AVG_EXECUTION_TIME/1000, 2) AS AVG_MS "
            "FROM M_SQL_PLAN_CACHE ORDER BY TOTAL_EXECUTION_TIME DESC"
        )
        if sq.get("status") == "success" and sq.get("rows"):
            rows = sq["rows"]
            if isinstance(rows[0], dict):
                headers = list(rows[0].keys())
                tbl = "| " + " | ".join(headers) + " |\n"
                tbl += "| " + " | ".join("---" for _ in headers) + " |\n"
                for r in rows:
                    tbl += "| " + " | ".join(str(r.get(h, "")) for h in headers) + " |\n"
            else:
                tbl = "\n".join(str(r) for r in rows)
            return _resp(f"**Top Expensive SQL Queries**\n\n{tbl}\n\nShare a specific query for detailed analysis.")
        return _resp("I can help optimize SQL queries. Share a query or ask about specific optimization topics.")

    # Diagnostics
    elif "diagnostic" in msg_lower or "diagnose" in msg_lower:
        try:
            result = run_instance_diagnostic(checks=["all"])
            status = result.get("overall_status", "unknown")
            issues = result.get("issue_count", 0)
            return _resp(f"Diagnostic completed. Overall status: **{status}**. Issues detected: {issues}. Use the Instance Monitoring page for full details.")
        except Exception as e:
            return _resp(f"Error running diagnostics: {str(e)}")

    # Explicit browser request (use_browser flag — autonomous already handled above)
    elif use_browser:
        try:
            return _browse_and_answer(message, use_autonomous_browser=False)
        except Exception as exc:
            logger.warning(f"Browse failed: {exc}")
            return _answer_with_llm(message, model=_voice_model)

    # Last resort: try LLM-based command extraction before giving up
    else:
        llm_command = _extract_command_with_llm(original_message, model=_voice_model)
        if llm_command:
            if not _is_read_only(llm_command):
                return _reject_write(llm_command)
            executor = get_http_executor()
            if executor.is_configured():
                result = executor.execute_command(llm_command, timeout=60, admin_override=True)
                if result.get("status") == "success" or result.get("exit_code") == 0:
                    output = result.get("output", "").strip()
                    if output:
                        if voice_mode:
                            summary = _summarize_output_for_voice(llm_command, output, model=_voice_model)
                            if summary:
                                return _resp(summary)
                            return _resp(f"Ran {llm_command}. Result: {output[:500]}")
                        return _resp(f"**Command:** `{llm_command}`\n\n**Output:**\n```\n{output}\n```")
                    msg = f"Command {llm_command} executed successfully with no output." if voice_mode else f"**Command:** `{llm_command}`\n\nCommand executed successfully (no output)."
                    return _resp(msg)
                else:
                    error = result.get("error", "") or result.get("output", "")
                    if _is_remote_forbidden(result):
                        return _reject_write(llm_command)
                    if voice_mode:
                        return _resp(f"The command {llm_command} failed. Error: {error[:300]}")
                    return _resp(f"**Command:** `{llm_command}`\n\n**Error:**\n```\n{error}\n```")

        # Try answering as a general question via LLM before showing welcome
        llm_answer = _answer_with_llm(message, model=_voice_model)
        if llm_answer.get("response") and "couldn't retrieve" not in llm_answer["response"]:
            return llm_answer

        return _resp(f"""I'm the HANA Ops Agent AI assistant. I can help with:\n\n• **Run commands**: "run uptime", "execute df -h", "run sapcontrol -nr {_inst_nr} -function GetProcessList"\n• **System health**: "check health", "show status"\n• **Diagnostics**: "run diagnostics"\n• **Backups**: "check backup status"\n• **SQL optimization**: Share a query and ask me to analyze it\n• **Browse SAP docs**: "what is ...", "how to ...", "explain ..."\n\nWhat would you like help with?""")


# ──────────────────────────────────────────────
# Real-time Metrics Endpoint (non-blocking)
# ──────────────────────────────────────────────

_cached_metrics = None
_metrics_lock = threading.Lock()
_metrics_refresh_thread = None
_startup_reconnect_done = False


def _refresh_metrics_background():
    """Refresh metrics in background thread so the endpoint never blocks."""
    global _cached_metrics
    from .tools.hana_tools import get_remote_hana_metrics

    now = datetime.utcnow()
    sid = os.getenv("GCP_TOOLKIT_HANA_SID", os.getenv("HANA_SID", ""))

    # Check database connection
    try:
        conn = check_hana_connection()
        db_connected = conn.get("status") == "connected"
    except Exception:
        db_connected = False

    metrics = {
        "timestamp": now.isoformat(),
        "system_id": sid,
        "database_connected": db_connected,
        "cpu_usage": None,
        "memory_usage": None,
        "disk_usage": None,
        "active_connections": None,
        "transactions_per_sec": None,
        "active_transactions": None,
        "response_time_ms": None,
        "cache_hit_ratio": None,
        "active_threads": None,
        "blocking_sessions": None,
    }

    if db_connected:
        # Single call to remote exec /hana/metrics gets all metrics at once
        try:
            result = get_remote_hana_metrics()
            if result.get("status") == "success":
                m = result.get("metrics", {})
                metrics["cpu_usage"] = m.get("cpu_usage")
                metrics["memory_usage"] = m.get("memory_usage")
                metrics["active_connections"] = m.get("active_connections")
                metrics["active_transactions"] = m.get("active_transactions")
                metrics["transactions_per_sec"] = m.get("transactions_per_sec")
                metrics["blocking_sessions"] = m.get("blocking_sessions")
                metrics["cache_hit_ratio"] = m.get("cache_hit_ratio")
                metrics["active_threads"] = m.get("active_threads")
        except Exception:
            pass

        # Disk usage not in /hana/metrics — get via separate query
        try:
            disk_result = query_hana("SELECT ROUND(SUM(USED_SIZE) * 100.0 / SUM(TOTAL_SIZE), 1) AS disk_usage FROM M_DISKS WHERE USAGE_TYPE = 'DATA'")
            if disk_result.get("status") == "success" and disk_result.get("rows"):
                metrics["disk_usage"] = disk_result["rows"][0].get("DISK_USAGE")
        except Exception:
            pass

    with _metrics_lock:
        _cached_metrics = metrics


def _ensure_metrics_refresh():
    """Start a background metrics refresh if one isn't already running."""
    global _metrics_refresh_thread
    if _metrics_refresh_thread is None or not _metrics_refresh_thread.is_alive():
        _metrics_refresh_thread = threading.Thread(target=_refresh_metrics_background, daemon=True)
        _metrics_refresh_thread.start()


# Pre-warm: kick off the first metrics refresh immediately on import
# so the cache is populated before the first frontend poll arrives.
_ensure_metrics_refresh()


@app.get("/api/v1/metrics/realtime")
def get_realtime_metrics():
    """Get real-time system metrics. Returns cached metrics instantly,
    refreshes in background to avoid blocking when HANA DB is unreachable."""
    global _metrics_refresh_thread

    # Kick off background refresh if not already running
    _ensure_metrics_refresh()

    # Return cached metrics immediately (or default if first call)
    with _metrics_lock:
        if _cached_metrics is not None:
            return _cached_metrics

    # First call ever — return defaults while background thread works
    sid = os.getenv("GCP_TOOLKIT_HANA_SID", os.getenv("HANA_SID", ""))
    return {
        "timestamp": datetime.utcnow().isoformat(),
        "system_id": sid,
        "database_connected": False,
        "cpu_usage": None,
        "memory_usage": None,
        "disk_usage": None,
        "active_connections": None,
        "transactions_per_sec": None,
        "active_transactions": None,
        "response_time_ms": None,
        "cache_hit_ratio": None,
        "active_threads": None,
        "blocking_sessions": None,
    }


@app.get("/api/v1/metrics/services")
def get_hana_services():
    """Get HANA service status from M_SERVICES joined with M_SERVICE_MEMORY."""
    from .tools.hana_tools import query_hana

    def _strip_quotes(val):
        """Strip escaped quotes from HANA string values."""
        if isinstance(val, str):
            return val.strip('"')
        return val

    try:
        conn = check_hana_connection()
        if conn.get("status") != "connected":
            return {"status": "disconnected", "services": []}
    except Exception:
        return {"status": "disconnected", "services": []}

    try:
        result = query_hana(
            "SELECT s.SERVICE_NAME, s.ACTIVE_STATUS, s.PORT,"
            " ROUND(m.PHYSICAL_MEMORY_SIZE / 1024 / 1024 / 1024, 1) AS MEMORY_GB"
            " FROM M_SERVICES s"
            " LEFT JOIN M_SERVICE_MEMORY m ON s.HOST = m.HOST AND s.PORT = m.PORT"
            " ORDER BY s.SERVICE_NAME"
        )
        logger.info(f"Services query returned {result.get('row_count', len(result.get('rows', [])))} rows")
        if result.get("status") == "success":
            services = []
            for row in result.get("rows", []):
                services.append({
                    "name": _strip_quotes(row.get("SERVICE_NAME", "")),
                    "status": "running" if _strip_quotes(row.get("ACTIVE_STATUS", "")) == "YES" else "stopped",
                    "port": row.get("PORT", 0),
                    "memory": f"{row.get('MEMORY_GB', 0)} GB",
                    "cpu": 0,
                })
            return {"status": "success", "services": services}
        else:
            logger.error(f"Services endpoint - query failed: {result.get('error_message', 'unknown')}")
    except Exception as e:
        logger.error(f"Failed to fetch HANA services: {e}", exc_info=True)

    return {"status": "error", "services": []}


@app.get("/api/v1/metrics/top-queries")
def get_top_queries():
    """Get top resource-consuming queries from M_EXPENSIVE_STATEMENTS."""
    from .tools.hana_tools import query_hana

    def _strip_quotes(val):
        if isinstance(val, str):
            return val.strip('"')
        return val

    try:
        conn = check_hana_connection()
        if conn.get("status") != "connected":
            return {"status": "disconnected", "queries": []}
    except Exception:
        return {"status": "disconnected", "queries": []}

    try:
        result = query_hana(
            "SELECT TOP 10 STATEMENT_STRING, DURATION_MICROSEC, MEMORY_SIZE"
            " FROM M_EXPENSIVE_STATEMENTS"
            " ORDER BY DURATION_MICROSEC DESC"
        )
        if result.get("status") == "success":
            queries = []
            for idx, row in enumerate(result.get("rows", []), 1):
                stmt = _strip_quotes(str(row.get("STATEMENT_STRING", "")))
                duration_us = row.get("DURATION_MICROSEC", 0)
                try:
                    duration_sec = round(float(duration_us) / 1000000.0, 2)
                except (ValueError, TypeError):
                    duration_sec = 0
                mem = row.get("MEMORY_SIZE", 0)
                try:
                    mem_mb = round(float(mem) / 1024 / 1024, 1)
                except (ValueError, TypeError):
                    mem_mb = 0
                queries.append({
                    "id": idx,
                    "query": stmt,
                    "duration": duration_sec,
                    "memory_mb": mem_mb,
                })
            return {"status": "success", "queries": queries}
    except Exception as e:
        logger.error(f"Failed to fetch top queries: {e}")

    return {"status": "error", "queries": []}


@app.get("/api/v1/metrics/active-transactions")
def get_active_transactions():
    """Get currently running transactions with their SQL statements."""
    from .tools.hana_tools import query_hana

    try:
        conn = check_hana_connection()
        if conn.get("status") != "connected":
            return {"status": "disconnected", "transactions": []}
    except Exception:
        return {"status": "disconnected", "transactions": []}

    try:
        result = query_hana(
            "SELECT t.TRANSACTION_ID, t.TRANSACTION_TYPE, t.TRANSACTION_STATUS,"
            " SECONDS_BETWEEN(t.START_TIME, CURRENT_TIMESTAMP) AS DURATION_SEC,"
            " t.START_TIME, c.CONNECTION_ID, c.CLIENT_IP, c.CLIENT_PID,"
            " s.STATEMENT_STRING,"
            " ROUND(s.DURATION_MICROSEC / 1000000.0, 2) AS STMT_DURATION_SEC"
            " FROM M_TRANSACTIONS t"
            " LEFT JOIN M_CONNECTIONS c ON t.CONNECTION_ID = c.CONNECTION_ID"
            " LEFT JOIN M_ACTIVE_STATEMENTS s ON t.CONNECTION_ID = s.CONNECTION_ID"
            " WHERE t.TRANSACTION_STATUS = 'ACTIVE'"
            " ORDER BY t.START_TIME ASC"
        )
        if result.get("status") == "success":
            transactions = []
            for row in result.get("rows", []):
                stmt = row.get("STATEMENT_STRING", "") or ""
                transactions.append({
                    "transaction_id": row.get("TRANSACTION_ID"),
                    "type": row.get("TRANSACTION_TYPE", ""),
                    "status": row.get("TRANSACTION_STATUS", ""),
                    "duration_sec": row.get("DURATION_SEC", 0),
                    "start_time": str(row.get("START_TIME", "")),
                    "connection_id": row.get("CONNECTION_ID"),
                    "client_ip": row.get("CLIENT_IP", ""),
                    "sql": stmt,
                    "stmt_duration_sec": row.get("STMT_DURATION_SEC", 0),
                })
            return {
                "status": "success",
                "count": len(transactions),
                "transactions": transactions
            }
    except Exception:
        pass

    return {"status": "error", "transactions": []}


@app.get("/api/v1/metrics/history")
def get_metrics_history(hours: int = 24):
    """Get historical metrics via the remote exec server's /hana/metrics/history endpoint."""
    import requests
    from .tools.hana_tools import _REMOTE_EXEC_URL, _REMOTE_EXEC_API_KEY, _REQUEST_TIMEOUT

    sid = os.getenv("GCP_TOOLKIT_HANA_SID", os.getenv("HANA_SID", ""))

    # Use the remote server's dedicated history endpoint (avoids raw SQL table issues)
    try:
        resp = requests.get(
            f"{_REMOTE_EXEC_URL}/hana/metrics/history",
            params={"hours": min(hours, 168)},
            headers={"X-API-Key": _REMOTE_EXEC_API_KEY},
            timeout=_REQUEST_TIMEOUT + 15,
        )
        if resp.status_code == 200:
            data = resp.json()
            history = data.get("history", [])
            return {
                "system_id": sid,
                "hours": hours,
                "data_points": len(history),
                "metrics": history
            }
    except Exception:
        pass

    return {
        "system_id": sid,
        "hours": hours,
        "data_points": 0,
        "metrics": [],
        "error": "Failed to query historical data"
    }


@app.get("/api/v1/activities/recent")
def get_recent_activities(limit: int = 20):
    """Get recent system activities for live feed."""
    activities = []

    # Add certificate approvals
    for cert in list(_certificates.values())[:5]:
        activities.append({
            "id": cert.certificate_id,
            "type": "action",
            "severity": "info" if cert.status == "approved" else "warning",
            "message": f"Action {cert.action_type} {cert.status} by {cert.created_by_agent}",
            "timestamp": cert.timestamp,
            "agent": cert.created_by_agent
        })

    # Sort by timestamp and limit
    activities.sort(key=lambda x: x["timestamp"], reverse=True)
    return {
        "activities": activities[:limit],
        "total": len(activities)
    }


# ──────────────────────────────────────────────
# Instance Management Endpoints (vlgdbzo3)
# ──────────────────────────────────────────────

class InstanceDiagnosticRequest(BaseModel):
    instance_name: Optional[str] = None
    project_id: Optional[str] = None
    zone: Optional[str] = None


class InstanceHealingProposal(BaseModel):
    diagnostic_id: str
    script_name: str
    issue_description: str
    parameters: Optional[dict] = None


class InstanceHealingApproval(BaseModel):
    approved_by: str
    notes: Optional[str] = ""


# ──────────────────────────────────────────────
# Diagnostic → Healing auto-generation pipeline
# ──────────────────────────────────────────────

DIAGNOSTIC_TO_HEALING_MAP = {
    "userstore": {
        "script": "auto_db_userstoremanagement",
        "triggers": ["warning", "critical", "error"],
        "sap_notes": ["1792209"],
        "description": "Userstore connectivity issues detected",
    },
    "disk_usage": {
        "script": "auto_db_metadata",
        "triggers": ["critical"],
        "parameters": {"issues": ["backup_paths"]},
        "sap_notes": ["2399979"],
        "description": "Disk usage critical — backup path optimisation needed",
    },
    "memory_usage": {
        "script": "auto_db_dbintegrations",
        "triggers": ["critical"],
        "parameters": {"parameters": ["swappiness"]},
        "sap_notes": ["2131662"],
        "description": "Memory pressure detected — OS tuning required",
    },
    "backup_status": {
        "script": "auto_db_eligibility",
        "triggers": ["warning", "critical"],
        "sap_notes": ["1642148"],
        "description": "Backup validation issues detected",
    },
    "system_parameters": {
        "script": "auto_db_metadata",
        "triggers": ["warning", "critical"],
        "parameters": {"issues": ["db_parameters"]},
        "sap_notes": ["2222200"],
        "description": "System parameters outside recommended range",
    },
    "trace_directory": {
        "script": "auto_db_metadata",
        "triggers": ["warning", "critical"],
        "parameters": {"issues": ["trace_permissions"]},
        "sap_notes": ["2380176"],
        "description": "Trace directory issues detected",
    },
    "process_status": {
        "script": "auto_db_dbintegrations",
        "triggers": ["critical"],
        "sap_notes": ["2177064"],
        "description": "HANA process failures — OS integration check needed",
    },
    "database_alerts": {
        "script": "auto_db_metadata",
        "triggers": ["critical"],
        "sap_notes": ["2147247"],
        "description": "Database alerts require metadata review",
    },
}


def _enrich_with_llm(check_name: str, check_data: dict, script_name: str, diagnostic_result: dict) -> Optional[dict]:
    """Call AI Core LLM to generate detailed analysis for a healing proposal."""
    try:
        from .aicore_client import AICoreiClient
        client = AICoreiClient()
        if not client.is_configured():
            return None

        prompt = (
            "Analyze this SAP HANA diagnostic finding and provide a healing recommendation.\n\n"
            f"Diagnostic Check: {check_name}\n"
            f"Severity: {check_data.get('severity', 'unknown')}\n"
            f"Message: {check_data.get('message', 'N/A')}\n"
            f"Error: {check_data.get('error', 'N/A')}\n"
            f"Proposed Healing Script: {script_name}\n"
            f"Instance: {diagnostic_result.get('instance_name', '')}\n"
            f"SID: {diagnostic_result.get('sid', '')}\n\n"
            "Respond ONLY with JSON (no markdown):\n"
            '{"root_cause":"...","impact":"...","healing_steps":["..."],'
            '"expected_outcome":"...","risk_assessment":"...",'
            '"estimated_downtime":"None|Minimal|Minutes|Requires restart",'
            '"sap_recommendation":"..."}'
        )
        raw = client.generate_text(
            prompt=prompt,
            system_prompt="You are an SAP HANA database expert. Be concise and actionable.",
            temperature=0.3,
            max_tokens=1024,
        )
        # Parse JSON from response
        start = raw.find("{")
        end = raw.rfind("}") + 1
        if start >= 0 and end > start:
            return json.loads(raw[start:end])
        return {"raw_analysis": raw}
    except Exception as exc:
        logger.warning(f"LLM enrichment failed for {check_name}: {exc}")
        return None


def _verify_with_browser(script_name: str, sap_notes: list) -> dict:
    """Use browser-use to verify healing commands against SAP documentation."""
    try:
        from .agent import browser_navigate

        search_topics = {
            "auto_db_userstoremanagement": "HANA userstore configuration hdbuserstore best practice",
            "auto_db_metadata": "HANA backup path configuration global.ini trace permissions",
            "auto_db_dbintegrations": "HANA OS parameters swappiness THP ASLR SAP recommended",
            "auto_db_eligibility": "HANA backup catalog validation eligibility checks",
        }
        topic = search_topics.get(script_name, script_name)
        url = (
            f"https://me.sap.com/notes/{sap_notes[0]}"
            if sap_notes
            else f"https://me.sap.com/search?query={topic}"
        )
        result = browser_navigate(
            url=url,
            task_description=(
                f"Find SAP recommendations about {topic}. "
                "Extract the key recommended steps, parameter values, and any warnings."
            ),
        )
        if result.get("status") == "success":
            return {
                "verified": True,
                "source_url": url,
                "sap_guidance": result.get("extracted_data", ""),
                "timestamp": datetime.utcnow().isoformat(),
            }
        return {
            "verified": False,
            "error": result.get("error_message", "Verification failed"),
            "timestamp": datetime.utcnow().isoformat(),
        }
    except Exception as exc:
        logger.warning(f"Browser verification failed for {script_name}: {exc}")
        return {"verified": False, "error": str(exc), "timestamp": datetime.utcnow().isoformat()}


# ──────────────────────────────────────────────
# Restricted command approval pipeline
# ──────────────────────────────────────────────

def _enrich_restricted_command_llm(command: str) -> Optional[dict]:
    """Use LLM to explain what a restricted command does and assess its risk."""
    try:
        from .aicore_client import AICoreiClient
        client = AICoreiClient()
        if not client.is_configured():
            return None

        prompt = (
            "A user attempted to execute the following command on an SAP HANA production system, "
            "but it was blocked by the safety filter.\n\n"
            f"Command: {command}\n\n"
            "Analyse this command and respond ONLY with JSON (no markdown):\n"
            '{"purpose":"what the command does in 1-2 sentences",'
            '"risk_assessment":"why this command is dangerous on a production HANA system",'
            '"impact":"potential impact if executed incorrectly",'
            '"preconditions":["checks to perform before running"],'
            '"sap_recommendation":"SAP best practice guidance for this operation",'
            '"estimated_downtime":"None|Minimal|Minutes|Requires restart",'
            '"safe_alternative":"a safer read-only alternative if available, or null",'
            '"relevant_sap_notes":["SAP Note numbers if applicable"]}'
        )
        raw = client.generate_text(
            prompt=prompt,
            system_prompt="You are an SAP HANA database and Linux administration expert. Be concise and actionable.",
            temperature=0.3,
            max_tokens=1024,
        )
        start = raw.find("{")
        end = raw.rfind("}") + 1
        if start >= 0 and end > start:
            return json.loads(raw[start:end])
        return {"raw_analysis": raw}
    except Exception as exc:
        logger.warning(f"LLM enrichment failed for restricted command: {exc}")
        return None


def _research_restricted_command_browser(command: str) -> dict:
    """Use browser-use to research a restricted command against SAP documentation."""
    try:
        from .agent import browser_navigate

        # Extract the primary command name for search
        cmd_parts = command.strip().split()
        primary_cmd = cmd_parts[0] if cmd_parts else command
        search_query = f"SAP HANA {primary_cmd} command best practice"

        url = f"https://me.sap.com/search?query={search_query}"
        result = browser_navigate(
            url=url,
            task_description=(
                f"Find SAP documentation about the command '{command}'. "
                "Look for SAP Notes, KBA articles, or official guidance about when "
                "and how to safely use this command on SAP HANA systems. "
                "Extract the SAP Note number, URL, and key recommendations."
            ),
        )
        if result.get("status") == "success":
            return {
                "verified": True,
                "source_url": url,
                "sap_guidance": result.get("extracted_data", ""),
                "sources": result.get("sources", []),
                "timestamp": datetime.utcnow().isoformat(),
            }
        return {
            "verified": False,
            "error": result.get("error_message", "Research failed"),
            "timestamp": datetime.utcnow().isoformat(),
        }
    except Exception as exc:
        logger.warning(f"Browser research failed for restricted command: {exc}")
        return {"verified": False, "error": str(exc), "timestamp": datetime.utcnow().isoformat()}


async def _queue_restricted_command(command: str, source: str = "chat", user_request: str = ""):
    """Queue a restricted command for approval with LLM + browser enrichment."""
    try:
        # LLM enrichment (run in thread)
        llm_analysis = await asyncio.to_thread(_enrich_restricted_command_llm, command)

        # Browser research (best-effort, timeout 90s)
        browser_result: Optional[dict] = None
        try:
            browser_result = await asyncio.wait_for(
                asyncio.to_thread(_research_restricted_command_browser, command),
                timeout=90,
            )
        except (asyncio.TimeoutError, Exception) as exc:
            logger.warning(f"Browser research skipped for restricted command: {exc}")
            browser_result = {"verified": False, "error": "Research timed out or failed"}

        # Extract SAP notes from LLM analysis
        sap_notes = []
        if llm_analysis and isinstance(llm_analysis.get("relevant_sap_notes"), list):
            sap_notes = [str(n) for n in llm_analysis["relevant_sap_notes"] if n]

        # Create ActionCertificate
        cert = ActionCertificate(
            action_type="restricted_command",
            action_description=f"Restricted command execution: {command}",
            target_component=os.getenv("GCP_TOOLKIT_INSTANCE_NAME", ""),
            created_by_agent="supervisor",
            supporting_evidence=[
                f"Command: {command}",
                f"Source: {source}",
                f"Blocked by: safety filter (_is_read_only)",
            ],
            rollback_steps=[
                "Verify system state before execution",
                "Command may not be reversible — review carefully",
            ],
        )
        cert.likelihood = 3
        cert.impact = 3
        cert.compute_dynamic_risk()

        sid = os.getenv("GCP_TOOLKIT_HANA_SID", os.getenv("HANA_SID", ""))
        budget = _risk_budgets.get(sid)
        if not budget:
            budget = RiskBudget(system_id=sid)
            _risk_budgets[sid] = budget

        decision = PolicyEngine.evaluate(cert, budget)
        cert.status = "pending"
        _certificates[cert.certificate_id] = cert

        proposal_data = {
            "certificate_id": cert.certificate_id,
            "proposal_type": "restricted_command",
            "command": command,
            "source": source,
            "user_request": user_request or command,
            "status": "pending_approval",
            "risk_score": cert.risk_score,
            "created_at": datetime.utcnow().isoformat(),
            "llm_analysis": llm_analysis,
            "browser_verification": browser_result,
            "sap_notes": sap_notes,
            "execution_output": None,
            "executed_at": None,
            "approved_by": None,
            "approval_notes": None,
        }
        _restricted_command_approvals[cert.certificate_id] = proposal_data

        # Broadcast approval_required
        await manager.broadcast({
            "type": "approval_required",
            "timestamp": datetime.utcnow().isoformat(),
            "agent": "supervisor",
            "data": {
                "certificate_id": cert.certificate_id,
                "proposal_type": "restricted_command",
                "command": command,
                "risk_score": cert.risk_score,
            },
        })
        logger.info(f"Restricted command queued for approval: {command[:80]} (cert={cert.certificate_id[:8]})")
    except Exception as exc:
        logger.error(f"Failed to queue restricted command for approval: {exc}")


async def _auto_generate_healing_proposals(diagnostic_id: str, diagnostic_result: dict):
    """Analyse diagnostic output → create healing proposals with LLM + browser enrichment."""
    checks = diagnostic_result.get("checks", {})
    proposals_created = []
    scripts_proposed: Dict[str, dict] = {}  # script_name → merged parameters

    # Phase 1: Map issues to healing scripts (deduplicate by script)
    for check_name, check_data in checks.items():
        severity = check_data.get("severity", "ok")
        mapping = DIAGNOSTIC_TO_HEALING_MAP.get(check_name)
        if not mapping or severity not in mapping["triggers"]:
            continue
        script = mapping["script"]
        if script not in scripts_proposed:
            scripts_proposed[script] = {
                "checks": [],
                "parameters": {},
                "sap_notes": [],
                "descriptions": [],
            }
        entry = scripts_proposed[script]
        entry["checks"].append((check_name, check_data))
        entry["descriptions"].append(f"{mapping['description']} — {check_data.get('message', check_name)}")
        # Merge parameters
        for k, v in mapping.get("parameters", {}).items():
            existing = entry["parameters"].setdefault(k, [])
            if isinstance(v, list):
                existing.extend(x for x in v if x not in existing)
        # Merge SAP notes
        for note in mapping.get("sap_notes", []):
            if note not in entry["sap_notes"]:
                entry["sap_notes"].append(note)

    if not scripts_proposed:
        logger.info("No healing proposals needed — all checks passed")
        return []

    # Phase 2: For each healing script, enrich with LLM + browser then create proposal
    for script_name, entry in scripts_proposed.items():
        issue_desc = "; ".join(entry["descriptions"])
        primary_check_name, primary_check_data = entry["checks"][0]

        # LLM enrichment (run in thread to avoid blocking event loop)
        llm_analysis = await asyncio.to_thread(
            _enrich_with_llm, primary_check_name, primary_check_data, script_name, diagnostic_result
        )

        # Browser verification (best-effort, timeout 90s)
        browser_result: Optional[dict] = None
        try:
            browser_result = await asyncio.wait_for(
                asyncio.to_thread(_verify_with_browser, script_name, entry["sap_notes"]),
                timeout=90,
            )
        except (asyncio.TimeoutError, Exception) as exc:
            logger.warning(f"Browser verification skipped for {script_name}: {exc}")
            browser_result = {"verified": False, "error": "Verification timed out or failed"}

        # Create ActionCertificate + proposal (same logic as manual propose)
        cert = ActionCertificate(
            action_type=f"instance_healing_{script_name}",
            action_description=issue_desc,
            target_component=os.getenv("GCP_TOOLKIT_INSTANCE_NAME", ""),
            created_by_agent="instance_healing_agent",
            supporting_evidence=[
                f"Diagnostic ID: {diagnostic_id}",
                f"Checks: {', '.join(c[0] for c in entry['checks'])}",
                f"Severities: {', '.join(c[1].get('severity', '?') for c in entry['checks'])}",
            ],
            rollback_steps=[
                "Verify current state before execution",
                "Document changes made",
                "Execute rollback script if needed",
            ],
        )
        cert.compute_dynamic_risk()

        sid = os.getenv("GCP_TOOLKIT_HANA_SID", os.getenv("HANA_SID", ""))
        budget = _risk_budgets.get(sid)
        if not budget:
            budget = RiskBudget(system_id=sid)
            _risk_budgets[sid] = budget

        decision = PolicyEngine.evaluate(cert, budget)
        can_proceed = decision["decision"] in ("APPROVED", "NEEDS_APPROVAL")
        cert.status = "pending" if can_proceed else "rejected"
        _certificates[cert.certificate_id] = cert

        proposal_data = {
            "certificate_id": cert.certificate_id,
            "diagnostic_id": diagnostic_id,
            "script_name": script_name,
            "parameters": entry["parameters"],
            "status": "pending_approval" if can_proceed else "rejected",
            "risk_score": cert.risk_score,
            "created_at": datetime.utcnow().isoformat(),
            "issue_description": issue_desc,
            "llm_analysis": llm_analysis,
            "browser_verification": browser_result,
            "sap_notes": entry["sap_notes"],
            "auto_generated": True,
        }
        _instance_healing_proposals[cert.certificate_id] = proposal_data
        proposals_created.append(proposal_data)

        # Broadcast approval_required
        await manager.broadcast({
            "type": "approval_required",
            "timestamp": datetime.utcnow().isoformat(),
            "agent": "instance_healing_agent",
            "data": {
                "certificate_id": cert.certificate_id,
                "script_name": script_name,
                "risk_score": cert.risk_score,
                "issue": issue_desc,
                "auto_generated": True,
            },
        })

    logger.info(f"Auto-generated {len(proposals_created)} healing proposals for diagnostic {diagnostic_id}")
    return proposals_created


@app.post("/api/v1/instance/diagnostics")
async def run_instance_diagnostics(req: InstanceDiagnosticRequest):
    """Run diagnostic check on vlgdbzo3 instance."""
    try:
        # Broadcast start
        await manager.broadcast({
            "type": "diagnostic_started",
            "timestamp": datetime.utcnow().isoformat(),
            "agent": "instance_monitor_agent",
            "data": {"instance": req.instance_name or os.getenv("GCP_TOOLKIT_INSTANCE_NAME", "")}
        })

        # Run diagnostic
        result = await asyncio.to_thread(
            run_instance_diagnostic,
            instance_name=req.instance_name,
            project_id=req.project_id,
            zone=req.zone,
        )

        # Store result
        diagnostic_id = result.get('diagnostic_id')
        if not diagnostic_id:
            raise HTTPException(status_code=500, detail="Diagnostic returned no ID")
        _instance_diagnostics[diagnostic_id] = result
        _save_diagnostic_history()

        # Log
        logger = get_instance_logger()
        logger.log_diagnostic(result)

        # Broadcast completion
        await manager.broadcast({
            "type": "diagnostic_completed",
            "timestamp": datetime.utcnow().isoformat(),
            "agent": "instance_monitor_agent",
            "data": {
                "diagnostic_id": diagnostic_id,
                "overall_status": result.get('overall_status'),
                "issue_count": result.get('issue_count', 0)
            }
        })

        # Auto-generate healing proposals for any detected issues
        healing_proposals = []
        if result.get('issue_count', 0) > 0:
            try:
                healing_proposals = await _auto_generate_healing_proposals(diagnostic_id, result)
            except Exception as heal_exc:
                logger.warning(f"Auto-healing generation failed (non-fatal): {heal_exc}")

        return {
            "status": "success",
            "diagnostic_id": diagnostic_id,
            "result": result,
            "healing_proposals": [
                {
                    "certificate_id": p["certificate_id"],
                    "script_name": p["script_name"],
                    "issue_description": p["issue_description"],
                    "risk_score": p["risk_score"],
                    "llm_analysis": p.get("llm_analysis"),
                    "browser_verification": p.get("browser_verification"),
                    "sap_notes": p.get("sap_notes", []),
                }
                for p in healing_proposals
            ],
        }

    except Exception as e:
        await manager.broadcast({
            "type": "diagnostic_failed",
            "timestamp": datetime.utcnow().isoformat(),
            "agent": "instance_monitor_agent",
            "data": {"error": str(e)}
        })
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/v1/instance/diagnostics/history")
def get_diagnostic_history():
    """Get summary list of all diagnostics, newest first."""
    summaries = []
    for diag in _instance_diagnostics.values():
        issue_count = diag.get('issue_count', 0)
        checks = diag.get('checks', {})
        severity_counts = {}
        for c in checks.values():
            sev = c.get('severity', 'info')
            severity_counts[sev] = severity_counts.get(sev, 0) + 1
        summaries.append({
            "diagnostic_id": diag.get('diagnostic_id', ''),
            "timestamp": diag.get('timestamp', ''),
            "overall_status": diag.get('overall_status', 'unknown'),
            "issue_count": issue_count,
            "check_count": len(checks),
            "severity_counts": severity_counts,
            "instance_name": diag.get('instance_name', ''),
        })
    summaries.sort(key=lambda x: x['timestamp'], reverse=True)
    return {"status": "success", "diagnostics": summaries}


@app.get("/api/v1/instance/diagnostics/latest")
def get_latest_diagnostic():
    """Get most recent diagnostic."""
    if not _instance_diagnostics:
        return {
            "status": "no_data",
            "message": "No diagnostics have been run yet. Click 'Run Diagnostics' to start.",
            "result": {"overall_status": "unknown", "checks": {}, "issue_count": 0},
            "timestamp": datetime.utcnow().isoformat(),
        }

    # Get most recent by timestamp
    latest = max(_instance_diagnostics.values(), key=lambda x: x.get('timestamp', ''))
    return latest


@app.get("/api/v1/instance/diagnostics/{diagnostic_id}")
def get_instance_diagnostic(diagnostic_id: str):
    """Get specific diagnostic results."""
    if diagnostic_id not in _instance_diagnostics:
        raise HTTPException(status_code=404, detail="Diagnostic not found")

    return _instance_diagnostics[diagnostic_id]


@app.post("/api/v1/instance/snapshot")
async def create_instance_vm_snapshot():
    """Create daily VM snapshot of vlgdbzo3 instance."""
    try:
        # Broadcast start
        await manager.broadcast({
            "type": "snapshot_started",
            "timestamp": datetime.utcnow().isoformat(),
            "agent": "instance_backup_agent",
            "data": {}
        })

        # Create snapshot
        result = create_instance_snapshot()

        # Store result
        snapshot_id = f"snapshot_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}"
        _instance_snapshots[snapshot_id] = result

        # Log
        logger = get_instance_logger()
        logger.log_snapshot(result)

        # Broadcast completion
        await manager.broadcast({
            "type": "snapshot_completed",
            "timestamp": datetime.utcnow().isoformat(),
            "agent": "instance_backup_agent",
            "data": {
                "status": result.get('status'),
                "snapshots_created": len(result.get('snapshots', [])),
                "snapshots_skipped": len(result.get('skipped', []))
            }
        })

        return {
            "status": "success",
            "snapshot_id": snapshot_id,
            "result": result
        }

    except Exception as e:
        await manager.broadcast({
            "type": "snapshot_failed",
            "timestamp": datetime.utcnow().isoformat(),
            "agent": "instance_backup_agent",
            "data": {"error": str(e)}
        })
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/v1/instance/snapshots")
def list_instance_vm_snapshots():
    """List all VM snapshots for vlgdbzo3."""
    try:
        snapshots = list_instance_snapshots()
        return {
            "status": "success",
            "snapshots": snapshots,
            "total": len(snapshots)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/v1/instance/healing/propose")
async def propose_instance_healing(proposal: InstanceHealingProposal):
    """Propose healing script execution."""
    try:
        # Get diagnostic
        if proposal.diagnostic_id not in _instance_diagnostics:
            raise HTTPException(status_code=404, detail="Diagnostic not found")

        diagnostic = _instance_diagnostics[proposal.diagnostic_id]

        # Create action certificate
        cert = ActionCertificate(
            action_type=f"instance_healing_{proposal.script_name}",
            action_description=proposal.issue_description,
            target_component=os.getenv("GCP_TOOLKIT_INSTANCE_NAME", ""),
            created_by_agent="instance_healing_agent",
            supporting_evidence=[f"Diagnostic ID: {proposal.diagnostic_id}"],
            rollback_steps=[
                "Verify current state before execution",
                "Document changes made",
                "Execute rollback script if needed"
            ]
        )
        cert.compute_dynamic_risk()

        # Check risk budget
        sid = os.getenv("GCP_TOOLKIT_HANA_SID", os.getenv("HANA_SID", ""))
        budget = _risk_budgets.get(sid)
        if not budget:
            budget = RiskBudget(system_id=sid)
            _risk_budgets[sid] = budget

        # Evaluate policy
        decision = PolicyEngine.evaluate(cert, budget)
        can_proceed = decision["decision"] in ("APPROVED", "NEEDS_APPROVAL")

        cert.status = "pending" if can_proceed else "rejected"
        _certificates[cert.certificate_id] = cert

        # Store proposal
        proposal_data = {
            "certificate_id": cert.certificate_id,
            "diagnostic_id": proposal.diagnostic_id,
            "script_name": proposal.script_name,
            "parameters": proposal.parameters or {},
            "status": "pending_approval" if can_proceed else "rejected",
            "risk_score": cert.risk_score,
            "created_at": datetime.utcnow().isoformat()
        }
        _instance_healing_proposals[cert.certificate_id] = proposal_data

        # Broadcast approval request
        await manager.broadcast({
            "type": "approval_required",
            "timestamp": datetime.utcnow().isoformat(),
            "agent": "instance_healing_agent",
            "data": {
                "certificate_id": cert.certificate_id,
                "script_name": proposal.script_name,
                "risk_score": cert.risk_score,
                "issue": proposal.issue_description
            }
        })

        return {
            "status": "success",
            "certificate_id": cert.certificate_id,
            "can_proceed": can_proceed,
            "reason": decision["reason"],
            "risk_score": cert.risk_score,
            "requires_approval": True
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/v1/instance/healing/pending")
def list_pending_approvals():
    """List all healing proposals that are pending approval."""
    pending = []
    for cert_id, proposal in _instance_healing_proposals.items():
        if proposal.get("status") == "pending_approval":
            cert = _certificates.get(cert_id)
            pending.append({
                "certificate_id": cert_id,
                "proposal_type": "healing",
                "script_name": proposal.get("script_name", ""),
                "issue_description": cert.action_description if cert else proposal.get("issue_description", ""),
                "risk_score": proposal.get("risk_score", 0),
                "parameters": proposal.get("parameters", {}),
                "diagnostic_id": proposal.get("diagnostic_id", ""),
                "created_at": proposal.get("created_at", ""),
                "status": proposal["status"],
                "llm_analysis": proposal.get("llm_analysis"),
                "browser_verification": proposal.get("browser_verification"),
                "sap_notes": proposal.get("sap_notes", []),
                "auto_generated": proposal.get("auto_generated", False),
            })

    # Also include restricted command approvals (all statuses for history)
    for cert_id, cmd_proposal in _restricted_command_approvals.items():
        cert = _certificates.get(cert_id)
        pending.append({
            "certificate_id": cert_id,
            "proposal_type": "restricted_command",
            "command": cmd_proposal.get("command", ""),
            "source": cmd_proposal.get("source", "chat"),
            "user_request": cmd_proposal.get("user_request", cmd_proposal.get("command", "")),
            "issue_description": f"Restricted command: {cmd_proposal.get('command', '')}",
            "risk_score": cmd_proposal.get("risk_score", 0),
            "created_at": cmd_proposal.get("created_at", ""),
            "status": cmd_proposal["status"],
            "llm_analysis": cmd_proposal.get("llm_analysis"),
            "browser_verification": cmd_proposal.get("browser_verification"),
            "sap_notes": cmd_proposal.get("sap_notes", []),
            "execution_output": cmd_proposal.get("execution_output"),
            "executed_at": cmd_proposal.get("executed_at"),
            "approved_by": cmd_proposal.get("approved_by"),
            "approval_notes": cmd_proposal.get("approval_notes"),
        })

    # Sort by created_at descending (newest first)
    pending.sort(key=lambda p: p.get("created_at", ""), reverse=True)
    return {"status": "success", "pending_approvals": pending}


@app.post("/api/v1/instance/healing/{certificate_id}/approve")
async def approve_instance_healing(certificate_id: str, approval: InstanceHealingApproval):
    """Approve healing script or restricted command execution."""
    try:
        # Get certificate
        if certificate_id not in _certificates:
            raise HTTPException(status_code=404, detail="Certificate not found")

        cert = _certificates[certificate_id]
        cert.status = "approved"
        cert.approved_by = approval.approved_by
        cert.approved_at = datetime.utcnow()
        cert.approval_notes = approval.notes or ""

        # Determine proposal type
        is_restricted_cmd = certificate_id in _restricted_command_approvals
        is_healing = certificate_id in _instance_healing_proposals

        if not is_restricted_cmd and not is_healing:
            raise HTTPException(status_code=404, detail="Proposal not found")

        if is_restricted_cmd:
            proposal = _restricted_command_approvals[certificate_id]
            proposal["status"] = "approved"
            proposal["approved_by"] = approval.approved_by
            proposal["approval_notes"] = approval.notes or ""
            await manager.broadcast({
                "type": "healing_approved",
                "timestamp": datetime.utcnow().isoformat(),
                "agent": "supervisor",
                "data": {
                    "certificate_id": certificate_id,
                    "approved_by": approval.approved_by,
                    "proposal_type": "restricted_command",
                    "command": proposal.get("command", ""),
                },
            })
            return {
                "status": "success",
                "certificate_id": certificate_id,
                "message": "Restricted command approved. Execute via /execute endpoint."
            }

        proposal = _instance_healing_proposals[certificate_id]

        # Broadcast approval
        await manager.broadcast({
            "type": "healing_approved",
            "timestamp": datetime.utcnow().isoformat(),
            "agent": "instance_healing_agent",
            "data": {
                "certificate_id": certificate_id,
                "approved_by": approval.approved_by,
                "script_name": proposal['script_name']
            }
        })

        return {
            "status": "success",
            "certificate_id": certificate_id,
            "message": "Healing script approved. Execute via /execute endpoint."
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/v1/instance/healing/{certificate_id}/reject")
async def reject_instance_healing(certificate_id: str, approval: InstanceHealingApproval):
    """Reject healing script or restricted command execution."""
    try:
        if certificate_id not in _certificates:
            raise HTTPException(status_code=404, detail="Certificate not found")

        cert = _certificates[certificate_id]
        cert.status = "rejected"

        # Update the correct store
        if certificate_id in _restricted_command_approvals:
            _restricted_command_approvals[certificate_id]["status"] = "rejected"
            _restricted_command_approvals[certificate_id]["approved_by"] = approval.approved_by
            _restricted_command_approvals[certificate_id]["approval_notes"] = approval.notes or ""
        elif certificate_id in _instance_healing_proposals:
            _instance_healing_proposals[certificate_id]["status"] = "rejected"

        # Broadcast rejection
        await manager.broadcast({
            "type": "healing_rejected",
            "timestamp": datetime.utcnow().isoformat(),
            "agent": "supervisor",
            "data": {
                "certificate_id": certificate_id,
                "rejected_by": approval.approved_by,
                "reason": approval.notes
            }
        })

        return {
            "status": "success",
            "certificate_id": certificate_id,
            "message": "Rejected."
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/v1/instance/healing/{certificate_id}/execute")
async def execute_instance_healing(certificate_id: str):
    """Execute approved healing script or restricted command."""
    try:
        # Get certificate
        if certificate_id not in _certificates:
            raise HTTPException(status_code=404, detail="Certificate not found")

        cert = _certificates[certificate_id]

        if cert.status != "approved":
            raise HTTPException(status_code=400, detail="Not approved")

        # Determine if this is a restricted command or a healing script
        is_restricted_cmd = certificate_id in _restricted_command_approvals

        if is_restricted_cmd:
            # ── Execute restricted command via RCE server ──
            cmd_proposal = _restricted_command_approvals[certificate_id]
            command = cmd_proposal["command"]

            await manager.broadcast({
                "type": "healing_executing",
                "timestamp": datetime.utcnow().isoformat(),
                "agent": "supervisor",
                "data": {
                    "certificate_id": certificate_id,
                    "proposal_type": "restricted_command",
                    "command": command,
                },
            })

            # Execute via HTTP command executor (admin override)
            from .tools import get_http_executor
            executor = get_http_executor()
            result = await asyncio.to_thread(
                lambda: executor.execute_command(command, timeout=120, admin_override=True)
            )

            cmd_proposal["status"] = "executed"
            cmd_proposal["execution_output"] = result.get("output", "")
            cmd_proposal["executed_at"] = datetime.utcnow().isoformat()
            cert.status = "executed"

            await manager.broadcast({
                "type": "healing_completed",
                "timestamp": datetime.utcnow().isoformat(),
                "agent": "supervisor",
                "data": {
                    "certificate_id": certificate_id,
                    "proposal_type": "restricted_command",
                    "status": result.get("status", "unknown"),
                    "exit_code": result.get("exit_code"),
                    "output": result.get("output", "")[:2000],
                },
            })

            return {
                "status": "success",
                "certificate_id": certificate_id,
                "execution_result": {
                    "output": result.get("output", ""),
                    "exit_code": result.get("exit_code"),
                    "status": result.get("status", "unknown"),
                },
            }

        # ── Execute healing script ──
        if certificate_id not in _instance_healing_proposals:
            raise HTTPException(status_code=404, detail="Healing proposal not found")
        proposal = _instance_healing_proposals[certificate_id]

        # Broadcast execution start
        await manager.broadcast({
            "type": "healing_executing",
            "timestamp": datetime.utcnow().isoformat(),
            "agent": "instance_healing_agent",
            "data": {
                "certificate_id": certificate_id,
                "script_name": proposal['script_name']
            }
        })

        # Execute healing script
        result = await asyncio.to_thread(
            execute_healing_script,
            script_name=proposal['script_name'],
            parameters=proposal['parameters'],
        )

        # Log
        inst_logger = get_instance_logger()
        inst_logger.log_healing(result, proposal['script_name'])

        # Broadcast progress
        await manager.broadcast({
            "type": "healing_progress",
            "timestamp": datetime.utcnow().isoformat(),
            "agent": "instance_healing_agent",
            "data": {
                "certificate_id": certificate_id,
                "status": result.get('status'),
                "steps_completed": len(result.get('steps', []))
            }
        })

        # Verify
        verification = await asyncio.to_thread(
            verify_healing_execution, proposal['script_name'], result
        )
        inst_logger.log_verification(verification, proposal['script_name'])

        # Deduct risk budget
        sid = os.getenv("GCP_TOOLKIT_HANA_SID", os.getenv("HANA_SID", ""))
        budget = _risk_budgets.get(sid)
        if not budget:
            budget = RiskBudget(system_id=sid)
            _risk_budgets[sid] = budget
        budget.deduct(cert.action_type, cert.created_by_agent)

        # Broadcast completion
        await manager.broadcast({
            "type": "healing_completed",
            "timestamp": datetime.utcnow().isoformat(),
            "agent": "instance_healing_agent",
            "data": {
                "certificate_id": certificate_id,
                "status": result.get('status'),
                "verification_status": verification.get('overall_status')
            }
        })

        return {
            "status": "success",
            "certificate_id": certificate_id,
            "healing_result": result,
            "verification": verification
        }

    except Exception as e:
        await manager.broadcast({
            "type": "healing_failed",
            "timestamp": datetime.utcnow().isoformat(),
            "agent": "instance_healing_agent",
            "data": {
                "certificate_id": certificate_id,
                "error": str(e)
            }
        })
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/v1/instance/status")
def get_instance_status():
    """Get current instance status."""
    sid = os.getenv("GCP_TOOLKIT_HANA_SID", os.getenv("HANA_SID", ""))
    instance_name = (
        os.getenv("GCP_TOOLKIT_INSTANCE_NAME")
        or os.getenv("HANA_INSTANCE_NAME")
        or sid
        or "vlgdbzo3"
    )

    # Get actual snapshot count from GCP
    try:
        snapshots = list_instance_snapshots()
        snapshot_count = len(snapshots)
    except Exception:
        snapshot_count = len(_instance_snapshots)

    return {
        "instance_name": instance_name,
        "project_id": os.getenv("GCP_TOOLKIT_PROJECT_ID", "sap-development"),
        "diagnostics_count": len(_instance_diagnostics),
        "pending_approvals": (
            len([p for p in _instance_healing_proposals.values() if p.get('status') == 'pending_approval'])
            + len([p for p in _restricted_command_approvals.values() if p.get('status') == 'pending_approval'])
        ),
        "pending_commands": len([p for p in _restricted_command_approvals.values() if p.get('status') == 'pending_approval']),
        "snapshots_count": snapshot_count,
    }


# ──────────────────────────────────────────────
# WebSocket Endpoints
# ──────────────────────────────────────────────

# Browser stream connections manager
class BrowserStreamManager:
    def __init__(self):
        self.connections: Dict[str, WebSocket] = {}

    async def connect(self, websocket: WebSocket, conversation_id: str):
        await websocket.accept()
        self.connections[conversation_id] = websocket

    def disconnect(self, conversation_id: str):
        if conversation_id in self.connections:
            del self.connections[conversation_id]

    async def send_update(self, conversation_id: str, data: dict):
        if conversation_id in self.connections:
            try:
                await self.connections[conversation_id].send_json(data)
            except Exception:
                self.disconnect(conversation_id)

browser_manager = BrowserStreamManager()


@app.websocket("/ws/browser-stream")
async def websocket_browser_stream(websocket: WebSocket):
    """WebSocket endpoint for real-time Playwright browser activity streaming."""
    await websocket.accept()
    conversation_id = None

    try:
        # Immediate ack so client can confirm WS connection is healthy
        await websocket.send_json({
            "type": "status",
            "status": "connected",
            "message": "WebSocket connected. Waiting for browser query...",
            "progress": 1,
        })

        # Wait for initial message with conversation_id and query
        try:
            data = await asyncio.wait_for(websocket.receive_text(), timeout=20)
        except asyncio.TimeoutError:
            logger.warning("[ws/browser] Client connected but sent no init payload within 20s")
            await websocket.send_json({
                "type": "error",
                "status": "error",
                "message": "No browser query received within 20s. Please retry.",
            })
            await websocket.close(code=1000)
            return

        try:
            msg = json.loads(data)
        except Exception:
            logger.warning("[ws/browser] Invalid init payload (not JSON)")
            await websocket.send_json({
                "type": "error",
                "status": "error",
                "message": "Invalid browser init payload. Expected JSON.",
            })
            await websocket.close(code=1003)
            return

        conversation_id = msg.get("conversation_id", str(uuid.uuid4()))
        query = str(msg.get("query", "") or "")
        use_playwright = msg.get("use_playwright", True)

        if not query.strip():
            logger.warning("[ws/browser] Empty query received for conversation %s", conversation_id)
            await websocket.send_json({
                "type": "error",
                "status": "error",
                "message": "Browser query is empty. Please ask a question first.",
            })
            await websocket.close(code=1000)
            return

        logger.info(
            "[ws/browser] Init payload received: conversation_id=%s, query_len=%d, use_playwright=%s",
            conversation_id,
            len(query),
            use_playwright,
        )

        browser_manager.connections[conversation_id] = websocket

        if use_playwright:
            # Use browser-use (headful) for LLM-driven autonomous browsing.
            try:
                from .agents.browser_agent import BrowserUseAgent

                await websocket.send_json({
                    "type": "status",
                    "status": "starting",
                    "message": "Launching browser-use agent (headful)...",
                    "progress": 0,
                })

                await websocket.send_json({
                    "type": "action",
                    "action_type": "navigate",
                    "url": "about:blank",
                    "description": f"Searching: {query[:80]}",
                    "progress": 10,
                    "status": "browsing",
                    "success": True,
                })

                logger.info("[ws/browser] Starting browser-use agent (headful)")

                agent = BrowserUseAgent(headless=False)
                is_partial = False
                visited_pages = []  # Collect {url, title} from each step

                # Step callback — streams agent thoughts/scratchpad to the UI
                async def _on_step(browser_state, agent_output, step_num):
                    try:
                        thought_data = {
                            "type": "thought",
                            "step": step_num,
                            "url": getattr(browser_state, "url", "") or "",
                            "title": getattr(browser_state, "title", "") or "",
                            "thinking": getattr(agent_output, "thinking", None) or "",
                            "evaluation": getattr(agent_output, "evaluation_previous_goal", None) or "",
                            "memory": getattr(agent_output, "memory", None) or "",
                            "next_goal": getattr(agent_output, "next_goal", None) or "",
                        }
                        # Extract action names for display
                        actions = []
                        for a in (getattr(agent_output, "action", None) or []):
                            action_dict = a.model_dump() if hasattr(a, "model_dump") else {}
                            for k, v in action_dict.items():
                                if v is not None:
                                    actions.append(k)
                                    break
                        thought_data["actions"] = actions

                        # Track visited pages for sources
                        step_url = getattr(browser_state, "url", "") or ""
                        step_title = getattr(browser_state, "title", "") or ""
                        if step_url and step_url != "about:blank":
                            if not any(p["url"] == step_url for p in visited_pages):
                                visited_pages.append({"url": step_url, "title": step_title})

                        # Include screenshot if available
                        screenshot = getattr(browser_state, "screenshot", None)
                        if screenshot:
                            thought_data["screenshot"] = screenshot

                        await websocket.send_json(thought_data)
                    except Exception as cb_err:
                        logger.debug("[ws/browser] step callback send failed: %s", cb_err)

                try:
                    result_text = await asyncio.wait_for(
                        agent.navigate_and_extract(task=query, timeout=180, step_callback=_on_step),
                        timeout=240,
                    )
                except asyncio.TimeoutError:
                    # Outer timeout — navigate_and_extract itself should have
                    # already returned partial results in most cases, but if the
                    # outer 240s fires we still salvage what we can.
                    logger.warning("[ws/browser] Outer 240s timeout — extracting partial results")
                    result_text = BrowserUseAgent._extract_partial_results(
                        agent._get_inner_agent() if hasattr(agent, '_get_inner_agent') else None,
                        240,
                    )
                    is_partial = True

                # Detect partial-result marker from browser agent
                if result_text and "**Note:** The browser agent" in result_text:
                    is_partial = True

                await websocket.send_json({
                    "type": "action",
                    "action_type": "extract",
                    "url": "",
                    "description": "Browser-use agent finished browsing" + (" (partial — timed out)" if is_partial else ""),
                    "progress": 80,
                    "status": "browsing",
                    "success": True,
                })

                # LLM synthesis on the extracted content (works for both full and partial)
                synthesized = result_text or ""
                if result_text and not result_text.startswith("[Browser"):
                    try:
                        await websocket.send_json({
                            "type": "status",
                            "status": "synthesizing",
                            "message": "Analyzing extracted content with AI..." + (" (from partial results)" if is_partial else ""),
                            "progress": 95,
                        })
                        from .aicore_client import get_aicore_client
                        client = get_aicore_client()
                        if client.is_configured():
                            partial_note = (
                                "\n\nIMPORTANT: The browser agent timed out before completing all queries. "
                                "Synthesize the best possible answer from what WAS collected. "
                                "Clearly note which parts are based on partial information.\n"
                            ) if is_partial else ""
                            system_prompt = (
                                "You are an SAP HANA expert assistant. Answer the user's question based ONLY on "
                                "the documentation excerpts provided below. Cite the source URL when referencing "
                                "specific information. If the documentation doesn't fully answer the question, "
                                "say so and suggest where to look further.\n\n"
                                f"Documentation excerpts:\n{result_text}"
                                f"{partial_note}"
                            )
                            answer = client.generate_text(
                                prompt=query,
                                system_prompt=system_prompt,
                                temperature=0.3,
                                max_tokens=1024,
                            )
                            if answer:
                                synthesized = answer.strip()
                    except Exception as synth_exc:
                        logger.warning(f"LLM synthesis in WS path failed: {synth_exc}")

                # Build sources from visited pages
                browse_sources = [
                    {
                        "url": p["url"],
                        "title": p["title"] or p["url"],
                        "status": "ok",
                        "source": "browser_use",
                    }
                    for p in visited_pages
                ]

                # Append a Sources section to the response text so it's visible in markdown
                if browse_sources and synthesized and not synthesized.startswith("[Browser"):
                    source_lines = "\n".join(
                        f"- [{s['title']}]({s['url']})" for s in browse_sources
                    )
                    synthesized = f"{synthesized}\n\n---\n**Sources:**\n{source_lines}"

                await websocket.send_json({
                    "type": "complete",
                    "status": "complete",
                    "progress": 100,
                    "response": synthesized,
                    "sources": browse_sources,
                    "action_count": max(1, len(visited_pages)),
                    "is_partial": is_partial,
                })

            except Exception as bu_exc:
                logger.error(f"browser-use flow failed: {bu_exc}", exc_info=True)
                await websocket.send_json({
                    "type": "error",
                    "status": "error",
                    "message": f"Browser-use failed: {bu_exc}",
                })
        else:
            await _simulate_browser_steps(websocket, query)

        # Keep connection open until client disconnects
        while True:
            await websocket.receive_text()

    except WebSocketDisconnect:
        if conversation_id:
            browser_manager.disconnect(conversation_id)
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        if conversation_id:
            browser_manager.disconnect(conversation_id)


async def _simulate_browser_steps(websocket: WebSocket, query: str):
    """Fallback when browser automation is unavailable — informs the user honestly."""
    await websocket.send_json({
        "type": "action",
        "url": "",
        "description": "Browser automation is not available",
        "progress": 50,
        "status": "browsing",
        "page_text": "browser-use agent is not available or failed to initialize. Cannot perform live web browsing.",
        "elements": [],
    })
    await asyncio.sleep(0.5)

    fallback_response = (
        f"Browser automation is unavailable. I cannot browse SAP documentation for: {query}\n\n"
        "To get live web results, ensure browser-use is installed:\n"
        "  pip install browser-use\n\n"
        "In the meantime, you can check these resources manually:\n"
        "- SAP KBA: https://userapps.support.sap.com/sap/support/knowledge/en\n"
        "- SAP Notes: https://me.sap.com/notes\n"
        "- SAP Help: https://help.sap.com/docs/SAP_HANA_PLATFORM\n"
        "- SAP Community: https://community.sap.com"
    )

    # Try LLM-only answer as fallback
    try:
        from .aicore_client import get_aicore_client
        client = get_aicore_client()
        if client.is_configured():
            answer = client.generate_text(
                prompt=query,
                system_prompt="You are an SAP HANA expert. Answer based on your knowledge. Be honest if you are not sure.",
                temperature=0.3,
                max_tokens=1024,
            )
            if answer:
                fallback_response = answer.strip()
    except Exception:
        pass

    await websocket.send_json({
        "type": "complete",
        "status": "complete",
        "progress": 100,
        "response": fallback_response,
        "sources": [],
        "action_count": 0,
    })


@app.websocket("/ws/instance-status")
async def websocket_instance_status(websocket: WebSocket):
    """WebSocket endpoint for real-time instance status updates."""
    await manager.connect(websocket)
    try:
        while True:
            # Keep connection alive
            data = await websocket.receive_text()
            # Echo back (optional)
            if data:
                await websocket.send_json({
                    "type": "pong",
                    "timestamp": datetime.utcnow().isoformat()
                })
    except WebSocketDisconnect:
        manager.disconnect(websocket)


# ──────────────────────────────────────────────
# LiveKit Voice Agent — Token Endpoint
# ──────────────────────────────────────────────
class LiveKitTokenRequest(BaseModel):
    identity: str = "user"
    room: str = "hana-sentinel-voice"

@app.post("/api/v1/voice/token")
def get_livekit_token(req: LiveKitTokenRequest):
    """Generate a LiveKit room token for the voice frontend."""
    try:
        from livekit.api import AccessToken, VideoGrants
    except ImportError:
        raise HTTPException(status_code=501, detail="livekit-api not installed. Run: pip install livekit-api")

    api_key = os.getenv("LIVEKIT_API_KEY")
    api_secret = os.getenv("LIVEKIT_API_SECRET")
    livekit_url = os.getenv("LIVEKIT_URL", "")

    if not api_key or not api_secret:
        raise HTTPException(status_code=500, detail="LIVEKIT_API_KEY and LIVEKIT_API_SECRET must be set")

    token = AccessToken(api_key, api_secret) \
        .with_identity(req.identity) \
        .with_grants(VideoGrants(room_join=True, room=req.room))

    return {
        "token": token.to_jwt(),
        "url": livekit_url,
        "room": req.room,
    }


# ──────────────────────────────────────────────
# Frontend Routes (must be last)
# ──────────────────────────────────────────────
@app.get("/{full_path:path}")
async def serve_frontend(full_path: str):
    """Serve React frontend for all non-API routes."""
    # If file exists in dist, serve it
    if os.path.exists(frontend_build_path):
        file_path = os.path.join(frontend_build_path, full_path)
        if os.path.isfile(file_path):
            return FileResponse(file_path)
        # Otherwise serve index.html for SPA routing
        index_path = os.path.join(frontend_build_path, "index.html")
        if os.path.isfile(index_path):
            return FileResponse(index_path)
    
    # Fallback if frontend not built
    return {"message": "Frontend not built. Run 'npm run build' in frontend directory."}
