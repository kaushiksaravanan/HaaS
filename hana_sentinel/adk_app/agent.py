"""
HANA Sentinel — ADK Agent Definitions.
Each sub-agent is a google.adk.agents.Agent with specialized tools and instructions.
The root_agent is the Supervisor that orchestrates via sub_agents.
PRD Sections: 4, 7, 9, 10

Includes: health, backup, recovery, sql_tuning, capacity, rag, browser, verifier, monitoring
"""

import os
import logging

from google.adk.agents import Agent
from google.adk.models import LiteLlm

_logger = logging.getLogger(__name__)

# ──────────────────────────────────────────────
# Shared LLM configuration for all ADK agents.
# Uses GenAI Hub proxy (Hyperspace AI) via LiteLlm.
# Falls back to local proxy at localhost:6655.
# ──────────────────────────────────────────────
_PROXY_URL = os.getenv("GENAIHUB_PROXY_URL", "http://localhost:6655")
_PROXY_KEY = os.getenv("GENAIHUB_PROXY_API_KEY", "d3d25b98-d27a-4d9c-8f95-5d39731e3a3a")
_LLM_MODEL = os.getenv("ADK_LLM_MODEL", "openai/gpt-4o")

_sentinel_llm = LiteLlm(
    model=_LLM_MODEL,
    api_key=_PROXY_KEY,
    api_base=f"{_PROXY_URL}/v1",
)
_logger.info("ADK agents using model=%s via proxy=%s", _LLM_MODEL, _PROXY_URL)

from .tools.hana_tools import query_hana, execute_hana_sql, check_hana_connection, execute_remote_command
from .tools.rag_tools import rag_query, rag_ingest
from .tools.docker_tools import (
    docker_exec,
    docker_logs,
    docker_stats,
    docker_inspect,
    docker_list_containers,
    docker_health_check,
)
from .tools.learning_store import (
    get_monitoring_commands,
    record_command_result,
    learn_new_commands,
    add_monitoring_command,
    get_monitoring_script,
)
from .tools.gcp_event_tools import (
    pubsub_publish_alert,
    pubsub_pull_events,
    pubsub_create_topic,
    cloudrun_dispatch_task,
    cloudrun_get_service_status,
    cloudrun_deploy_agent,
)
from .tools.log_preprocessor import (
    preprocess_command_output,
    check_hdb_storage,
)
from .tools.analysis_tools import (
    run_analysis_script,
    parse_analysis_errors,
    discover_hana_schema,
    fix_analysis_script,
    run_and_learn_analysis,
)

# ──────────────────────────────────────────────
# Instance Agent Tools (for vlgdbzo3 HANA instance)
# ──────────────────────────────────────────────
from .agents.instance_monitor_agent import (
    INSTANCE_MONITOR_TOOLS,
    instance_monitor_agent_tools,
    instance_monitor_agent_instructions,
)
from .agents.instance_backup_agent import (
    INSTANCE_BACKUP_TOOLS,
    instance_backup_agent_tools,
    instance_backup_agent_instructions,
)
from .agents.instance_healing_agent import (
    INSTANCE_HEALING_TOOLS,
    instance_healing_agent_tools,
    instance_healing_agent_instructions,
)


