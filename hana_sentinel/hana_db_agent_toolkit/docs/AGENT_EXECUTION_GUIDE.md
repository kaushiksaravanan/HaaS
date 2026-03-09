# HANA Database Agent Execution Guide

## Overview
This guide is for AI agents monitoring a 24/7 running HANA database system. It contains SAFE, READ-ONLY diagnostic operations and references to healing scripts for APPROVED issues only.

## ⚠️ CRITICAL SAFETY RULES

1. **NEVER run destructive operations without explicit approval**
2. **ALWAYS verify before executing any healing script**
3. **READ-ONLY operations can be performed freely**
4. **Document all actions in logs**
5. **Escalate complex issues to human operators**

---

## Problem Detection & Response Matrix

### 1. HANA Database Health Check Issues

#### Problem: Database not responding / Connection issues
**Detection Script:**
```bash
# Check HANA process status
su - <sid>adm -c "sapcontrol -nr <instance> -function GetProcessList"
```

**Verification Command:**
```bash
# Verify all processes are GREEN
su - <sid>adm -c "HDB info"
```

**Healing Script:** `auto_db_userstoremanagement`
- **Purpose:** Fixes HANA userstore connectivity issues
- **Safe Level:** MEDIUM (modifies userstore keys)
- **When to Use:** When userstore keys are incorrectly configured
- **Verification After Run:**
```bash
su - <sid>adm -c "hdbuserstore list"
# Check if keys are properly configured and connectable
```

---

### 2. Database Metadata Issues

#### Problem: Backup path misconfiguration, trace directory permissions
**Detection Script:**
```bash
# Check backup paths
su - <sid>adm -c "hdbsql -U BKPMON 'SELECT * FROM M_BACKUP_CONFIGURATION'"
```

**Healing Script:** `auto_db_metadata`
- **Purpose:** Fixes DB metadata issues including:
  - Backup path parameters
  - Trace directory permissions
  - Database configuration parameters
- **Safe Level:** MEDIUM-HIGH
- **When to Use:**
  - Backup paths are misconfigured
  - Trace directories have wrong permissions
  - Database parameters need reset to standard values
- **Verification After Run:**
```bash
# Check backup configuration
su - <sid>adm -c "hdbsql -U BKPMON 'SELECT * FROM M_BACKUP_CONFIGURATION'"
# Check trace directory permissions
ls -la /usr/sap/<SID>/HDB<instance>/*/trace/
```

---

### 3. Database Integration Issues

#### Problem: System configuration, swappiness, THP, ASLR settings
**Detection Script:**
```bash
# Check system settings
cat /proc/sys/vm/swappiness
cat /sys/kernel/mm/transparent_hugepage/enabled
cat /proc/sys/kernel/randomize_va_space
```

**Healing Script:** `auto_db_dbintegrations`
- **Purpose:** Fixes OS-level database integration issues:
  - Swappiness settings
  - Transparent Huge Pages (THP)
  - Address Space Layout Randomization (ASLR)
  - User shell configurations
  - File permissions and ownership
- **Safe Level:** HIGH (modifies system settings)
- **When to Use:**
  - After system reboot/updates
  - When OS parameters drift from standards
  - Permission issues on database directories
- **Verification After Run:**
```bash
# Verify swappiness
cat /proc/sys/vm/swappiness  # Should be 10 or per standard
# Verify THP
cat /sys/kernel/mm/transparent_hugepage/enabled  # Should be [never]
# Verify ASLR
cat /proc/sys/kernel/randomize_va_space  # Should be 0
```

---

### 4. Database Eligibility & Configuration

#### Problem: License issues, backup verification, parameter settings
**Detection Script:**
```bash
# Check database configuration
su - <sid>adm -c "hdbsql -U SYSTEM 'SELECT * FROM M_SYSTEM_OVERVIEW'"
```

**Healing Script:** `auto_db_eligibility`
- **Purpose:** Validates and fixes database eligibility criteria:
  - Database backups configuration
  - HANA Cleaner setup
  - System database configuration
  - Archive management
- **Safe Level:** MEDIUM
- **When to Use:**
  - Database backup validation fails
  - Archive directories have issues
  - System DB needs configuration updates
- **Verification After Run:**
```bash
# Check backup status
su - <sid>adm -c "hdbsql -U BKPMON 'SELECT * FROM M_BACKUP_CATALOG'"
# Verify archive status
ls -la /hana/data/<SID>/mnt00001/hdb00001/backup/log/
```

---

## Safe Diagnostic Commands (Always Available)

### Database Status Checks
```bash
# Check all HANA processes
su - <sid>adm -c "HDB info"

# Check database status
su - <sid>adm -c "sapcontrol -nr <instance> -function GetSystemInstanceList"

# Check database version
su - <sid>adm -c "HDB version"

# Check memory usage
su - <sid>adm -c "hdbsql -U SYSTEM 'SELECT * FROM M_HOST_RESOURCE_UTILIZATION'"

# Check disk usage
df -h | grep -E 'hana|hdb'

# Check database alerts
su - <sid>adm -c "hdbsql -U SYSTEM 'SELECT * FROM M_ALERTS WHERE ALERT_RATING > 3'"
```

