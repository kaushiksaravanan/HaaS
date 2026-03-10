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
    HANAOperationState,
    RiskBudget,
    ActionCertificate,
    XFixReport,
    PolicyEngine,
    RISK_SCORES,
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
_incidents: Dict[str, HANAOperationState] = {}
_certificates: Dict[str, ActionCertificate] = {}
_xfix_reports: Dict[str, XFixReport] = {}
_risk_budgets: Dict[str, RiskBudget] = {}
_replays: Dict[str, dict] = {}
_instance_diagnostics: Dict[str, dict] = {}
_instance_healing_proposals: Dict[str, dict] = {}
_instance_snapshots: Dict[str, dict] = {}


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
class IncidentCreate(BaseModel):
    system_id: str = os.getenv("GCP_TOOLKIT_HANA_SID", os.getenv("HANA_SID", ""))
    severity: int = 3
    description: str = ""
    detected_by: str = ""
    evidence: dict = {}


class RemediationPropose(BaseModel):
    action_type: str
    description: str
    target_component: str
    agent: str
    evidence: List[str] = []


class ApprovalRequest(BaseModel):
    approved_by: str
    notes: str = ""


class RAGQueryRequest(BaseModel):
    question: str


class ReplayCreate(BaseModel):
    incident_id: str
    modified_policies: dict = {}


class AgentChatRequest(BaseModel):
    message: str
    conversation_id: Optional[str] = None
    admin_mode: bool = False
    use_browser: bool = False  # When True, always browse SAP docs for answers
    autonomous_browser: bool = False  # When True, use browser-use agent (like Manus)


# ──────────────────────────────────────────────
# Incident Endpoints
# ──────────────────────────────────────────────
@app.post("/api/v1/incidents")
def create_incident(req: IncidentCreate):
    """Create incident from agent detection."""
    state = HANAOperationState(system_id=req.system_id)
    state.audit_trail.append(
        {
            "timestamp": datetime.utcnow().isoformat(),
            "event": "incident_created",
            "severity": req.severity,
            "description": req.description,
            "detected_by": req.detected_by,
        }
    )
    _incidents[state.incident_id] = state
    return {"incident_id": state.incident_id, "status": "created"}


@app.get("/api/v1/incidents")
def list_incidents():
    """List all incidents."""
    return {
        "incidents": [
            {
                "incident_id": incident_id,
                **state.model_dump()
            }
            for incident_id, state in _incidents.items()
        ]
    }


@app.get("/api/v1/incidents/{incident_id}")
def get_incident(incident_id: str):
    """Retrieve incident details."""
    if incident_id not in _incidents:
        raise HTTPException(status_code=404, detail="Incident not found")
    return _incidents[incident_id].model_dump()


@app.get("/api/v1/incidents/{incident_id}/timeline")
def get_incident_timeline(incident_id: str):
    """Full event timeline for an incident."""
    if incident_id not in _incidents:
        raise HTTPException(status_code=404, detail="Incident not found")
    return {"incident_id": incident_id, "timeline": _incidents[incident_id].audit_trail}


# ──────────────────────────────────────────────
# Remediation Endpoints
# ──────────────────────────────────────────────
@app.post("/api/v1/incidents/{incident_id}/remediation")
def propose_remediation(incident_id: str, req: RemediationPropose):
    """Propose X-Fix remediation for an incident."""
    if incident_id not in _incidents:
        raise HTTPException(status_code=404, detail="Incident not found")

    # Create Action Certificate
    cert = ActionCertificate(
        created_by_agent=req.agent,
        target_component=req.target_component,
        action_type=req.action_type,
        action_description=req.description,
        supporting_evidence=req.evidence,
    )
    cert.compute_dynamic_risk()

    # Evaluate against policy
    sid = os.getenv("GCP_TOOLKIT_HANA_SID", os.getenv("HANA_SID", ""))
    budget = _risk_budgets.get(sid, RiskBudget())
    decision = PolicyEngine.evaluate(cert, budget)
    cert.status = "approved" if decision["decision"] == "APPROVED" else "pending"
    cert.sign()

    _certificates[cert.certificate_id] = cert

    # Generate X-Fix Report
    xfix = XFixReport(
        certificate_id=cert.certificate_id,
        summary=req.description,
        trigger_event=f"Incident {incident_id}",
        risk_score=cert.risk_score,
        budget_cost=cert.risk_budget_cost,
        approval_required=decision["decision"] == "NEEDS_APPROVAL",
    )
    _xfix_reports[xfix.report_id] = xfix

    # Update incident state
    incident = _incidents[incident_id]
    incident.action_certificate = cert.model_dump()
    incident.xfix_explanation = xfix.model_dump()
    incident.audit_trail.append(
        {
            "timestamp": datetime.utcnow().isoformat(),
            "event": "remediation_proposed",
            "certificate_id": cert.certificate_id,
            "policy_decision": decision,
        }
    )

    return {
        "certificate_id": cert.certificate_id,
        "xfix_report_id": xfix.report_id,
        "policy_decision": decision,
        "xfix_text": xfix.render_text(),
    }