# ──────────────────────────────────────────────
# Browser-Use Tool Function (NO MOCK)
# ──────────────────────────────────────────────
def browser_navigate(url: str, task_description: str) -> dict:
    """Navigate to a URL and perform a task using browser automation (browser-use).
    Used for SAP web interfaces that lack programmatic APIs.
    PRD Section 10.
    NEVER returns fabricated data — performs real browser automation or returns error.

    Args:
        url (str): The URL to navigate to.
        task_description (str): Description of what to extract or do on the page.

    Returns:
        dict: status and extracted data or action result.
    """
    import os

    # Domain allowlist — security rule from PRD
    allowed_domains = os.getenv(
        "BROWSER_ALLOWED_DOMAINS",
        "support.sap.com,me.sap.com,launchpad.support.sap.com",
    ).split(",")

    from urllib.parse import urlparse

    parsed = urlparse(url)
    domain = parsed.hostname or ""
    if not any(domain.endswith(d.strip()) for d in allowed_domains):
        return {
            "status": "error",
            "error_message": f"Domain '{domain}' not in allowed list: {allowed_domains}",
        }

    try:
        from browser_use import Agent as BrowserAgent, BrowserProfile
    except ImportError:
        return {
            "status": "error",
            "error_message": (
                "browser-use not installed. "
                "Install via: pip install browser-use"
            ),
        }

    try:
        from .chat_genaihub import ChatGenAIHub
        from .agents.browser_agent import _safe_copy_chrome_profile
        import asyncio

        # Use GenAIHub (SAP AI Core) instead of Google Generative AI
        llm = ChatGenAIHub()

        # Safe copy of Chrome profile (browser-use prefix skips its own copytree)
        profile = BrowserProfile(
            headless=False,
            channel="chrome",
            user_data_dir=_safe_copy_chrome_profile(),
            disable_security=False,
            keep_alive=False,
        )

        browser_task = f"Navigate to {url} and {task_description}"
        agent = BrowserAgent(task=browser_task, llm=llm, browser_profile=profile)

        # Run the browser agent
        loop = asyncio.new_event_loop()
        try:
            result = loop.run_until_complete(agent.run())
        finally:
            loop.close()

        return {
            "status": "success",
            "source": "browser_use",
            "url": url,
            "extracted_data": result
            if isinstance(result, (dict, str))
            else str(result),
        }
    except Exception as e:
        return {
            "status": "error",
            "error_message": f"Browser automation failed: {e}",
            "url": url,
        }


def browser_verify_page(url: str, expected_content: str) -> dict:
    """Verify that a webpage contains expected content using browser automation.
    Used by the Verifier Agent to validate UI state after remediation.

    Args:
        url (str): The URL to verify.
        expected_content (str): Content or state expected on the page (text, element, status indicator).

    Returns:
        dict: verification_passed (bool), page_title, found_content, screenshot_path.
    """
    import os

    try:
        from browser_use import Agent as BrowserAgent, BrowserProfile
    except ImportError:
        return {
            "status": "error",
            "error_message": "browser-use not installed. Install via: pip install browser-use",
        }

    try:
        from .chat_genaihub import ChatGenAIHub
        from .agents.browser_agent import _safe_copy_chrome_profile
        import asyncio

        # Use GenAIHub (SAP AI Core) instead of Google Generative AI
        llm = ChatGenAIHub()

        # Safe copy of Chrome profile (browser-use prefix skips its own copytree)
        profile = BrowserProfile(
            headless=False,
            channel="chrome",
            user_data_dir=_safe_copy_chrome_profile(),
            disable_security=False,
            keep_alive=False,
        )

        verify_task = (
            f"Navigate to {url}. "
            f"Check if the following is true: {expected_content}. "
            "Return a JSON with: 'found' (boolean), 'page_title', 'relevant_text' (the matching content), "
            "and 'screenshot_description' (describe what you see)."
        )
        agent = BrowserAgent(task=verify_task, llm=llm, browser_profile=profile)

        loop = asyncio.new_event_loop()
        try:
            result = loop.run_until_complete(agent.run())
        finally:
            loop.close()

        is_passed = False
        if isinstance(result, dict):
            is_passed = result.get("found", False)
        elif isinstance(result, str):
            is_passed = (
                "true" in result.lower()
                or "found" in result.lower()
                or "pass" in result.lower()
            )

        return {
            "status": "success",
            "source": "browser_use",
            "verification_passed": is_passed,
            "url": url,
            "expected": expected_content,
            "result": result if isinstance(result, (dict, str)) else str(result),
        }
    except Exception as e:
        return {
            "status": "error",
            "error_message": f"Browser verification failed: {e}",
            "url": url,
        }


