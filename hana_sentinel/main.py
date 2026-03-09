"""
HANA Sentinel — Main entry point.
Provides multiple ways to run the system:
1. `adk run adk_app` — Google ADK CLI (interactive chat)
2. `python main.py api` — FastAPI REST server
3. `python main.py chaos` — Run chaos engineering suite
4. `python main.py verify` — Verify setup
"""

import sys
import os
import json

# Add parent to path for imports
sys.path.insert(0, os.path.dirname(__file__))

# Load .env (override=True ensures .env values win over existing shell env)
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), ".env"), override=True)


def run_api():
    """Start FastAPI REST server."""
    import uvicorn
    from adk_app.api import app

    print("Starting HANA Sentinel API on http://localhost:8000")
    print("API docs at http://localhost:8000/docs")
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")


def run_chaos(scenarios=None):
    """Run chaos engineering suite."""
    from adk_app.chaos import run_chaos_suite

    print("Running HANA Sentinel Chaos Engineering Suite")
    results = run_chaos_suite(scenarios)
    print(json.dumps(results, indent=2))
    print(f"\n  Passed: {results['passed']}/{results['total']}")
    if results["failed"] > 0:
        print(f"  ❌ Failed: {results['failed']}")


def run_verify():
    """Verify setup and imports."""
    print("🔍 HANA Sentinel — Setup Verification")
    print("=" * 50)

    checks = []

    # 1. Google ADK
    try:
        from google.adk.agents import Agent

        checks.append(("Google ADK", "✅"))
    except ImportError:
        checks.append(("Google ADK", "❌ pip install google-adk"))

    # 2. Models
    try:
        from adk_app.models import (
            RiskBudget,
            ActionCertificate,
            XFixReport,
            PolicyEngine,
        )

        budget = RiskBudget()
        cert = ActionCertificate(action_type="read_monitoring", created_by_agent="test")
        xfix = XFixReport(summary="Test report")
        decision = PolicyEngine.evaluate(cert, budget)
        checks.append(("Models (RiskBudget, ActionCert, X-Fix, Policy)", "✅"))
    except Exception as e:
        checks.append(("Models", f"❌ {e}"))

    # 3. HANA Tools
    try:
        from adk_app.tools.hana_tools import query_hana, check_hana_connection

        result = query_hana("SELECT * FROM M_SERVICES")
        checks.append(
            (
                "HANA Tools",
                f"✅ ({result.get('source', 'unknown')} mode, {result.get('row_count', 0)} rows)",
            )
        )
    except Exception as e:
        checks.append(("HANA Tools", f"❌ {e}"))

    # 4. Remote Exec
    try:
        from adk_app.tools.hana_tools import execute_remote_command

        result = execute_remote_command("echo ok")
        checks.append(("Remote Exec", f"✅ (stdout={result.get('stdout', '').strip()})"))
    except Exception as e:
        checks.append(("Remote Exec", f"❌ {e}"))

    # 5. RAG Tools
    try:
        from adk_app.tools.rag_tools import rag_query

        result = rag_query("How to fix backup failure in SAP HANA?")
        checks.append(
            (
                "RAG Tools",
                f"✅ ({result.get('source', 'unknown')}, confidence={result.get('confidence', 0):.0%})",
            )
        )
    except Exception as e:
        checks.append(("RAG Tools", f"❌ {e}"))

    # 6. ADK Agent Definitions
    try:
        from adk_app.agent import root_agent

        sub_count = len(root_agent.sub_agents) if root_agent.sub_agents else 0
        checks.append(("ADK Agents", f"✅ (root + {sub_count} sub-agents)"))
    except Exception as e:
        checks.append(("ADK Agents", f"❌ {e}"))

    # 7. FastAPI
    try:
        from adk_app.api import app

        route_count = len(app.routes)
        checks.append(("FastAPI REST API", f"✅ ({route_count} routes)"))
    except Exception as e:
        checks.append(("FastAPI REST API", f"❌ {e}"))

    # 8. Chaos Suite
    try:
        from adk_app.chaos import ALL_SCENARIOS

        checks.append(("Chaos Engineering", f"✅ ({len(ALL_SCENARIOS)} scenarios)"))
    except Exception as e:
        checks.append(("Chaos Engineering", f"❌ {e}"))

    # Print results
    for name, status in checks:
        print(f"  {status}  {name}")

    passed = sum(1 for _, s in checks if s.startswith("✅"))
    print(f"\n{'=' * 50}")
    print(f"  {passed}/{len(checks)} checks passed")

    # Risk Budget Demo
    print(f"\n📊 Risk Budget Demo:")
    budget = RiskBudget()
    print(f"  Initial: {budget.current_points} pts, Mode: {budget.governance_mode}")
    budget.deduct("read_monitoring", "health_agent")
    budget.deduct("backup_execution", "backup_agent")
    budget.deduct("service_restart", "recovery_agent")
    print(
        f"  After 3 ops: {budget.current_points} pts ({budget.utilization_pct:.0f}% used), Mode: {budget.governance_mode}"
    )

    # X-Fix Report Demo
    print(f"\n📋 X-Fix Report Demo:")
    xfix = XFixReport(
        summary="Indexserver crash detected — automatic restart initiated",
        trigger_event="M_SERVICES shows indexserver INACTIVE",
        confidence_score=0.95,
        rag_sources=["SAP Note 1999998"],
        proposed_steps=[
            {
                "description": "ALTER SYSTEM START SERVICE indexserver",
                "duration": "30s",
            },
            {"description": "Verify service status via M_SERVICES", "duration": "10s"},
        ],
        risk_score=6,
        blast_radius="Single service",
        budget_cost=6,
        rollback_steps=["sapcontrol RestartService", "Manual restart via HDB"],
        estimated_rollback_time="2 minutes",
        verification_method="Query M_SERVICES for ACTIVE_STATUS = 'YES'",
    )
    print(xfix.render_text())

    return passed == len(checks)


if __name__ == "__main__":
    if len(sys.argv) > 1:
        cmd = sys.argv[1].lower()
        if cmd == "api":
            run_api()
        elif cmd == "chaos":
            scenarios = sys.argv[2:] if len(sys.argv) > 2 else None
            run_chaos(scenarios)
        elif cmd == "verify":
            run_verify()
        else:
            print(f"Unknown command: {cmd}")
            print("Usage: python main.py [api|chaos|verify]")
    else:
        print("HANA Sentinel — Autonomous AI for SAP HANA Operations")
        print("=" * 50)
        print("Commands:")
        print("  python main.py verify  — Verify setup")
        print("  python main.py api     — Start REST API")
        print("  python main.py chaos   — Run chaos tests")
        print("  adk run adk_app        — Interactive ADK chat")
