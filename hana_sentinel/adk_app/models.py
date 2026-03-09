"""
Core data models for HANA Sentinel governance layer.
Implements: Action Certificates, X-Fix Reports, Risk Budget, Policy Engine.

ALL FORMULAS ARE DYNAMIC — driven by configuration, not hardcoded constants.
Override any default via environment variables or the DynamicConfig class.
"""

from pydantic import BaseModel, Field
from typing import Optional, List, Literal, Dict
from datetime import datetime
import uuid
import hashlib
import json
import os


# ──────────────────────────────────────────────
# Dynamic Configuration (NO HARDCODED VALUES)
# ──────────────────────────────────────────────
class DynamicConfig(BaseModel):
    """
    Centralized configuration for all governance formulas.
    Every threshold, multiplier, and score is configurable.
    Override via env vars or at runtime.
    """

    # Risk Budget defaults
    daily_baseline: int = int(os.getenv("RISK_DAILY_BASELINE", "100"))

    # Trust multiplier formula params
    trust_reward_threshold_days: int = int(os.getenv("TRUST_REWARD_DAYS", "7"))
    trust_reward_factor: float = float(os.getenv("TRUST_REWARD_FACTOR", "1.1"))
    trust_max_multiplier: float = float(os.getenv("TRUST_MAX_MULTIPLIER", "1.5"))
    trust_penalty_multiplier: float = float(
        os.getenv("TRUST_PENALTY_MULTIPLIER", "0.75")
    )

    # Behavioral gate thresholds (percentage of budget consumed)
    gate_hootl_max: float = float(os.getenv("GATE_HOOTL_MAX", "50"))
    gate_hotl_max: float = float(os.getenv("GATE_HOTL_MAX", "75"))
    gate_hitl_async_max: float = float(os.getenv("GATE_HITL_ASYNC_MAX", "90"))
    gate_hitl_sync_max: float = float(os.getenv("GATE_HITL_SYNC_MAX", "100"))

    # Policy engine thresholds
    high_risk_threshold: int = int(os.getenv("HIGH_RISK_THRESHOLD", "12"))
    frozen_allowed_ops: List[str] = Field(
        default_factory=lambda: os.getenv(
            "FROZEN_ALLOWED_OPS", "read_monitoring,log_analysis,config_read"
        ).split(",")
    )

    # Default cost for unknown operations
    unknown_op_cost: int = int(os.getenv("UNKNOWN_OP_COST", "25"))

    # Health thresholds
    cpu_warning_pct: float = float(os.getenv("CPU_WARNING_PCT", "80"))
    cpu_critical_pct: float = float(os.getenv("CPU_CRITICAL_PCT", "95"))
    mem_warning_pct: float = float(os.getenv("MEM_WARNING_PCT", "85"))
    mem_critical_pct: float = float(os.getenv("MEM_CRITICAL_PCT", "95"))
    disk_warning_pct: float = float(os.getenv("DISK_WARNING_PCT", "80"))
    disk_critical_pct: float = float(os.getenv("DISK_CRITICAL_PCT", "90"))

    # Backup compliance
    backup_max_age_hours: int = int(os.getenv("BACKUP_MAX_AGE_HOURS", "24"))


# Global config instance — can be replaced at runtime
_config = DynamicConfig()


def get_config() -> DynamicConfig:
    return _config


def set_config(config: DynamicConfig):
    global _config
    _config = config


# ──────────────────────────────────────────────
# Dynamic Risk Matrix (Section 5)
# ──────────────────────────────────────────────
def _load_risk_scores() -> Dict[str, int]:
    """
    Load risk scores from RISK_SCORES_JSON env var or use defaults.
    Format: JSON object {"operation_name": score, ...}
    Score formula: Likelihood (1-5) x Impact (1-5)
    """
    env_scores = os.getenv("RISK_SCORES_JSON", "")
    if env_scores:
        try:
            return json.loads(env_scores)
        except json.JSONDecodeError:
            pass

    return {
        "read_monitoring": int(os.getenv("RISK_read_monitoring", "1")),
        "log_analysis": int(os.getenv("RISK_log_analysis", "2")),
        "config_read": int(os.getenv("RISK_config_read", "1")),
        "parameter_change": int(os.getenv("RISK_parameter_change", "6")),
        "global_ini_mod": int(os.getenv("RISK_global_ini_mod", "6")),
        "backup_execution": int(os.getenv("RISK_backup_execution", "6")),
        "service_restart": int(os.getenv("RISK_service_restart", "12")),
        "security_change": int(os.getenv("RISK_security_change", "8")),
        "data_modification": int(os.getenv("RISK_data_modification", "15")),
        "failover_trigger": int(os.getenv("RISK_failover_trigger", "20")),
    }