def verify_hana_cockpit_health(cockpit_url: str = "") -> dict:
    """Verify SAP HANA Cockpit shows healthy system status via browser automation.
    Cross-validates browser-visible state against API/SQL data.

    Args:
        cockpit_url (str): URL of HANA Cockpit. If empty, reads from env HANA_COCKPIT_URL.

    Returns:
        dict: verification result with cockpit-visible health details.
    """
    import os

    if not cockpit_url:
        cockpit_url = os.getenv("HANA_COCKPIT_URL", "")
    if not cockpit_url:
        return {
            "status": "error",
            "error_message": "HANA_COCKPIT_URL not configured. Set via env or provide cockpit_url parameter.",
        }

    return browser_verify_page(
        url=cockpit_url,
        expected_content="All services are running (GREEN status). No critical alerts visible. System overview shows healthy state.",
    )


def verify_sap_note_applied(note_number: str) -> dict:
    """Verify a specific SAP Note is applied by checking SAP Support Launchpad.

    Args:
        note_number (str): The SAP Note number (e.g., '3691059').

    Returns:
        dict: verification result indicating if the note was found and its status.
    """
    import os

    base_url = os.getenv("SAP_SUPPORT_URL", "https://me.sap.com/notes")
    url = f"{base_url}/{note_number}"
    return browser_verify_page(
        url=url,
        expected_content=f"SAP Note {note_number} details are visible. Extract: title, category, priority, affected component, and any correction instructions.",
    )


# ──────────────────────────────────────────────
# 7.1 Health Monitor Agent
# ──────────────────────────────────────────────
health_agent = Agent(
    name="health_agent",
    model=_sentinel_llm,
    description="Monitors SAP HANA system health via M_* monitoring views. Generates structured health assessments covering services, memory, disk, CPU, alerts, and system replication.",
    instruction="""You are the HANA Sentinel Health Monitor Agent.

Your responsibilities:
1. Continuously assess SAP HANA system health by querying monitoring views.
2. Generate structured health reports covering: services, memory, disk, CPU, alerts, replication.
3. Flag anomalies and escalate to the Supervisor when thresholds are breached.

Key HANA monitoring queries you should use:
- Services: SELECT SERVICE_NAME, ACTIVE_STATUS, HOST, PORT FROM M_SERVICES
- CPU/Memory: SELECT HOST, CPU_USER_PCT, CPU_SYSTEM_PCT, MEMORY_USED_PCT FROM M_HOST_RESOURCE_UTILIZATION
- Memory detail: SELECT SERVICE_NAME, TOTAL_MEMORY_USED_SIZE, EFFECTIVE_ALLOCATION_LIMIT FROM M_SERVICE_MEMORY
- Disk: SELECT USAGE_TYPE, USED_SIZE, TOTAL_SIZE FROM M_DISK_USAGE
- Alerts: SELECT ALERT_ID, ALERT_RATING, ALERT_DETAILS FROM STATISTICS_CURRENT_ALERTS WHERE ALERT_RATING >= 3
- Replication: SELECT SITE_ID, SITE_NAME, REPLICATION_STATUS FROM M_SYSTEM_REPLICATION
- Load history: SELECT TIME, CPU, MEMORY_USED FROM M_LOAD_HISTORY_SERVICE ORDER BY TIME DESC LIMIT 10

Thresholds are DYNAMIC — read from system configuration. Defaults:
- CPU > 80%: WARNING, CPU > 95%: CRITICAL
- Memory > 85%: WARNING, Memory > 95%: CRITICAL
- Disk > 80%: WARNING, Disk > 90%: CRITICAL
- Any service not GREEN/YES: CRITICAL

Always return a structured assessment with overall_status (OK/WARNING/CRITICAL), component statuses, and recommendations.
Risk cost: 1 point (read-only monitoring).
""",
    tools=[query_hana, check_hana_connection],
)


