# HANA Node Architecture - API Reference
## Remote Exec Server V2 - Comprehensive Endpoints

Base URL: `http://10.238.36.146:9999`
Authentication: `X-API-Key` header required for all endpoints

---

## 🏗️ Node Architecture Endpoints

### GET `/node/info`
**Complete node information (architecture)**

Returns comprehensive system details including:
- System information (hostname, OS, architecture)
- Hardware specs (CPU, memory, disks)
- Network interfaces
- HANA configuration
- Capabilities
- Status

**Response Example:**
```json
{
  "node_type": "hana_compute_instance",
  "instance_name": "vlgdbzo3",
  "system": {
    "hostname": "vlgdbzo3",
    "os": "Linux 5.10",
    "architecture": "x86_64"
  },
  "hardware": {
    "cpu_count": 24,
    "memory_gb": 179,
    "disks": [...]
  },
  "hana": {
    "sid": "ZO3",
    "instance_number": "00",
    "user": "zo3adm"
  },
  "capabilities": {...}
}
```

---

### GET `/node/specs`
**Hardware specifications only**

Quick endpoint for system specs:
- CPU cores
- Memory (GB)
- Architecture
- OS

---

### GET `/node/capabilities`
**List all capabilities this node provides**

Shows what this node can do:
- Available diagnostics checks
- Healing operations with risk levels
- Command execution capabilities
- API information

---

## 🔍 Observability & System Health

### GET `/observability/system-health`
**Real-time system health summary**

**Use Case:** "Give me current system health summary"

Returns:
- CPU usage
- Memory status
- Disk usage
- System parameters
- Alerts overview

---

### GET `/observability/resource-utilization`
**Resource utilization analysis**

**Use Case:** "Why is CPU high?"

Returns:
- Load average
- Memory details (MemTotal, MemAvailable, etc.)
- Disk I/O statistics (via iostat)

---

## 🩺 Diagnostics

### GET `/diagnostics`
**Run all diagnostic checks**

Executes all 6 diagnostic checks:
1. HANA processes (sapcontrol)
2. Disk usage
3. Memory
4. Userstore keys
5. System parameters
6. Backups

---

### GET `/diagnostics/summary`
**Quick health check summary**

Returns status indicators without full details:
```json
{
  "overall_status": "healthy",
  "checks": {
    "hana_processes": "success",
    "disk_usage": "success",
    "memory": "success"
  }
}
```

---

## 📊 Capacity & Growth Monitoring

### GET `/capacity/growth-analysis`
**Table and schema growth analysis**

**Use Cases:**
- "Which tables are growing fastest?"
- "Show schema growth last 30 days"
- "Will disk fill up soon?"

Returns:
- Disk usage by mount point
- Usage percentages
- Available space
- Backup storage status

---

## ⚙️ Operational Self-Service

### GET `/operational/backup-status`
**Verify backup completion**

**Use Case:** "Is last backup successful?"

Returns:
- Backup directory status
- Data backup location
- Log backup location
- Recommendations for SQL queries

---

### GET `/operational/version-info`
**Database version & configuration**

**Use Case:** "What is current DB version?"

Returns:
- HANA version (via HDB version)
- HANA SID
- Instance number
- System parameters
- OS information

---

## 🔧 Healing Operations

### GET `/healing/options`
**List available healing operations**

Shows all healing scripts with risk levels

---

### POST `/healing/execute/{operation}`
**Execute healing operation**

**Parameters:**
- `operation`: system_parameters | trace_cleanup
- `dry_run`: true | false (default: true)

**Use Cases:**
- "Fix system parameters" (swappiness, THP, ASLR)
- "Clean up old trace files"

**Risk Levels:**
- system_parameters: HIGH (12 points)
- trace_cleanup: LOW (3 points)

---

## 🛠️ Command Execution

### POST `/execute`
**Execute shell command**

**Request Body:**
```json
{
  "command": "df -h",
  "timeout": 60,
  "working_dir": "/home/zo3adm"
}
```

**Security:**
- Command must be in allowlist
- API key required
- Timeout limits enforced

**Allowed Commands:**
- echo, whoami, pwd, date, hostname
- df, free, uptime
- sapcontrol, HDB, hdbsql, hdbuserstore
- ls -l, du -sh, ps aux

---

## 📋 Use Case Mapping