# Loaded once, but can be refreshed
RISK_SCORES = _load_risk_scores()


def refresh_risk_scores():
    """Reload risk scores from environment. Call after env changes."""
    global RISK_SCORES
    RISK_SCORES = _load_risk_scores()


def get_risk_cost(operation: str) -> int:
    """Get the risk cost for an operation, using dynamic lookup."""
    return RISK_SCORES.get(operation, get_config().unknown_op_cost)


def compute_risk_score(likelihood: int, impact: int) -> int:
    """Compute risk score from dynamic Likelihood x Impact formula.
    Both values are on a 1-5 scale.

    Args:
        likelihood: Probability of failure (1=rare, 5=certain)
        impact: Consequence severity (1=negligible, 5=catastrophic)

    Returns:
        int: Risk score (1-25)
    """
    return max(1, min(25, likelihood * impact))


# ──────────────────────────────────────────────
# LangGraph-style State Schema (Section 4)
# ──────────────────────────────────────────────
class HANAOperationState(BaseModel):
    """Mirrors PRD Section 4 — State Schema."""

    incident_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    system_id: str = os.getenv("HANA_SID", "HXE")
    risk_score: int = 0
    risk_budget_remaining: int = int(os.getenv("RISK_DAILY_BASELINE", "100"))
    action_certificate: Optional[dict] = None
    approval_status: Literal["pending", "approved", "rejected", "auto"] = "pending"
    execution_status: Literal[
        "idle", "executing", "completed", "failed", "rolled_back"
    ] = "idle"
    xfix_explanation: Optional[dict] = None
    audit_trail: List[dict] = Field(default_factory=list)


# ──────────────────────────────────────────────
# Risk Budget Engine (Section 5) — FULLY DYNAMIC
# ──────────────────────────────────────────────
class RiskBudget(BaseModel):
    """
    PRD Section 5 — Agent Risk Budget adapted from Google SRE error budgets.
    Rolling 24-hour window with trust multipliers.
    ALL thresholds and formulas are driven by DynamicConfig.
    """

    system_id: str = os.getenv("HANA_SID", "HXE")
    daily_baseline: int = int(os.getenv("RISK_DAILY_BASELINE", "100"))
    current_points: int = int(os.getenv("RISK_DAILY_BASELINE", "100"))
    consumed_today: int = 0
    trust_multiplier: float = 1.0
    consecutive_clean_days: int = 0
    last_reset: datetime = Field(default_factory=datetime.utcnow)
    transactions: List[dict] = Field(default_factory=list)

    @property
    def effective_budget(self) -> int:
        """Dynamic: baseline * trust_multiplier."""
        return int(self.daily_baseline * self.trust_multiplier)

    @property
    def utilization_pct(self) -> float:
        """Dynamic: consumed / effective_budget * 100."""
        eff = self.effective_budget
        if eff == 0:
            return 100.0
        return (self.consumed_today / eff) * 100

    @property
    def governance_mode(self) -> str:
        """Dynamic behavioral gates — thresholds from DynamicConfig."""
        cfg = get_config()
        pct = self.utilization_pct
        if pct <= cfg.gate_hootl_max:
            return "HOOTL"
        elif pct <= cfg.gate_hotl_max:
            return "HOTL"
        elif pct <= cfg.gate_hitl_async_max:
            return "HITL-async"
        elif pct <= cfg.gate_hitl_sync_max:
            return "HITL-sync"
        else:
            return "FROZEN"

    def can_afford(self, operation: str) -> bool:
        """Dynamic cost lookup."""
        cost = get_risk_cost(operation)
        return self.current_points >= cost

    def deduct(self, operation: str, agent_name: str) -> dict:
        """Deduct risk points. Cost is dynamically looked up."""
        cost = get_risk_cost(operation)
        self.current_points -= cost
        self.consumed_today += cost
        txn = {
            "timestamp": datetime.utcnow().isoformat(),
            "agent": agent_name,
            "operation": operation,
            "cost": cost,
            "remaining": self.current_points,
            "governance_mode": self.governance_mode,
            "utilization_pct": round(self.utilization_pct, 1),
        }
        self.transactions.append(txn)
        return txn

    def apply_trust_reward(self):
        """Dynamic: N consecutive clean days → reward_factor increase (capped)."""
        cfg = get_config()
        self.consecutive_clean_days += 1
        if self.consecutive_clean_days >= cfg.trust_reward_threshold_days:
            self.trust_multiplier = min(
                self.trust_multiplier * cfg.trust_reward_factor,
                cfg.trust_max_multiplier,
            )

    def apply_incident_penalty(self):
        """Dynamic: Severity-1 → penalty_multiplier applied."""
        cfg = get_config()
        self.trust_multiplier = cfg.trust_penalty_multiplier
        self.consecutive_clean_days = 0
        self.current_points = int(self.daily_baseline * cfg.trust_penalty_multiplier)

    def reset_daily(self):
        """Reset budget for new 24h window, applying current trust multiplier."""
        self.current_points = self.effective_budget
        self.consumed_today = 0
        self.last_reset = datetime.utcnow()
        self.transactions = []

    def add_custom_operation(self, name: str, cost: int):
        """Dynamically register a new operation type with its cost."""
        RISK_SCORES[name] = cost