# ──────────────────────────────────────────────
# 7.2 Backup Agent
# ──────────────────────────────────────────────
backup_agent = Agent(
    name="backup_agent",
    model=_sentinel_llm,
    description="Manages the entire SAP HANA backup lifecycle: scheduling, execution, verification, catalog housekeeping, and failure recovery.",
    instruction="""You are the HANA Sentinel Backup Agent.

Your responsibilities:
1. Check backup status and compliance via M_BACKUP_CATALOG.
2. Trigger data and log backups when needed.
3. Verify backup integrity.
4. Manage backup catalog housekeeping.

Key queries:
- Last backup: SELECT TOP 1 BACKUP_ID, STATE_NAME, SYS_END_TIME, ENTRY_TYPE_NAME FROM M_BACKUP_CATALOG WHERE ENTRY_TYPE_NAME = 'complete data backup' ORDER BY SYS_END_TIME DESC
- Backup history: SELECT BACKUP_ID, STATE_NAME, SYS_START_TIME, SYS_END_TIME, ENTRY_TYPE_NAME FROM M_BACKUP_CATALOG ORDER BY SYS_END_TIME DESC
- Trigger backup: BACKUP DATA USING FILE ('backup_prefix')
- Trigger log backup: BACKUP DATA USING FILE ('log_backup_prefix')

Rules:
- Flag if last full backup exceeds max age (configurable, default: 24 hours).
- Flag if any backup has STATE_NAME != 'successful'.
- Before triggering backup, verify basepath_logbackup is configured (use execute_remote_command to check global.ini).
- Risk cost: Read catalog = 1 pt, Trigger differential = 6 pts, Trigger full = 6 pts.
""",
    tools=[query_hana, execute_hana_sql, execute_remote_command],
)


# ──────────────────────────────────────────────
# 7.3 Recovery Agent
# ──────────────────────────────────────────────
recovery_agent = Agent(
    name="recovery_agent",
    model=_sentinel_llm,
    description="Detects service failures and executes recovery procedures, from simple service restarts to system replication takeover.",
    instruction="""You are the HANA Sentinel Recovery Agent.

Your responsibilities:
1. Detect service failures via M_SERVICES and sapcontrol.
2. Execute recovery: service restart, ALTER SYSTEM START SERVICE, or escalate to failover.
3. Validate recovery by re-checking service status post-action.

Key operations:
- Check services: query_hana("SELECT SERVICE_NAME, ACTIVE_STATUS FROM M_SERVICES")
- Check sapcontrol: execute_remote_command("sapcontrol -nr 02 -function GetProcessList")
- Restart: execute_remote_command("sapcontrol -nr 02 -function RestartService", admin_override=True)
- SQL restart: execute_hana_sql("ALTER SYSTEM START SERVICE indexserver")

Recovery escalation:
1. First: ALTER SYSTEM START SERVICE (risk: configurable, default 6)
2. Second: sapcontrol RestartService (risk: configurable, default 12)
3. Last resort: System replication takeover (risk: configurable, default 20, ALWAYS needs human approval)

Always generate an Action Certificate before executing any recovery action.
""",
    tools=[
        query_hana,
        execute_hana_sql,
        execute_remote_command,
    ],
)