@app.post("/api/v1/remediations/{cert_id}/approve")
def approve_remediation(cert_id: str, req: ApprovalRequest):
    """Human approval of Action Certificate."""
    if cert_id not in _certificates:
        raise HTTPException(status_code=404, detail="Certificate not found")

    cert = _certificates[cert_id]
    cert.approve(req.approved_by, req.notes)
    return {
        "certificate_id": cert_id,
        "status": "approved",
        "approved_by": req.approved_by,
    }


@app.post("/api/v1/remediations/{cert_id}/execute")
def execute_remediation(cert_id: str):
    """Trigger execution of an approved Action Certificate."""
    if cert_id not in _certificates:
        raise HTTPException(status_code=404, detail="Certificate not found")

    cert = _certificates[cert_id]
    if cert.status != "approved":
        raise HTTPException(
            status_code=400,
            detail=f"Certificate status is '{cert.status}', must be 'approved'",
        )

    # Deduct risk budget
    sid = os.getenv("GCP_TOOLKIT_HANA_SID", os.getenv("HANA_SID", ""))
    budget = _risk_budgets.get(sid, RiskBudget())
    if not budget.can_afford(cert.action_type):
        raise HTTPException(status_code=403, detail="Insufficient risk budget")

    txn = budget.deduct(cert.action_type, cert.created_by_agent)
    cert.status = "executed"

    return {
        "certificate_id": cert_id,
        "status": "executed",
        "budget_transaction": txn,
        "governance_mode": budget.governance_mode,
    }


@app.post("/api/v1/remediations/{cert_id}/rollback")
def rollback_remediation(cert_id: str):
    """Trigger rollback of an executed Action Certificate."""
    if cert_id not in _certificates:
        raise HTTPException(status_code=404, detail="Certificate not found")

    cert = _certificates[cert_id]
    cert.status = "rolled_back"
    return {
        "certificate_id": cert_id,
        "status": "rolled_back",
        "rollback_steps": cert.rollback_steps,
    }


# ──────────────────────────────────────────────
# Risk Budget Endpoints
# ──────────────────────────────────────────────
@app.get("/api/v1/risk-budgets/{system_id}")
def get_risk_budget(system_id: str):
    """Current risk budget status."""
    if system_id not in _risk_budgets:
        _risk_budgets[system_id] = RiskBudget(system_id=system_id)
    budget = _risk_budgets[system_id]
    return {
        "system_id": system_id,
        "effective_budget": budget.effective_budget,
        "current_points": budget.current_points,
        "consumed_today": budget.consumed_today,
        "utilization_pct": round(budget.utilization_pct, 1),
        "governance_mode": budget.governance_mode,
        "trust_multiplier": budget.trust_multiplier,
    }