# ──────────────────────────────────────────────
# Action Certificates (Section 6)
# ──────────────────────────────────────────────
class ActionCertificate(BaseModel):
    """
    PRD Section 6 — Digitally signed pre-approved remediation plan.
    Risk score computed dynamically from likelihood x impact.
    """

    # Identity
    certificate_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    version: int = 1
    status: Literal[
        "draft", "pending", "approved", "rejected", "executed", "rolled_back"
    ] = "draft"
    created_by_agent: str = ""
    created_at: datetime = Field(default_factory=datetime.utcnow)
    expires_at: Optional[datetime] = None
    digital_signature: str = ""

    # Target
    system_id: str = os.getenv("HANA_SID", "HXE")
    target_component: str = ""

    # Action
    action_type: str = ""
    action_description: str = ""
    action_parameters: dict = Field(default_factory=dict)
    execution_steps: List[str] = Field(default_factory=list)

    # Justification (WHY)
    trigger_event: str = ""
    root_cause_hypothesis: str = ""
    confidence_level: float = 0.0
    alternatives_considered: List[str] = Field(default_factory=list)
    supporting_evidence: List[str] = Field(default_factory=list)
    rag_sources: List[str] = Field(default_factory=list)

    # Risk Assessment — DYNAMIC
    risk_score: int = 0
    likelihood: int = 1
    impact: int = 1
    blast_radius: str = ""
    risk_budget_cost: int = 0

    # Pre/Post Conditions
    preconditions: List[str] = Field(default_factory=list)
    postconditions: List[str] = Field(default_factory=list)

    # Rollback
    rollback_steps: List[str] = Field(default_factory=list)
    auto_rollback_triggers: List[str] = Field(default_factory=list)
    estimated_rollback_time: str = ""
    data_loss_risk: str = "none"

    # Approval
    approval_required: bool = True
    approved_by: Optional[str] = None
    approved_at: Optional[datetime] = None
    approval_notes: str = ""

    def compute_dynamic_risk(self):
        """Recompute risk_score from current likelihood x impact."""
        self.risk_score = compute_risk_score(self.likelihood, self.impact)
        self.risk_budget_cost = get_risk_cost(self.action_type)

    def sign(self):
        """Generate digital signature from certificate content."""
        payload = json.dumps(self.model_dump(), default=str, sort_keys=True)
        self.digital_signature = hashlib.sha256(payload.encode()).hexdigest()

    def approve(self, approver: str, notes: str = ""):
        self.status = "approved"
        self.approved_by = approver
        self.approved_at = datetime.utcnow()
        self.approval_notes = notes
        self.sign()