# ──────────────────────────────────────────────
# 7.4 SQL Tuning Agent
# ──────────────────────────────────────────────
sql_tuning_agent = Agent(
    name="sql_tuning_agent",
    model=_sentinel_llm,
    description="Identifies expensive SQL statements, analyzes execution plans, and recommends or executes optimizations.",
    instruction="""You are the HANA Sentinel SQL Tuning Agent.

Your responsibilities:
1. Find expensive SQL statements.
2. Analyze execution plans.
3. Recommend or create indexes.
4. Query RAG for relevant SAP Notes before recommending.

Key queries:
- Expensive: SELECT TOP 10 STATEMENT_STRING, DURATION_MICROSEC, CPU_TIME, START_TIME FROM M_EXPENSIVE_STATEMENTS ORDER BY DURATION_MICROSEC DESC
- Plan cache: SELECT STATEMENT_STRING, AVG_EXECUTION_TIME, EXECUTION_COUNT, TOTAL_EXECUTION_TIME FROM M_SQL_PLAN_CACHE ORDER BY TOTAL_EXECUTION_TIME DESC
- Active: SELECT STATEMENT_STRING, DURATION_MICROSEC FROM M_ACTIVE_STATEMENTS
- Existing indexes: SELECT SCHEMA_NAME, TABLE_NAME, INDEX_NAME, INDEX_TYPE, CONSTRAINT FROM INDEXES WHERE SCHEMA_NAME NOT LIKE '_SYS%' ORDER BY SCHEMA_NAME, TABLE_NAME
- Table sizes: SELECT SCHEMA_NAME, TABLE_NAME, RECORD_COUNT, TABLE_SIZE FROM M_CS_TABLES WHERE SCHEMA_NAME NOT LIKE '_SYS%' ORDER BY TABLE_SIZE DESC LIMIT 30

For index suggestions:
1. ALWAYS query the database first — collect expensive statements, plan cache stats, existing indexes, and table sizes.
2. Analyze the actual slow queries to find missing indexes (look for full table scans on large tables, frequent WHERE clauses without indexes).
3. Cross-reference with existing indexes to avoid duplicates.
4. Provide specific CREATE INDEX DDL for each suggestion with reasoning.
5. Query RAG with the problematic SQL pattern to find relevant SAP Notes.
6. Include RAG sources in your recommendations.

NEVER suggest indexes without first querying the database for real data.
Risk cost: Read = 1 pt, Create index = 8 pts (needs approval for hints).
""",
    tools=[query_hana, execute_hana_sql, rag_query],
)


# ──────────────────────────────────────────────
# 7.5 Capacity Agent
# ──────────────────────────────────────────────
capacity_agent = Agent(
    name="capacity_agent",
    model=_sentinel_llm,
    description="Tracks disk, memory, and table growth trends. Predicts capacity thresholds and manages global.ini configuration compliance.",
    instruction="""You are the HANA Sentinel Capacity Agent.

Your responsibilities:
1. Monitor disk and memory usage trends.
2. Predict capacity exhaustion.
3. Manage global.ini compliance (PRD Section 8).
4. Clean trace files when needed.

Key queries:
- Disk: SELECT USAGE_TYPE, USED_SIZE, TOTAL_SIZE FROM M_DISK_USAGE
- Memory: SELECT TOTAL_MEMORY_USED_SIZE, EFFECTIVE_ALLOCATION_LIMIT FROM M_SERVICE_MEMORY
- Config: execute_remote_command("cat /usr/sap/SID/SYS/global/hdb/custom/config/global.ini")
- OS resources: execute_remote_command("free -m && df -h")
- Custom OS command: execute_remote_command("df -h /data /log /backup")

global.ini compliance (Section 8):
Check global.ini regularly via execute_remote_command. Required entries are configurable.
If entries are missing, report them. Risk cost: Read = 1 pt, Config update = 6 pts.
""",
    tools=[
        query_hana,
        execute_remote_command,
    ],
)


# ──────────────────────────────────────────────
# 9. RAG Agent (Support Assistant Role)
# ──────────────────────────────────────────────
rag_agent = Agent(
    name="rag_agent",
    model=_sentinel_llm,
    description="SAP knowledge retrieval and support assistant. Queries RAG knowledge base grounded in SAP Notes, EWA reports, admin guides, and Patch Day bulletins.",
    instruction="""You are the HANA Sentinel RAG Agent — the SAP knowledge expert.

Dual role:
1. Agent Grounding: Other agents query you for SAP documentation before making decisions.
2. Support Assistant: Basis admins query you directly for SAP knowledge.

Always:
- Ground answers in SAP documentation (SAP Notes, admin guides).
- Include source citations with SAP Note numbers.
- Provide confidence scores.
- If unsure, say so and recommend checking SAP Support Portal.

You can also ingest new documents into the knowledge base using rag_ingest.
Risk cost: 1 pt (read-only advisory).
""",
    tools=[rag_query, rag_ingest],
)


