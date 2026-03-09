# Quick Reference Card for AI Agents

## Problem → Script → Verification

### 1. Database Connection Issues
```
Problem: Can't connect to database / Userstore issues
Script:  ../auto_db_userstoremanagement <hostname>
Verify:  ./verify_healing.sh auto_db_userstoremanagement <SID> <INSTANCE>
Check:   hdbuserstore list (as <sid>adm)
```

### 2. Backup Configuration Issues
```
Problem: Backup paths wrong / Trace directory permissions
Script:  ../auto_db_metadata <hostname> <parameters>
Verify:  ./verify_healing.sh auto_db_metadata <SID> <INSTANCE>
Check:   M_BACKUP_CONFIGURATION table
```

### 3. System Configuration Issues
```
Problem: Swappiness / THP / ASLR wrong / Permission issues
Script:  ../auto_db_dbintegrations <hostname>
Verify:  ./verify_healing.sh auto_db_dbintegrations <SID> <INSTANCE>
Check:   cat /proc/sys/vm/swappiness (should be 10)
         cat /sys/kernel/mm/transparent_hugepage/enabled (should be [never])
```

### 4. Backup Validation Issues
```
Problem: Backup validation failed / Archive issues
Script:  ../auto_db_eligibility <hostname>
Verify:  ./verify_healing.sh auto_db_eligibility <SID> <INSTANCE>
Check:   M_BACKUP_CATALOG table
```

## Quick Diagnostic Commands
```bash
# Get all info at once
./quick_diagnostic.sh <SID> <INSTANCE>

# Check if database is up
su - <sid>adm -c "HDB info"

# Check userstore
su - <sid>adm -c "hdbuserstore list"

# Check disk space
df -h | grep -E 'hana|hdb'

# Check recent alerts
su - <sid>adm -c "hdbsql -U SYSTEM 'SELECT * FROM M_ALERTS WHERE ALERT_RATING > 3 ORDER BY ALERT_TIMESTAMP DESC' -a"
```

## Before Running ANY Healing Script

### APPROVAL CHECKLIST:
☐ Diagnostic completed
☐ Problem identified and matches known pattern
☐ Correct healing script selected
☐ Risk level assessed
☐ Verification plan ready
☐ **EXPLICIT APPROVAL RECEIVED**

## After Running Healing Script

### VERIFICATION CHECKLIST:
☐ Run verify_healing.sh
☐ Check healing script logs in /tmp/db/auto/
☐ Re-run diagnostic to confirm fix
☐ Document results
☐ If failed → Escalate

## Risk Levels

**LOW**: Read-only diagnostics → ✅ No approval needed

**MEDIUM**: Userstore, backups, metadata → ⚠️ Approval required

**HIGH**: System settings, permissions → ⚠️⚠️ Explicit approval required

## Emergency Contact

**Critical Issues**: Escalate immediately
**Include**: SID, hostname, issue, logs, actions attempted

---

**Remember**: Better to ask than to break!
