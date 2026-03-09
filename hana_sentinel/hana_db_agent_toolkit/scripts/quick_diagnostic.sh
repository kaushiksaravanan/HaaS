#!/bin/bash
###############################################################################
# HANA Database Quick Diagnostic Script
# Purpose: Safe, read-only diagnostic checks for HANA database health
# Usage: ./quick_diagnostic.sh <SID> <INSTANCE_NUMBER>
# Example: ./quick_diagnostic.sh ABC 00
###############################################################################

# Input validation
if [ $# -ne 2 ]; then
    echo "Usage: $0 <SID> <INSTANCE_NUMBER>"
    echo "Example: $0 ABC 00"
    exit 1
fi

SID=$1
INSTANCE=$2
LOWER_SID=$(echo "$SID" | tr '[:upper:]' '[:lower:]')
TIMESTAMP=$(date '+%Y-%m-%d %H:%M:%S')
LOG_FILE="../logs/diagnostic_${SID}_$(date +%Y%m%d_%H%M%S).log"

# Ensure log directory exists
mkdir -p ../logs

# Logging function
log() {
    echo "[$TIMESTAMP] $1" | tee -a "$LOG_FILE"
}

log "========================================"
log "HANA Database Diagnostic Report"
log "========================================"
log "SID: $SID"
log "Instance: $INSTANCE"
log "Hostname: $(hostname)"
log "========================================"

# Check 1: HANA Process Status
log ""
log "1. HANA PROCESS STATUS"
log "----------------------"
PROCESS_STATUS=$(su - ${LOWER_SID}adm -c "sapcontrol -nr $INSTANCE -function GetProcessList" 2>&1)
if [ $? -eq 0 ]; then
    echo "$PROCESS_STATUS" | grep -E "name|GREEN|YELLOW|RED" | tee -a "$LOG_FILE"
else
    log "ERROR: Unable to get process status"
    log "$PROCESS_STATUS"
fi

# Check 2: HDB Info
log ""
log "2. HDB INFO"
log "-----------"
HDB_INFO=$(su - ${LOWER_SID}adm -c "HDB info" 2>&1)
log "$HDB_INFO"

# Check 3: Disk Usage
log ""
log "3. DISK USAGE"
log "-------------"
df -h | grep -E "Filesystem|hana|hdb|$SID" | tee -a "$LOG_FILE"

# Check 4: Database Version
log ""
log "4. DATABASE VERSION"
log "-------------------"
VERSION=$(su - ${LOWER_SID}adm -c "HDB version" 2>&1 | head -10)
log "$VERSION"

# Check 5: Userstore Keys
log ""
log "5. USERSTORE KEYS"
log "-----------------"
USERSTORE=$(su - ${LOWER_SID}adm -c "hdbuserstore list" 2>&1)
log "$USERSTORE"

# Check 6: Recent Database Alerts (if accessible)
log ""
log "6. RECENT DATABASE ALERTS (Last 24 hours)"
log "------------------------------------------"
ALERTS=$(su - ${LOWER_SID}adm -c "hdbsql -U SYSTEM \"SELECT ALERT_TIMESTAMP, ALERT_RATING, ALERT_DETAILS FROM M_ALERTS WHERE ALERT_TIMESTAMP > ADD_SECONDS(CURRENT_TIMESTAMP, -86400) AND ALERT_RATING > 2 ORDER BY ALERT_TIMESTAMP DESC\" -a" 2>&1 | head -20)
if [ $? -eq 0 ]; then
    log "$ALERTS"
else
    log "INFO: Unable to retrieve alerts (database may be down or credentials not configured)"
fi

# Check 7: Memory Usage
log ""
log "7. SYSTEM MEMORY USAGE"
log "----------------------"
free -h | tee -a "$LOG_FILE"

# Check 8: Last Backup Status (if accessible)
log ""
log "8. LAST BACKUP STATUS"
log "---------------------"
BACKUP=$(su - ${LOWER_SID}adm -c "hdbsql -U BKPMON \"SELECT TOP 1 ENTRY_ID, SYS_START_TIME, ENTRY_TYPE_NAME, STATE_NAME FROM M_BACKUP_CATALOG ORDER BY ENTRY_ID DESC\" -a" 2>&1 | head -10)
if [ $? -eq 0 ]; then
    log "$BACKUP"
else
    log "INFO: Unable to retrieve backup status (BKPMON key may not be configured)"
fi

# Check 9: System Parameters
log ""
log "9. CRITICAL SYSTEM PARAMETERS"
log "------------------------------"
log "Swappiness: $(cat /proc/sys/vm/swappiness 2>/dev/null || echo 'Unable to read')"
log "Transparent Huge Pages: $(cat /sys/kernel/mm/transparent_hugepage/enabled 2>/dev/null || echo 'Unable to read')"
log "ASLR: $(cat /proc/sys/kernel/randomize_va_space 2>/dev/null || echo 'Unable to read')"

# Check 10: Trace Directory
log ""
log "10. TRACE DIRECTORY STATUS"
log "--------------------------"
TRACE_DIR="/usr/sap/$SID/HDB$INSTANCE/*/trace"
if ls $TRACE_DIR/*.trc >/dev/null 2>&1; then
    log "Recent trace files:"
    ls -lth $TRACE_DIR/*.trc 2>/dev/null | head -5 | tee -a "$LOG_FILE"

    # Check trace directory size
    TRACE_SIZE=$(du -sh $TRACE_DIR 2>/dev/null | awk '{print $1}')
    log "Trace directory size: $TRACE_SIZE"
else
    log "INFO: No trace files found or unable to access trace directory"
fi

# Summary
log ""
log "========================================"
log "DIAGNOSTIC COMPLETED"
log "========================================"
log "Full log saved to: $LOG_FILE"
log ""

# Return summary
echo ""
echo "Quick Summary:"
echo "--------------"
if echo "$PROCESS_STATUS" | grep -q "GREEN"; then
    echo "✓ Database processes are running"
else
    echo "✗ Database processes may have issues"
fi

if df -h | grep -E "hana|hdb|$SID" | awk '{print $5}' | sed 's/%//' | awk '$1 > 85 {exit 1}'; then
    echo "✓ Disk usage is within acceptable limits"
else
    echo "⚠ WARNING: High disk usage detected"
fi

echo ""
echo "For detailed information, review: $LOG_FILE"