# ──────────────────────────────────────────────
# 10. Browser-Use Agent
# ──────────────────────────────────────────────
browser_agent = Agent(
    name="browser_agent",
    model=_sentinel_llm,
    description="Automates interaction with SAP web interfaces using browser automation. Extracts data from SAP Support Portal, HANA Cockpit, and EWA reports. NEVER fabricates data.",
    instruction="""You are the HANA Sentinel Browser-Use Agent.

Your responsibilities:
1. SAP Security Patch Day monitoring — extract security notes from support.sap.com
2. HANA Cockpit data extraction — extract health dashboards and KPIs
3. EWA report retrieval — extract from Solution Manager
4. SAP Note detail extraction — get remediation steps for specific notes

Security rules (NON-NEGOTIABLE):
- ONLY navigate to allowed domains (configurable via BROWSER_ALLOWED_DOMAINS)
- NEVER expose credentials in logs
- Always capture audit screenshots
- NEVER return fabricated/mock data

Risk cost: Navigation + extraction = 6 pts (medium).
""",
    tools=[browser_navigate, rag_ingest],
)


# ──────────────────────────────────────────────
# 11. Verifier Agent (browser-use content verification)
# ──────────────────────────────────────────────
verifier_agent = Agent(
    name="verifier_agent",
    model=_sentinel_llm,
    description="Verifies remediation outcomes using browser automation and cross-validation. Checks SAP HANA Cockpit, SAP Support Portal, and other web UIs to confirm that actions had the expected effect. Uses browser-use for real verification.",
    instruction="""You are the HANA Sentinel Verifier Agent.

Your role is to VERIFY that actions taken by other agents produced the expected results.
You use browser automation AND SQL/remote exec tools to cross-validate state.

Verification workflows:
1. POST-REMEDIATION: After recovery/backup/security actions:
   - Check HANA Cockpit for expected system state via browser
   - Cross-validate by querying M_SERVICES, M_BACKUP_CATALOG via SQL
   - Compare browser-visible state vs API state

2. SAP NOTE VERIFICATION: After patching:
   - Navigate to SAP Support Portal to confirm note details
   - Verify applied patches via HANA version query
   - Cross-reference with RAG knowledge base

3. CONFIGURATION VERIFICATION: After global.ini changes:
   - Read the file via remote exec
   - Verify via HANA M_INIFILE_CONTENTS view
   - Check Cockpit shows updated config

4. SECURITY VERIFICATION: After privilege changes:
   - Query EFFECTIVE_PRIVILEGES to confirm changes
   - Check audit trail is recording
   - Verify encryption status via browser if applicable

Verification output must always include:
- verification_passed: true/false
- method: How you verified (browser, sql, remote_exec, cross-validated)
- evidence: What you found
- discrepancies: Any differences between data sources
- confidence: How confident you are in the verification

NEVER fabricate verification results. If you cannot verify, say so explicitly.
Risk cost: 1-2 pts (read-only verification).
""",
    tools=[
        browser_verify_page,
        verify_hana_cockpit_health,
        verify_sap_note_applied,
        query_hana,
        check_hana_connection,
        execute_remote_command,
        rag_query,
    ],
)


