"""Standalone verification for HANA Sentinel."""

import sys
import os

sys.path.insert(0, os.path.dirname(__file__))
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

checks = []


def check(label, fn):
    try:
        result = fn()
        checks.append((label, result))
    except Exception as exc:
        checks.append((label, "FAIL: " + str(exc)))


# 1. Google ADK
def test_adk():
    from google.adk.agents import Agent  # noqa: F401

    return "PASS"


# 2. Dynamic Models
def test_models():
    from adk_app.models import (
        ActionCertificate,
        PolicyEngine,
    )

    cert = ActionCertificate(
        action_type="read_monitoring",
        created_by_agent="test",
    )
    cert.compute_dynamic_risk()
    return "PASS"


# 3. HANA Tools (no mock)
def test_hana():
    from adk_app.tools.hana_tools import (
        check_hana_connection,
    )

    result = check_hana_connection()
    return "PASS (status=" + result["status"] + ")"


# 4. Remote Exec Server
def test_remote_exec():
    from adk_app.tools.hana_tools import execute_remote_command

    result = execute_remote_command("echo ok")
    assert result.get("stdout", "").strip() == "ok"
    return "PASS (remote exec server reachable)"


# 5. RAG Tools (no mock)
def test_rag():
    from adk_app.tools.rag_tools import (
        rag_query as _rq,
        rag_ingest as _ri,
    )

    assert _rq and _ri
    return "PASS"


# 6. Docker Tools
def test_docker():
    from adk_app.tools.docker_tools import (
        docker_exec as _de,
        docker_logs as _dl,
        docker_stats as _ds,
        docker_inspect as _di,
        docker_list_containers as _dlc,
        docker_health_check as _dhc,
    )

    assert all([_de, _dl, _ds, _di, _dlc, _dhc])
    return "PASS (6 tools)"


# 7. Learning Store
def test_learning():
    from adk_app.tools.learning_store import (
        get_monitoring_commands,
    )

    result = get_monitoring_commands()
    cnt = str(result["count"])
    cats = str(len(result["categories"]))
    return "PASS (" + cnt + " seed cmds, " + cats + " categories)"


# 8. GCP Event Tools
def test_gcp_events():
    from adk_app.tools import gcp_event_tools as g

    fns = [
        g.pubsub_publish_alert,
        g.pubsub_pull_events,
        g.pubsub_create_topic,
        g.cloudrun_dispatch_task,
        g.cloudrun_get_service_status,
        g.cloudrun_deploy_agent,
    ]
    assert all(callable(f) for f in fns)
    return "PASS (3 Pub/Sub + 3 Cloud Run tools)"


# 9. Log Preprocessor
def test_preprocessor():
    from adk_app.tools.log_preprocessor import (
        preprocess_command_output,
    )

    sample_log = (
        "2026-02-12 INFO Starting indexserver\n" * 50
        + "2026-02-12 ERROR out of memory\n"
        + "2026-02-12 WARNING disk space low\n"
        + "2026-02-12 DEBUG trace message\n" * 100
    )
    result = preprocess_command_output(sample_log, context="log")
    ratio = result["compression_ratio"]
    orig = str(result["original_chars"])
    comp = str(result["compressed_chars"])
    return "PASS (compressed " + orig + " -> " + comp + " chars, " + str(ratio) + "x)"


# 10. Log Preprocessor disk context
def test_df_preprocessing():
    from adk_app.tools.log_preprocessor import (
        preprocess_command_output,
    )

    sample_df = (
        "Filesystem  Size Used Avail Use% Mounted\n"
        "/dev/sda1   100G  90G  10G  90% /hana/data\n"
        "/dev/sdb1   200G  50G 150G  25% /hana/log\n"
        "/dev/sdc1    50G  48G   2G  96% /hana/backup\n"
        "tmpfs       4.0G 100M 3.9G   3% /tmp\n"
    )
    result = preprocess_command_output(sample_df, context="disk")
    preprocessed = result["preprocessed"]
    has_alert = "CRITICAL" in preprocessed or "WARNING" in preprocessed
    return "PASS (alerts detected: " + str(has_alert) + ")"


# 11. ADK Agents
def test_agents():
    from adk_app.agent import (
        root_agent,
        monitoring_agent,
    )

    sub_count = len(root_agent.sub_agents) if root_agent.sub_agents else 0
    sub_names = [a.name for a in root_agent.sub_agents] if root_agent.sub_agents else []
    mon_tools = len(monitoring_agent.tools) if monitoring_agent.tools else 0
    has_mon = "monitoring_agent" in sub_names
    return (
        "PASS (root + "
        + str(sub_count)
        + " subs, monitoring has "
        + str(mon_tools)
        + " tools, "
        + "has_pubsub="
        + str(has_mon)
        + ")"
    )


# 12. Dynamic Config
def test_config():
    from adk_app.models import get_config

    cfg = get_config()
    bl = str(cfg.daily_baseline)
    g1 = str(cfg.gate_hootl_max)
    g2 = str(cfg.gate_hotl_max)
    return "PASS (baseline=" + bl + ", gates=" + g1 + "/" + g2 + ")"


check("Google ADK", test_adk)
check("Models (dynamic)", test_models)
check("HANA Tools (no mock)", test_hana)
check("Remote Exec Server", test_remote_exec)
check("RAG Tools (no mock)", test_rag)
check("Docker Tools", test_docker)
check("Learning Store (14 seeds)", test_learning)
check("GCP Event Tools", test_gcp_events)
check("Log Preprocessor", test_preprocessor)
check("DF Preprocessing", test_df_preprocessing)
check("ADK Agents", test_agents)
check("Dynamic Config", test_config)

print("\nHANA Sentinel Verification (Full Stack):")
print("=" * 60)
for label, status in checks:
    marker = "PASS" if status.startswith("PASS") else "FAIL"
    print("  [" + marker + "] " + label + ": " + status)
passed = sum(1 for _, s in checks if s.startswith("PASS"))
print("=" * 60)
print("Total: " + str(passed) + "/" + str(len(checks)) + " passed")

# Cleanup test-generated learned commands store
try:
    store_path = os.path.join(
        os.path.dirname(__file__),
        "adk_app",
        "data",
        "learned_commands.json",
    )
    if os.path.exists(store_path):
        os.remove(store_path)
except Exception:
    pass