@app.get("/api/v1/risk-budgets/{system_id}/transactions")
def get_budget_transactions(system_id: str):
    """Budget transaction history."""
    if system_id not in _risk_budgets:
        raise HTTPException(status_code=404, detail="Budget not found")
    return {
        "system_id": system_id,
        "transactions": _risk_budgets[system_id].transactions,
    }


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
    "security_agent": {
        "name": "Security Agent",
        "module": "adk_app.agents.security_agent",
        "class": "SecurityAgent",
        "risk_tier": "high",
        "description": "Audits privileges and security configurations"
    },
    "browser_agent": {
        "name": "Browser-Use Agent",
        "module": "adk_app.agents.browser_agent",
        "class": "BrowserUseAgent",
        "risk_tier": "medium",
        "description": "Automates browser-based tasks for SAP support"
    },
    "instance_monitor_agent": {
        "name": "Instance Monitor Agent",
        "module": "adk_app.agents.instance_monitor_agent",
        "class": "InstanceMonitorAgent",
        "risk_tier": "low",
        "description": "Monitors GCP instance health and diagnostics"
    },
    "instance_backup_agent": {
        "name": "Instance Backup Agent",
        "module": "adk_app.agents.instance_backup_agent",
        "class": "InstanceBackupAgent",
        "risk_tier": "medium",
        "description": "Manages GCP instance snapshots and backups"
    },
    "instance_healing_agent": {
        "name": "Instance Healing Agent",
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
# Replay Endpoints
# ──────────────────────────────────────────────
@app.post("/api/v1/replays")
def create_replay(req: ReplayCreate):
    """Create incident replay for what-if analysis."""
    if req.incident_id not in _incidents:
        raise HTTPException(status_code=404, detail="Incident not found")

    replay_id = str(uuid.uuid4())
    _replays[replay_id] = {
        "replay_id": replay_id,
        "original_incident_id": req.incident_id,
        "modified_policies": req.modified_policies,
        "status": "created",
        "created_at": datetime.utcnow().isoformat(),
    }
    return {"replay_id": replay_id, "status": "created"}


@app.get("/api/v1/replays/{replay_id}/comparison")
def get_replay_comparison(replay_id: str):
    """Original vs replay comparison."""
    if replay_id not in _replays:
        raise HTTPException(status_code=404, detail="Replay not found")
    return {
        "replay_id": replay_id,
        "replay": _replays[replay_id],
        "comparison": "Replay analysis would show differences in agent decisions with modified policies.",
    }


# ──────────────────────────────────────────────
# RAG Query Endpoint
# ──────────────────────────────────────────────
@app.post("/api/v1/rag/query")
def query_rag(req: RAGQueryRequest):
    """Query RAG knowledge base."""
    result = rag_query(req.question)
    return result


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
# Security Patch Day Endpoint
# ──────────────────────────────────────────────
@app.post("/api/v1/security/patch-day/assess")
def assess_patch_day():
    """Assess Patch Day impact on landscape.

    Note: This endpoint queries the RAG knowledge base for security notes.
    Real patch data should come from SAP Support Portal integration.
    """
    # Get current HANA version from actual database
    version = None
    try:
        version_result = query_hana("SELECT VERSION FROM M_DATABASE")
        if version_result["status"] == "success" and version_result["rows"]:
            version = version_result["rows"][0].get("VERSION")
    except Exception:
        pass

    # Query RAG for any relevant security advisories
    rag_result = {}
    try:
        rag_result = rag_query("SAP HANA security notes patch day assessment")
    except Exception:
        pass

    return {
        "hana_version": version,
        "rag_assessment": rag_result.get("answer") if rag_result else None,
        "sources": rag_result.get("sources", []) if rag_result else [],
        "note": "Real patch data requires SAP Support Portal API integration",
        "timestamp": datetime.utcnow().isoformat(),
    }


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
    budget = _risk_budgets.get(sid, RiskBudget())

    return {
        "status": "healthy" if db_connected else "degraded",
        "database_connected": db_connected,
        "hana_connection": conn,
        "sapcontrol": processes,
        "global_ini": ini,
        "risk_budget": {
            "governance_mode": budget.governance_mode,
            "utilization_pct": round(budget.utilization_pct, 1),
        },
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

    # TODO: Integrate with actual Google ADK agent
    # For now, provide a basic response
    result = generate_agent_response(
        req.message,
        admin_mode=req.admin_mode,
        use_browser=req.use_browser,
        autonomous_browser=req.autonomous_browser
    )
    response_text = result.get("response", "")
    sources = result.get("sources", [])
    
    # Add assistant response to conversation
    _conversations[conversation_id].append({
        "role": "assistant", 
        "content": response_text,
        "timestamp": datetime.utcnow().isoformat()
    })
    
    return {
        "conversation_id": conversation_id,
        "response": response_text,
        "sources": sources,
        "timestamp": datetime.utcnow().isoformat()
    }


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


def _extract_command_with_llm(user_text: str) -> Optional[str]:
    """Use configured LLM to classify intent and extract a shell command if appropriate."""
    try:
        from .aicore_client import get_aicore_client

        client = get_aicore_client()
        if not client.is_configured():
            logger.warning("LLM command extraction skipped — AI Core not configured")
            return None

        system_prompt = (
            "You are an expert Linux/SAP HANA administrator. "
            "First decide: is the user asking a KNOWLEDGE QUESTION or requesting a COMMAND to run?\n\n"
            "KNOWLEDGE QUESTIONS (return NO_COMMAND):\n"
            "  - Questions about concepts, configuration, architecture: 'reverse proxy in hana?', 'what is HANA replication?'\n"
            "  - SAP Note lookups: 'sap note 2222222', 'sap notes about memory'\n"
            "  - Best practices, troubleshooting theory: 'how does HANA backup work?'\n"
            "  - General knowledge: 'explain index server', 'difference between row and column store'\n\n"
            "COMMANDS (return the shell command):\n"
            "  - Explicit commands: 'ls -ltr', 'df -h', 'run uptime'\n"
            "  - Actionable requests to check live system state: 'check disk usage', 'show running processes'\n"
            "  - System administration tasks: 'restart indexserver', 'list files in /hana/shared'\n\n"
            "Rules:\n"
            "- If KNOWLEDGE QUESTION → return exactly: NO_COMMAND\n"
            "- If COMMAND → return ONLY the raw shell command, no backticks, no explanation\n"
            "- When in doubt, prefer NO_COMMAND over guessing a wrong command"
        )
        prompt = f"User message: {user_text.strip()}"

        llm_response = client.generate_text(
            prompt=prompt,
            system_prompt=system_prompt,
            temperature=0.0,
            max_tokens=120,
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


def _answer_with_llm(question: str) -> dict:
    """Answer a knowledge question using only the LLM (no web browsing)."""
    try:
        from .aicore_client import get_aicore_client

        client = get_aicore_client()
        if client.is_configured():
            system_prompt = (
                "You are an SAP HANA expert assistant. Answer the user's question concisely "
                "and accurately. If you are not sure about something, say so."
            )
            answer = client.generate_text(
                prompt=question,
                system_prompt=system_prompt,
                temperature=0.3,
                max_tokens=1024,
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

    # Try Playwright browser first for visual browsing (Manus-style)
    if use_autonomous_browser:
        try:
            import asyncio
            from .tools.playwright_browser import browse_with_playwright

            logger.info(f"Using Playwright browser for: {question[:50]}...")
            result = asyncio.run(browse_with_playwright(
                query=question,
                headless=True,
                max_pages=3,
            ))

            if result.get("response") and "not installed" not in result.get("response", ""):
                context = result.get("response", "")
                sources = result.get("sources", [])
                logger.info(f"Playwright browser returned {len(sources)} sources")

                # Return with flag indicating Playwright was used
                return {
                    "response": context,
                    "sources": sources,
                    "use_playwright": True,
                    "actions": result.get("actions", []),
                }
        except Exception as exc:
            logger.warning(f"Playwright browser failed: {exc}, falling back to web scraping")

    # Try browser-use agent as second option
    if not context and use_autonomous_browser:
        try:
            from .agents.browser_agent import BrowserUseAgent
            browser_agent = BrowserUseAgent()
            logger.info(f"Using browser-use agent for: {question[:50]}...")
            result = browser_agent.run_task(f"Search the web and find information about: {question}")
            if result and "failed" not in result.lower():
                context = result
                sources.append({
                    "url": "browser-use-agent",
                    "title": "Autonomous Browser Agent",
                    "status": "ok",
                    "source": "browser_use",
                })
                logger.info("Browser-use agent returned results")
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


def generate_agent_response(message: str, admin_mode: bool = False, use_browser: bool = False, autonomous_browser: bool = False) -> dict:
    """Generate agent response based on user message.
    Supports direct command execution and knowledge browsing.

    Args:
        message: User's message
        admin_mode: If True, allow unrestricted command execution
        use_browser: If True, always browse web for answers
        autonomous_browser: If True, use browser-use agent for autonomous browsing (like Manus)

    Returns:
        {"response": str, "sources": list} — sources is empty for non-browse responses
    """
    from .tools.http_command_executor import get_http_executor, execute_hana_command

    msg_lower = message.lower()

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

    def _resp(text, sources=None):
        return {"response": text, "sources": sources or []}

    # Check for knowledge questions FIRST (before admin mode tries to extract commands)
    # This ensures "SAP Note 222221" goes to browser, not shell
    if _is_knowledge_question(msg_lower) and not has_shell_command:
        try:
            return _browse_and_answer(message, use_autonomous_browser=autonomous_browser)
        except Exception as exc:
            logger.warning(f"Browse failed for knowledge question: {exc}")
            return _answer_with_llm(message)

    if admin_mode:
        # Let the LLM decide if this is a command or a knowledge question
        command = _extract_command_with_llm(message)

        if not command:
            # LLM says it's NOT a command — try answering as a knowledge question
            try:
                browse_answer = _browse_and_answer(message, use_autonomous_browser=autonomous_browser)
                if browse_answer.get("response") and "couldn't find" not in browse_answer.get("response", ""):
                    return browse_answer
            except Exception as exc:
                logger.warning(f"Browse failed in admin mode fallback: {exc}")
            return _answer_with_llm(message)

        executor = get_http_executor()
        if not executor.is_configured():
            return _resp("Error: Remote execution server not configured. Check REMOTE_EXEC_URL and REMOTE_EXEC_API_KEY in .env")

        result = executor.execute_command(command, timeout=60, admin_override=True)

        if result.get("status") == "success" or result.get("exit_code") == 0:
            output = result.get("output", "").strip()
            if output:
                return _resp(f"**Admin Command:** `{command}`\n\n**Output:**\n```\n{output}\n```")
            return _resp(f"**Admin Command:** `{command}`\n\nCommand executed successfully (no output).")

        error = result.get("error", "") or result.get("output", "")
        return _resp(f"**Admin Command:** `{command}`\n\n**Error:**\n```\n{error}\n```")

    if is_command_request or has_shell_command:
        command = _extract_command_heuristic(message, msg_lower)

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
                return _resp(f"**Command:** `{command}`\n\n**Output:**\n```\n{output}\n```")
            else:
                return _resp(f"**Command:** `{command}`\n\nCommand executed successfully (no output).")
        else:
            error = result.get("error", "") or result.get("output", "")
            return _resp(f"**Command:** `{command}`\n\n**Error:**\n```\n{error}\n```")

    # Health/status check
    if "health" in msg_lower or "status" in msg_lower:
        try:
            conn = check_hana_connection()
            return _resp(f"System health check completed. Database status: {conn.get('status', 'unknown')}")
        except Exception as e:
            return _resp(f"I can help you check system health. Error: {str(e)}")

    # Backup inquiries
    elif "backup" in msg_lower:
        return _resp("I can assist with backup operations. What would you like to know about backups?")

    # SQL/query help
    elif "sql" in msg_lower or "query" in msg_lower:
        return _resp("I can help optimize SQL queries. Please share the query you'd like me to analyze.")

    # Diagnostics
    elif "diagnostic" in msg_lower or "diagnose" in msg_lower:
        try:
            result = run_instance_diagnostic(checks=["all"])
            status = result.get("overall_status", "unknown")
            issues = result.get("issue_count", 0)
            return _resp(f"Diagnostic completed. Overall status: **{status}**. Issues detected: {issues}. Use the Instance Monitoring page for full details.")
        except Exception as e:
            return _resp(f"Error running diagnostics: {str(e)}")

    # Explicit browser request (use_browser or autonomous_browser flags)
    elif use_browser or autonomous_browser:
        try:
            return _browse_and_answer(message, use_autonomous_browser=autonomous_browser)
        except Exception as exc:
            logger.warning(f"Browse failed: {exc}")
            return _answer_with_llm(message)

    # Last resort: try LLM-based command extraction before giving up
    else:
        llm_command = _extract_command_with_llm(message)
        if llm_command:
            executor = get_http_executor()
            if executor.is_configured():
                result = executor.execute_command(llm_command, timeout=60, admin_override=True)
                if result.get("status") == "success" or result.get("exit_code") == 0:
                    output = result.get("output", "").strip()
                    if output:
                        return _resp(f"**Command:** `{llm_command}`\n\n**Output:**\n```\n{output}\n```")
                    return _resp(f"**Command:** `{llm_command}`\n\nCommand executed successfully (no output).")
                else:
                    error = result.get("error", "") or result.get("output", "")
                    return _resp(f"**Command:** `{llm_command}`\n\n**Error:**\n```\n{error}\n```")

        # Try answering as a general question via LLM before showing welcome
        llm_answer = _answer_with_llm(message)
        if llm_answer.get("response") and "couldn't retrieve" not in llm_answer["response"]:
            return llm_answer

        return _resp("""I'm the HANA Sentinel AI assistant. I can help with:\n\n• **Run commands**: "run uptime", "execute df -h", "run sapcontrol -nr 00 -function GetProcessList"\n• **System health**: "check health", "show status"\n• **Diagnostics**: "run diagnostics"\n• **Backups**: "check backup status"\n• **SQL optimization**: Share a query and ask me to analyze it\n• **Browse SAP docs**: "what is ...", "how to ...", "explain ..."\n\nWhat would you like help with?""")


# ──────────────────────────────────────────────
# Real-time Metrics Endpoint (non-blocking)
# ──────────────────────────────────────────────

_cached_metrics = None
_metrics_lock = threading.Lock()
_metrics_refresh_thread = None


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
        "risk_budget": _risk_budgets.get(sid, RiskBudget(system_id=sid)).model_dump() if sid else {},
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


@app.get("/api/v1/metrics/realtime")
def get_realtime_metrics():
    """Get real-time system metrics. Returns cached metrics instantly,
    refreshes in background to avoid blocking when HANA DB is unreachable."""
    global _metrics_refresh_thread

    # Kick off background refresh if not already running
    if _metrics_refresh_thread is None or not _metrics_refresh_thread.is_alive():
        _metrics_refresh_thread = threading.Thread(target=_refresh_metrics_background, daemon=True)
        _metrics_refresh_thread.start()

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
        "risk_budget": _risk_budgets.get(sid, RiskBudget(system_id=sid)).model_dump() if sid else {},
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
                    "query": stmt[:80] + "..." if len(stmt) > 80 else stmt,
                    "duration": duration_sec,
                    "calls": mem_mb,
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
                    "sql": stmt[:120] + "..." if len(stmt) > 120 else stmt,
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

    # Add incidents
    for incident_id, incident in list(_incidents.items())[:5]:
        activities.append({
            "id": incident_id,
            "type": "incident",
            "severity": "error" if incident.severity > 3 else "warning",
            "message": f"Incident detected: {incident.description or 'System anomaly'}",
            "timestamp": incident.audit_trail[0]["timestamp"] if incident.audit_trail else datetime.utcnow().isoformat(),
            "agent": incident.audit_trail[0].get("detected_by", "system") if incident.audit_trail else "system"
        })

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
        result = run_instance_diagnostic(
            instance_name=req.instance_name,
            project_id=req.project_id,
            zone=req.zone
        )

        # Store result
        diagnostic_id = result.get('diagnostic_id')
        _instance_diagnostics[diagnostic_id] = result

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

        return {
            "status": "success",
            "diagnostic_id": diagnostic_id,
            "result": result
        }

    except Exception as e:
        await manager.broadcast({
            "type": "diagnostic_failed",
            "timestamp": datetime.utcnow().isoformat(),
            "agent": "instance_monitor_agent",
            "data": {"error": str(e)}
        })
        raise HTTPException(status_code=500, detail=str(e))


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

        cert.status = "pending_approval" if can_proceed else "denied"
        _certificates[cert.certificate_id] = cert

        # Store proposal
        proposal_data = {
            "certificate_id": cert.certificate_id,
            "diagnostic_id": proposal.diagnostic_id,
            "script_name": proposal.script_name,
            "parameters": proposal.parameters or {},
            "status": cert.status,
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
            "reason": reason,
            "risk_score": cert.risk_score,
            "requires_approval": True
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/v1/instance/healing/{certificate_id}/approve")
async def approve_instance_healing(certificate_id: str, approval: InstanceHealingApproval):
    """Approve healing script execution."""
    try:
        # Get certificate
        if certificate_id not in _certificates:
            raise HTTPException(status_code=404, detail="Certificate not found")

        cert = _certificates[certificate_id]
        cert.status = "approved"

        # Get proposal
        if certificate_id not in _instance_healing_proposals:
            raise HTTPException(status_code=404, detail="Healing proposal not found")

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
    """Reject healing script execution."""
    try:
        if certificate_id not in _certificates:
            raise HTTPException(status_code=404, detail="Certificate not found")

        cert = _certificates[certificate_id]
        cert.status = "rejected"

        proposal = _instance_healing_proposals.get(certificate_id, {})

        # Broadcast rejection
        await manager.broadcast({
            "type": "healing_rejected",
            "timestamp": datetime.utcnow().isoformat(),
            "agent": "instance_healing_agent",
            "data": {
                "certificate_id": certificate_id,
                "rejected_by": approval.approved_by,
                "reason": approval.notes
            }
        })

        return {
            "status": "success",
            "certificate_id": certificate_id,
            "message": "Healing script rejected."
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/v1/instance/healing/{certificate_id}/execute")
async def execute_instance_healing(certificate_id: str):
    """Execute approved healing script."""
    try:
        # Get certificate
        if certificate_id not in _certificates:
            raise HTTPException(status_code=404, detail="Certificate not found")

        cert = _certificates[certificate_id]

        if cert.status != "approved":
            raise HTTPException(status_code=400, detail="Healing not approved")

        # Get proposal
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
        result = execute_healing_script(
            script_name=proposal['script_name'],
            parameters=proposal['parameters']
        )

        # Log
        logger = get_instance_logger()
        logger.log_healing(result, proposal['script_name'])

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
        verification = verify_healing_execution(proposal['script_name'], result)
        logger.log_verification(verification, proposal['script_name'])

        # Deduct risk budget
        sid = os.getenv("GCP_TOOLKIT_HANA_SID", os.getenv("HANA_SID", ""))
        budget = _risk_budgets[sid]
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
    return {
        "instance_name": os.getenv("GCP_TOOLKIT_INSTANCE_NAME", ""),
        "project_id": os.getenv("GCP_TOOLKIT_PROJECT_ID", ""),
        "diagnostics_count": len(_instance_diagnostics),
        "pending_approvals": len([p for p in _instance_healing_proposals.values() if p['status'] == 'pending_approval']),
        "snapshots_count": len(_instance_snapshots),
        "risk_budget": _risk_budgets.get(sid).model_dump() if sid in _risk_budgets else None
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
        # Wait for initial message with conversation_id and query
        data = await websocket.receive_text()
        msg = json.loads(data)
        conversation_id = msg.get("conversation_id", str(uuid.uuid4()))
        query = msg.get("query", "")
        use_playwright = msg.get("use_playwright", True)

        browser_manager.connections[conversation_id] = websocket

        if use_playwright:
            # Use real Playwright browser automation
            try:
                from .tools.playwright_browser import browse_with_playwright, BrowserAction

                action_count = [0]

                async def on_action(action: BrowserAction):
                    """Stream each browser action to the WebSocket."""
                    action_count[0] += 1
                    total_expected = 10
                    progress = min(95, int((action_count[0] / total_expected) * 100))

                    # Send screenshot with page text and elements
                    await websocket.send_json({
                        "type": "action",
                        "action_type": action.action_type,
                        "url": action.url,
                        "page_title": action.page_title,
                        "description": action.description,
                        "screenshot": action.screenshot_base64,  # Base64 screenshot
                        "cursor_x": action.cursor_x,
                        "cursor_y": action.cursor_y,
                        "page_text": action.page_text[:1500] if action.page_text else "",
                        "elements": [
                            {
                                "tag": e.tag,
                                "text": e.text,
                                "element_type": e.element_type,
                                "href": e.href,
                            }
                            for e in (action.elements or [])[:15]
                        ],
                        "target_element": {
                            "tag": action.target_element.tag,
                            "text": action.target_element.text,
                            "element_type": action.target_element.element_type,
                        } if action.target_element else None,
                        "target": action.target,
                        "progress": progress,
                        "status": "browsing",
                        "success": action.success,
                        "error": action.error,
                    })

                # Send starting status
                await websocket.send_json({
                    "type": "status",
                    "status": "starting",
                    "message": "Launching Playwright browser...",
                    "progress": 0,
                })

                # Run Playwright browser
                result = await browse_with_playwright(
                    query=query,
                    on_action=lambda a: asyncio.create_task(on_action(a)),
                    headless=True,
                    max_pages=3,
                )

                # Send completion
                await websocket.send_json({
                    "type": "complete",
                    "status": "complete",
                    "progress": 100,
                    "response": result.get("response", ""),
                    "sources": result.get("sources", []),
                    "action_count": len(result.get("actions", [])),
                })

            except ImportError:
                logger.warning("Playwright not available, using simulation")
                await _simulate_browser_steps(websocket, query)
            except Exception as e:
                logger.error(f"Playwright error: {e}")
                await websocket.send_json({
                    "type": "error",
                    "status": "error",
                    "message": str(e),
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
    """Fallback simulation when Playwright is not available."""
    steps = [
        {
            "url": "about:blank",
            "action": "Initializing browser...",
            "progress": 5,
            "page_text": "Browser starting up...",
            "elements": [],
        },
        {
            "url": "https://www.google.com",
            "action": "Opening search engine...",
            "progress": 15,
            "page_text": "Google Search - The most comprehensive index of web pages",
            "elements": [
                {"tag": "input", "text": "Search", "element_type": "input"},
                {"tag": "button", "text": "Google Search", "element_type": "button"},
                {"tag": "button", "text": "I'm Feeling Lucky", "element_type": "button"},
            ],
        },
        {
            "url": f"https://www.google.com/search?q={query}",
            "action": "Searching...",
            "progress": 30,
            "page_text": f"Search results for: {query}\n\nAbout 1,230,000 results (0.42 seconds)\n\n1. SAP Help Portal - Documentation\nhttps://help.sap.com/docs\nComprehensive documentation for SAP products...\n\n2. SAP Community\nhttps://community.sap.com\nConnect with SAP experts and users...",
            "elements": [
                {"tag": "a", "text": "SAP Help Portal", "element_type": "link", "href": "https://help.sap.com"},
                {"tag": "a", "text": "SAP Community", "element_type": "link", "href": "https://community.sap.com"},
                {"tag": "a", "text": "SAP Notes", "element_type": "link", "href": "https://me.sap.com/notes"},
            ],
            "target_element": {"tag": "a", "text": "SAP Help Portal", "element_type": "link"},
        },
        {
            "url": "https://help.sap.com/docs",
            "action": "Navigating to SAP docs...",
            "progress": 45,
            "page_text": "SAP Help Portal\n\nWelcome to the SAP Help Portal, your central access point for SAP documentation.\n\nPopular Topics:\n- SAP HANA Administration Guide\n- SAP HANA SQL Reference\n- Backup and Recovery\n- Performance Optimization",
            "elements": [
                {"tag": "a", "text": "SAP HANA Administration Guide", "element_type": "link"},
                {"tag": "a", "text": "Backup and Recovery", "element_type": "link"},
                {"tag": "button", "text": "Search Documentation", "element_type": "button"},
            ],
        },
        {
            "url": "https://me.sap.com/notes",
            "action": "Checking SAP Notes...",
            "progress": 60,
            "page_text": "SAP Notes Search\n\nFind solutions and recommendations from SAP support.\n\nRecent Notes:\n- Note 2222200 - HANA Performance\n- Note 2380291 - Security Configuration\n- Note 2177064 - Backup Best Practices",
            "elements": [
                {"tag": "a", "text": "Note 2222200", "element_type": "link"},
                {"tag": "a", "text": "Note 2380291", "element_type": "link"},
                {"tag": "input", "text": "Search notes...", "element_type": "input"},
            ],
        },
        {
            "url": "https://community.sap.com",
            "action": "Reading community posts...",
            "progress": 75,
            "page_text": "SAP Community\n\nAsk questions, share knowledge, and connect with experts.\n\nTrending Discussions:\n- Best practices for HANA memory management\n- Troubleshooting backup failures\n- SQL optimization techniques",
            "elements": [
                {"tag": "a", "text": "Ask a Question", "element_type": "link"},
                {"tag": "a", "text": "Browse Topics", "element_type": "link"},
            ],
        },
        {
            "url": "https://help.sap.com/docs",
            "action": "Extracting content...",
            "progress": 85,
            "page_text": "Extracting relevant information from visited pages...\n\nContent gathered from 3 sources:\n- SAP Help Portal\n- SAP Notes\n- SAP Community",
            "elements": [],
        },
        {
            "url": "complete",
            "action": "Synthesizing answer...",
            "progress": 95,
            "page_text": "Processing extracted content with AI model...",
            "elements": [],
        },
        {
            "url": "complete",
            "action": "Done!",
            "progress": 100,
            "page_text": "Answer ready.",
            "elements": [],
        },
    ]

    for step in steps:
        await websocket.send_json({
            "type": "action",
            "url": step["url"],
            "description": step["action"],
            "progress": step["progress"],
            "status": "browsing" if step["progress"] < 100 else "complete",
            "page_text": step.get("page_text", ""),
            "elements": step.get("elements", []),
            "target_element": step.get("target_element"),
        })
        await asyncio.sleep(0.8)


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