# ──────────────────────────────────────────────
# 12. Docker Monitoring Agent (Pub/Sub + Cloud Run + Log Preprocessing)
# ──────────────────────────────────────────────
monitoring_agent = Agent(
    name="monitoring_agent",
    model=_sentinel_llm,
    description=(
        "Docker container monitoring with Pub/Sub events, "
        "Cloud Run dispatch, dynamic learning, "
        "log preprocessing, and HDB storage checks."
    ),
    instruction="""You are the HANA Sentinel Docker Monitoring Agent.

You run inside Docker/Podman containers that host SAP HANA and execute a DYNAMIC set
of monitoring commands. Your command set GROWS OVER TIME
as you learn from incidents.

=== CRITICAL: LOG PREPROCESSING ===
ALWAYS preprocess large outputs before analyzing them.
This protects your context.
1. After docker_exec or docker_logs, call preprocess_command_output(output, context).
   context values: 'log', 'disk', 'process', 'trace', 'hdbsql', 'general'
2. Use the 'preprocessed' field for your analysis, NOT the raw output.
3. For disk checks: preprocess_command_output(output, context='disk') auto-parses df.
4. For process listings: context='process' filters to HANA processes only.

=== HDB STORAGE MONITORING (PRIORITY) ===
You MUST check HDB storage paths on every monitoring cycle:
- check_hdb_storage() — checks /hana/data, /hana/log,
  /hana/backup, /hana/shared
- Reports alerts (CRITICAL, WARNING) based on usage percentage
- Also checks inode usage which can cause silent failures
Seed commands include: HDB data/log/backup/shared volume, inode, trace size checks.

=== CORE WORKFLOW ===
1. check_hdb_storage() — HDB path and storage check FIRST
2. docker_health_check() — overall container health
3. get_monitoring_commands() — load dynamic command set
4. For each command:
   a. docker_exec(container, command)
   b. preprocess_command_output(output, context) — compress for analysis
   c. record_command_result(id, success, preprocessed)
5. Analyze preprocessed outputs for anomalies
6. If issues found: pubsub_publish_alert() + escalate to Supervisor
7. If resolved: learn_new_commands() to capture what worked

=== PUB/SUB EVENT INTEGRATION ===
- pubsub_publish_alert(type, severity, message) — publish alerts to downstream
- pubsub_pull_events() — check for external triggers/alerts
- pubsub_create_topic() — create new event topics
Publish alerts for: disk critical, service down, OOM,
backup failures, security issues.

=== CLOUD RUN DISPATCH ===
- cloudrun_dispatch_task(task_type, payload) — offload heavy tasks
- cloudrun_get_service_status() — check agent service health
- cloudrun_deploy_agent() — deploy/update agent containers
Use Cloud Run for: heavy log analysis, batch monitoring, chaos testing.

=== LEARNING LOOP ===
After any incident is resolved, capture the commands that helped:
  learn_new_commands(incident_summary, diagnostic_cmds, remediation_cmds)
These are AUTOMATICALLY added to your monitoring rotation for future cycles.

=== COMMAND MANAGEMENT ===
- get_monitoring_commands() — dynamic command set (sorted by priority)
- add_monitoring_command() — manually add a new check
- get_monitoring_script() — export as standalone bash script
- Commands with >80% failure rate after 10+ runs are auto-disabled

Risk cost: 1 pt per cycle (read-only diagnostic).
""",
    tools=[
        # Container Tools
        docker_exec,
        docker_logs,
        docker_stats,
        docker_inspect,
        docker_list_containers,
        docker_health_check,
        # Learning Store
        get_monitoring_commands,
        record_command_result,
        learn_new_commands,
        add_monitoring_command,
        get_monitoring_script,
        # Pub/Sub Events
        pubsub_publish_alert,
        pubsub_pull_events,
        pubsub_create_topic,
        # Cloud Run Dispatch
        cloudrun_dispatch_task,
        cloudrun_get_service_status,
        cloudrun_deploy_agent,
        # Log Preprocessing & HDB Storage
        preprocess_command_output,
        check_hdb_storage,
        # Analysis Script Self-Learning Tools
        run_analysis_script,
        parse_analysis_errors,
        discover_hana_schema,
        fix_analysis_script,
        run_and_learn_analysis,
    ],
)


# ──────────────────────────────────────────────
# 7.11 Instance Monitor Agent (vlgdbzo3)
# ──────────────────────────────────────────────
instance_monitor_agent = Agent(
    name="instance_monitor_agent",
    model=_sentinel_llm,
    description="Primary monitoring agent for vlgdbzo3 HANA instance on GCP. Runs diagnostic checks and detects issues requiring healing.",
    instruction=instance_monitor_agent_instructions,
    tools=list(INSTANCE_MONITOR_TOOLS.values()),
)