# ──────────────────────────────────────────────
# X-Fix Explainable Remediation Reports (Section 11)
# ──────────────────────────────────────────────
class XFixReport(BaseModel):
    """
    PRD Section 11 — Structured, human-readable remediation explanation.
    Maps to ITIL Change Management RFC fields.
    """

    report_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    certificate_id: str = ""
    generated_at: datetime = Field(default_factory=datetime.utcnow)

    # SUMMARY
    summary: str = ""

    # WHY (Root Cause)
    trigger_event: str = ""
    evidence_chain: List[dict] = Field(default_factory=list)
    confidence_score: float = 0.0
    rag_sources: List[str] = Field(default_factory=list)
    alternatives_considered: List[str] = Field(default_factory=list)

    # WHAT (Proposed Actions)
    proposed_steps: List[dict] = Field(default_factory=list)
    estimated_duration: str = ""

    # RISK (Impact Assessment)
    risk_score: int = 0
    blast_radius: str = ""
    affected_processes: List[str] = Field(default_factory=list)
    budget_cost: int = 0
    approval_required: bool = True

    # ROLLBACK
    rollback_triggers: List[str] = Field(default_factory=list)
    rollback_steps: List[str] = Field(default_factory=list)
    estimated_rollback_time: str = ""
    data_loss_risk: str = "none"

    # EXPECTED OUTCOME
    target_metrics: dict = Field(default_factory=dict)
    verification_method: str = ""
    escalation_criteria: str = ""

    def render_text(self) -> str:
        """Render report as human-readable text."""
        lines = [
            "=" * 60,
            f"  X-FIX REPORT - {self.report_id[:8]}",
            "=" * 60,
            "",
            "## SUMMARY",
            self.summary,
            "",
            "## WHY (Root Cause)",
            f"Trigger: {self.trigger_event}",
            f"Confidence: {self.confidence_score:.0%}",
            f"RAG Sources: {', '.join(self.rag_sources) or 'N/A'}",
            "",
            "## WHAT (Proposed Actions)",
        ]
        for i, step in enumerate(self.proposed_steps, 1):
            lines.append(
                f"  {i}. {step.get('description', '')} [{step.get('duration', 'N/A')}]"
            )
        lines += [
            "",
            "## RISK",
            f"Score: {self.risk_score}/25 | Blast Radius: {self.blast_radius}",
            f"Budget Cost: {self.budget_cost} pts | Approval: {'Required' if self.approval_required else 'Auto'}",
            "",
            "## ROLLBACK",
            f"Time: {self.estimated_rollback_time} | Data Loss Risk: {self.data_loss_risk}",
        ]
        for step in self.rollback_steps:
            lines.append(f"  - {step}")
        lines += [
            "",
            "## EXPECTED OUTCOME",
            f"Verification: {self.verification_method}",
            f"Escalation: {self.escalation_criteria}",
            "=" * 60,
        ]
        return "\n".join(lines)


# ──────────────────────────────────────────────
# Policy Engine (Section 4) — DYNAMIC RULES
# ──────────────────────────────────────────────
class PolicyEngine:
    """
    PRD Section 4 — Policy-as-code enforcement.
    All thresholds are dynamic from DynamicConfig.
    Custom rules can be added at runtime.
    """

    _custom_rules: List = []

    @classmethod
    def add_rule(cls, rule_fn):
        """Add a custom policy rule. rule_fn(cert, budget) -> dict or None.
        Return dict with decision/reason to override, or None to continue chain.
        """
        cls._custom_rules.append(rule_fn)

    @classmethod
    def clear_custom_rules(cls):
        cls._custom_rules = []

    @staticmethod
    def evaluate(certificate: ActionCertificate, budget: RiskBudget) -> dict:
        """Evaluate an action certificate against ALL policies (built-in + custom)."""
        cfg = get_config()

        # Custom rules first (highest priority)
        for rule_fn in PolicyEngine._custom_rules:
            result = rule_fn(certificate, budget)
            if result is not None:
                return result

        # Rule 1: Budget sufficiency
        if not budget.can_afford(certificate.action_type):
            return {
                "decision": "DENIED",
                "reason": f"Insufficient risk budget (need {get_risk_cost(certificate.action_type)}, have {budget.current_points})",
                "governance_mode": budget.governance_mode,
            }

        # Rule 2: Governance mode gates
        mode = budget.governance_mode
        if mode == "FROZEN":
            if certificate.action_type not in cfg.frozen_allowed_ops:
                return {
                    "decision": "DENIED",
                    "reason": f"Budget FROZEN - only {cfg.frozen_allowed_ops} allowed",
                    "governance_mode": mode,
                }

        # Rule 3: Dynamic high-risk threshold
        if certificate.risk_score >= cfg.high_risk_threshold:
            return {
                "decision": "NEEDS_APPROVAL",
                "reason": f"High-risk action (score={certificate.risk_score} >= threshold={cfg.high_risk_threshold})",
                "governance_mode": mode,
            }

        # Rule 4: HITL modes require approval
        if mode in ("HITL-async", "HITL-sync"):
            return {
                "decision": "NEEDS_APPROVAL",
                "reason": f"Governance mode {mode} requires human review",
                "governance_mode": mode,
            }

        return {
            "decision": "APPROVED",
            "reason": "All policy checks passed",
            "governance_mode": mode,
        }