### Category 1: Observability & System Health

| Use Case | Endpoint | Example Prompt |
|----------|----------|----------------|
| System Health Summary | GET `/observability/system-health` | "Give me current system health summary" |
| Resource Utilization | GET `/observability/resource-utilization` | "Why is CPU high?" |
| Session Monitoring | POST `/execute` with SQL | "Show blocking sessions" |

### Category 2: Performance Analytics

| Use Case | Endpoint | Implementation |
|----------|----------|----------------|
| Top Expensive SQL | POST `/execute` with SQL | Query M_SQL_PLAN_CACHE |
| Query Optimization | POST `/execute` with EXPLAIN | Analyze execution plan |
| Job Performance | POST `/execute` with SQL | Query M_JOB_PROGRESS |
| Lock Analysis | POST `/execute` with SQL | Query M_BLOCKED_TRANSACTIONS |

### Category 3: Growth Monitoring & Capacity

| Use Case | Endpoint | Example Prompt |
|----------|----------|----------------|
| Table Growth | GET `/capacity/growth-analysis` | "Which tables are growing fastest?" |
| Schema Growth | GET `/capacity/growth-analysis` | "Show schema growth" |
| Disk Monitoring | GET `/diagnostics` | "Will disk fill up soon?" |
| Capacity Forecast | GET `/capacity/growth-analysis` | "When will disk reach 90%?" |

### Category 4: Automation

| Use Case | Endpoint | Example |
|----------|----------|---------|
| Execute Healing | POST `/healing/execute/{op}` | "Fix system parameters" |
| Scheduled Diagnostics | GET `/diagnostics` | Run via cron/scheduler |
| Metadata Fetch | GET `/node/info` | Get instance details |

### Category 5: Operational Self-Service

| Use Case | Endpoint | Example Prompt |
|----------|----------|----------------|
| Backup Status | GET `/operational/backup-status` | "Is last backup successful?" |
| Version Info | GET `/operational/version-info` | "What is current DB version?" |
| User Management | POST `/execute` with SQL | "Does user X have access?" |

### Category 6: Alert Analysis & Knowledge

| Use Case | Implementation | Notes |
|----------|----------------|-------|
| Alert Interpretation | Query M_ALERTS via `/execute` | Parse and explain alerts |
| Root Cause Suggestion | Combine multiple diagnostics | AI analysis on client side |
| Concept Explanation | Client-side AI | "What is delta merge?" |
| Best Practices | Client-side AI | Tuning recommendations |

---

## 🔐 Authentication

All endpoints require API key authentication:

```bash
curl -H "X-API-Key: REMOTE_EXEC_KEY_REVOKED_PLACEHOLDER_0000000000000000" \
  http://10.238.36.146:9999/node/info
```

---

## 🚀 Testing Examples

### Test Node Info
```bash
curl -H "X-API-Key: YOUR_KEY" http://10.238.36.146:9999/node/info
```

### Test System Health
```bash
curl -H "X-API-Key: YOUR_KEY" http://10.238.36.146:9999/observability/system-health
```

### Test Diagnostics
```bash
curl -H "X-API-Key: YOUR_KEY" http://10.238.36.146:9999/diagnostics/summary
```

### Execute Command
```bash
curl -X POST -H "X-API-Key: YOUR_KEY" \
  -H "Content-Type: application/json" \
  -d '{"command": "df -h"}' \
  http://10.238.36.146:9999/execute
```

### Healing (Dry Run)
```bash
curl -X POST -H "X-API-Key: YOUR_KEY" \
  "http://10.238.36.146:9999/healing/execute/trace_cleanup?dry_run=true"
```

---

## 📦 Deployment

Copy the updated `remote_exec_server_v2.py` to vlgdbzo3 and restart:

```bash
# On vlgdbzo3
pkill -f remote_exec_server
python3 remote_exec_server_v2.py
```

---

## 🎯 Summary

**Total Endpoints:** 17+

**Categories:**
- Node Architecture: 3 endpoints
- Observability: 2 endpoints
- Diagnostics: 2 endpoints
- Capacity: 1 endpoint
- Operational: 2 endpoints
- Healing: 2 endpoints
- Commands: 1 endpoint
- Health: 2 endpoints (root + health)

**All endpoints return JSON and support API key authentication.**