# ──────────────────────────────────────────────
# 7.12 Instance Backup Agent (vlgdbzo3)
# ──────────────────────────────────────────────
instance_backup_agent = Agent(
    name="instance_backup_agent",
    model=_sentinel_llm,
    description="VM snapshot management for vlgdbzo3 HANA instance. Creates daily GCP VM snapshots (one per day, never deletes).",
    instruction=instance_backup_agent_instructions,
    tools=list(INSTANCE_BACKUP_TOOLS.values()),
)


# ──────────────────────────────────────────────
# 7.13 Instance Healing Agent (vlgdbzo3)
# ──────────────────────────────────────────────
instance_healing_agent = Agent(
    name="instance_healing_agent",
    model=_sentinel_llm,
    description="Execution agent for healing/fixing scripts on vlgdbzo3. Implements all 4 toolkit healing scripts with approval workflow.",
    instruction=instance_healing_agent_instructions,
    tools=list(INSTANCE_HEALING_TOOLS.values()),
)


# ──────────────────────────────────────────────
# SUPERVISOR AGENT (Root Agent)
# PRD Section 4 — The orchestrator
# ──────────────────────────────────────────────
root_agent = Agent(
    name="hana_sentinel",
    model=_sentinel_llm,
    description="HANA Sentinel Supervisor — Autonomous, policy-gated multi-agent system for SAP HANA operations. Routes tasks to specialized agents including monitoring, verification, browser automation, and GCP instance management.",
    instruction="""You are HANA Sentinel, an autonomous AI system for SAP HANA operations.

You orchestrate specialized sub-agents to handle different operational domains:
- health_agent: System health monitoring (CPU, memory, disk, services, alerts)
- backup_agent: Backup compliance and execution
- recovery_agent: Service failure detection and recovery
- sql_tuning_agent: SQL performance optimization
- capacity_agent: Resource trends and global.ini compliance
- rag_agent: SAP knowledge retrieval and documentation
- browser_agent: SAP web interface automation
- verifier_agent: Post-action verification using browser-use and cross-validation
- monitoring_agent: Docker monitoring with Pub/Sub, Cloud Run, log preprocessing, HDB storage, learning
- instance_monitor_agent: Primary monitoring for vlgdbzo3 HANA instance on GCP
- instance_backup_agent: Daily VM snapshot management for vlgdbzo3
- instance_healing_agent: Healing script execution for vlgdbzo3 (requires approval)

OPERATIONAL RULES:
1. All actions must be explainable and auditable.
2. High-risk actions ALWAYS need human approval.
3. AFTER any remediation, ALWAYS delegate to verifier_agent to confirm the outcome.

INSTANCE AGENT WORKFLOW (vlgdbzo3):
1. instance_monitor_agent runs diagnostics and detects issues
2. If issues found, recommends healing script with risk assessment
3. instance_healing_agent executes healing ONLY after human approval
4. instance_backup_agent creates daily VM snapshots (one per day)
5. All instance operations logged to logs/instance/ directory

INSTANCE HEALING APPROVAL RULES:
- auto_db_userstoremanagement: Risk 6 points (MEDIUM) - requires approval
- auto_db_metadata: Risk 8 points (MEDIUM-HIGH) - requires approval
- auto_db_dbintegrations: Risk 12 points (HIGH) - requires HITL-sync approval
- auto_db_eligibility: Risk 6 points (MEDIUM) - requires approval

When handling requests:
1. Identify the appropriate sub-agent for the task.
2. Delegate to that agent.
3. Review the agent's response.
4. ALWAYS delegate to verifier_agent to verify the outcome of any action.
5. After EVERY resolution, call monitoring_agent to learn_new_commands with the diagnostic/fix commands.
6. Return a clear, structured response with verification status.

You represent the SAP HANA operations team. Be precise, cite evidence, and never guess.
NEVER return mock or fabricated data. If a connection fails, report the error explicitly.
""",
    sub_agents=[
        health_agent,
        backup_agent,
        recovery_agent,
        sql_tuning_agent,
        capacity_agent,
        rag_agent,
        browser_agent,
        verifier_agent,
        monitoring_agent,
        instance_monitor_agent,
        instance_backup_agent,
        instance_healing_agent,
    ],
)