### Log File Locations
```bash
# Main database logs
/usr/sap/<SID>/HDB<instance>/*/trace/

# Backup logs
/hana/backup/<SID>/log/

# Healing script logs
/tmp/db/auto/YYYYMMDD/
```

---

## Execution Workflow for Agent

### Step 1: Detection Phase
1. Run diagnostic commands to identify issues
2. Categorize the problem type
3. Check if problem matches known patterns

### Step 2: Decision Phase
1. Determine if issue requires healing
2. Check if healing script is safe for the specific issue
3. Verify prerequisites (database up, permissions, etc.)

### Step 3: Approval Phase
**⚠️ CRITICAL: Get explicit approval before executing healing scripts**
```text
REQUIRED APPROVAL INFO:
- What issue was detected?
- Which healing script will be used?
- What changes will it make?
- What is the risk level?
- What is the rollback plan?
```

### Step 4: Execution Phase
1. Take pre-execution snapshot (logs, configuration)
2. Execute healing script
3. Capture output to log file

### Step 5: Verification Phase
1. Run verification commands listed above
2. Check if issue is resolved
3. Document results
4. If issue persists, escalate to human operator

---

## Logging Requirements

All agent actions must be logged to:
`hana_db_agent_toolkit/logs/agent_actions_YYYYMMDD_HHMM.log`

Log format:
```
[TIMESTAMP] [SEVERITY] [ACTION_TYPE] [DETAILS]
```

Example:
```
[2026-03-04 10:30:00] [INFO] [DETECTION] Checking HANA database status for SID: ABC
[2026-03-04 10:30:15] [WARNING] [ISSUE_FOUND] Userstore key BKPMON not connectable
[2026-03-04 10:31:00] [INFO] [APPROVAL_REQUEST] Requesting approval for auto_db_userstoremanagement
[2026-03-04 10:35:00] [INFO] [EXECUTION] Running auto_db_userstoremanagement with args: <hostname>
[2026-03-04 10:36:00] [INFO] [VERIFICATION] Userstore connectivity restored - PASS
```

---

## Escalation Criteria

Escalate to human operator if:
1. Issue not covered in this guide
2. Multiple healing attempts failed
3. Database is in critical state (DOWN, no connectivity)
4. Data loss risk detected
5. Uncertainty about correct action
6. Healing script returns error code

---

## Emergency Commands (READ-ONLY)

### Quick Status Overview
```bash
#!/bin/bash
# Quick HANA status check
SID=$1
INSTANCE=$2

echo "=== HANA Quick Status Check ==="
echo "SID: $SID, Instance: $INSTANCE"
echo ""

echo "1. Process Status:"
su - ${SID,,}adm -c "sapcontrol -nr $INSTANCE -function GetProcessList" 2>&1 | grep -E "GREEN|YELLOW|RED"

echo ""
echo "2. Disk Usage:"
df -h | grep -E "hana|hdb|$SID"

echo ""
echo "3. Recent Alerts (Last 24h):"
su - ${SID,,}adm -c "hdbsql -U SYSTEM \"SELECT ALERT_TIMESTAMP, ALERT_DETAILS FROM M_ALERTS WHERE ALERT_TIMESTAMP > ADD_SECONDS(CURRENT_TIMESTAMP, -86400) ORDER BY ALERT_TIMESTAMP DESC\" -a" 2>&1

echo ""
echo "4. Last Backup:"
su - ${SID,,}adm -c "hdbsql -U BKPMON \"SELECT TOP 1 * FROM M_BACKUP_CATALOG ORDER BY ENTRY_ID DESC\" -a" 2>&1
```

---

## Script Reference Summary

| Script Name | Purpose | Risk Level | Approval Required |
|------------|---------|------------|------------------|
| `auto_db_userstoremanagement` | Fix userstore keys | MEDIUM | YES |
| `auto_db_metadata` | Fix backup paths, trace permissions, DB parameters | MEDIUM-HIGH | YES |
| `auto_db_dbintegrations` | Fix OS settings, permissions, system config | HIGH | YES |
| `auto_db_eligibility` | Validate/fix DB backups, archives, system DB | MEDIUM | YES |

---

## Version Information
- **Guide Version:** 1.0
- **Last Updated:** 2026-03-04
- **Compatible with:** HANA 2.0 SPS 04+, SLES 12/15
- **Author:** Generated for AI Agent Use

---

## Additional Resources

- Original healing scripts located in: `../`
- Full script logs: `/tmp/db/auto/`
- HANA documentation: `/usr/sap/<SID>/HDB<instance>/exe/doc/`
- Metadata finder: `/sapmnt/dlm/services/database/mastercodebase/Misc/metadatafinder.bash`

---

## Contact Information for Escalation

**Critical Issues:**
- Escalate immediately through designated ticketing system
- Include: SID, hostname, issue description, actions attempted, logs

**Non-Critical Issues:**
- Document in daily report
- Schedule review with human operator
