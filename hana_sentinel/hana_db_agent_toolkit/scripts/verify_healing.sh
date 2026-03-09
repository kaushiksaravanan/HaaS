#!/bin/bash
###############################################################################
# HANA Database Healing Script Verifier
# Purpose: Verify if a healing script executed successfully
# Usage: ./verify_healing.sh <script_name> <SID> <INSTANCE_NUMBER>
# Example: ./verify_healing.sh auto_db_userstoremanagement ABC 00
###############################################################################

if [ $# -ne 3 ]; then
    echo "Usage: $0 <script_name> <SID> <INSTANCE_NUMBER>"
    echo "Example: $0 auto_db_userstoremanagement ABC 00"
    exit 1
fi

SCRIPT_NAME=$1
SID=$2
INSTANCE=$3
LOWER_SID=$(echo "$SID" | tr '[:upper:]' '[:lower:]')
TIMESTAMP=$(date '+%Y-%m-%d %H:%M:%S')
LOG_FILE="../logs/verification_${SCRIPT_NAME}_${SID}_$(date +%Y%m%d_%H%M%S).log"

# Ensure log directory exists
mkdir -p ../logs

# Logging function
log() {
    echo "[$TIMESTAMP] $1" | tee -a "$LOG_FILE"
}

log "========================================"
log "Healing Script Verification"
log "========================================"
log "Script: $SCRIPT_NAME"
log "SID: $SID"
log "Instance: $INSTANCE"
log "========================================"

case "$SCRIPT_NAME" in
    "auto_db_userstoremanagement")
        log ""
        log "Verifying USERSTORE MANAGEMENT healing..."
        log "==========================================="

        log ""
        log "1. Checking userstore keys:"
        USERSTORE=$(su - ${LOWER_SID}adm -c "hdbuserstore list" 2>&1)
        log "$USERSTORE"

        log ""
        log "2. Testing key connectivity:"
        for key in BKPMON SAPDBCTRL SYSTEM TRANSPORT; do
            log "Testing $key..."
            TEST=$(su - ${LOWER_SID}adm -c "hdbsql -U $key 'SELECT 1 FROM DUMMY'" 2>&1)
            if [ $? -eq 0 ]; then
                log "✓ $key is connectable"
            else
                log "✗ $key connection failed"
                log "$TEST"
            fi
        done

        log ""
        log "3. Checking healing script logs:"
        LATEST_LOG=$(ls -t /tmp/db/auto/*/auto_db_userstoremanagement*.log 2>/dev/null | head -1)
        if [ -n "$LATEST_LOG" ]; then
            log "Latest log: $LATEST_LOG"
            log "Last 20 lines:"
            tail -20 "$LATEST_LOG" | tee -a "$LOG_FILE"
        else
            log "WARNING: No healing script logs found"
        fi
        ;;

    "auto_db_metadata")
        log ""
        log "Verifying DATABASE METADATA healing..."
        log "======================================"

        log ""
        log "1. Checking backup configuration:"
        BACKUP_CONFIG=$(su - ${LOWER_SID}adm -c "hdbsql -U BKPMON 'SELECT * FROM M_BACKUP_CONFIGURATION' -a" 2>&1 | head -20)
        log "$BACKUP_CONFIG"

        log ""
        log "2. Checking trace directory permissions:"
        TRACE_DIR="/usr/sap/$SID/HDB$INSTANCE/*/trace"
        log "Trace directory: $TRACE_DIR"
        ls -ld $TRACE_DIR 2>&1 | tee -a "$LOG_FILE"

        log ""
        log "3. Checking backup paths:"
        for dir in /hana/data/$SID /hana/log/$SID /hana/backup/$SID; do
            if [ -d "$dir" ]; then
                log "✓ $dir exists"
                ls -ld "$dir" | tee -a "$LOG_FILE"
            else
                log "✗ $dir not found"
            fi
        done

        log ""
        log "4. Checking healing script logs:"
        LATEST_LOG=$(ls -t /tmp/db/auto/*/auto_db_metadata*.log 2>/dev/null | head -1)
        if [ -n "$LATEST_LOG" ]; then
            log "Latest log: $LATEST_LOG"
            log "Last 20 lines:"
            tail -20 "$LATEST_LOG" | tee -a "$LOG_FILE"
        else
            log "WARNING: No healing script logs found"
        fi
        ;;

    "auto_db_dbintegrations")
        log ""
        log "Verifying DATABASE INTEGRATIONS healing..."
        log "==========================================="

        log ""
        log "1. Checking system parameters:"
        SWAPPINESS=$(cat /proc/sys/vm/swappiness 2>/dev/null)
        log "Swappiness: $SWAPPINESS (Expected: 10 or per standard)"

        THP=$(cat /sys/kernel/mm/transparent_hugepage/enabled 2>/dev/null)
        log "Transparent Huge Pages: $THP (Expected: [never])"

        ASLR=$(cat /proc/sys/kernel/randomize_va_space 2>/dev/null)
        log "ASLR: $ASLR (Expected: 0)"

        log ""
        log "2. Checking user shell:"
        SHELL=$(su - ${LOWER_SID}adm -c "echo \$SHELL" 2>&1)
        log "User shell for ${LOWER_SID}adm: $SHELL"

        log ""
        log "3. Checking file permissions:"
        for dir in /usr/sap/$SID /hana/shared/$SID; do
            if [ -d "$dir" ]; then
                log "Permissions for $dir:"
                ls -ld "$dir" | tee -a "$LOG_FILE"
            fi
        done

        log ""
        log "4. Checking healing script logs:"
        LATEST_LOG=$(ls -t /tmp/db/auto/*/auto_db_dbintegrations*.log 2>/dev/null | head -1)
        if [ -n "$LATEST_LOG" ]; then
            log "Latest log: $LATEST_LOG"
            log "Last 20 lines:"
            tail -20 "$LATEST_LOG" | tee -a "$LOG_FILE"
        else
            log "WARNING: No healing script logs found"
        fi
        ;;

    "auto_db_eligibility")
        log ""
        log "Verifying DATABASE ELIGIBILITY healing..."
        log "=========================================="

        log ""
        log "1. Checking backup catalog:"
        BACKUP_CAT=$(su - ${LOWER_SID}adm -c "hdbsql -U BKPMON 'SELECT TOP 5 ENTRY_ID, SYS_START_TIME, ENTRY_TYPE_NAME, STATE_NAME FROM M_BACKUP_CATALOG ORDER BY ENTRY_ID DESC' -a" 2>&1)
        log "$BACKUP_CAT"

        log ""
        log "2. Checking archive directories:"
        ARCHIVE_DIR="/hana/data/$SID/mnt00001/hdb00001/backup/log"
        if [ -d "$ARCHIVE_DIR" ]; then
            log "✓ Archive directory exists: $ARCHIVE_DIR"
            ls -ld "$ARCHIVE_DIR" | tee -a "$LOG_FILE"
        else
            log "INFO: Archive directory not found (may not be configured)"
        fi

        log ""
        log "3. Checking system database configuration:"
        SYSTEMDB=$(su - ${LOWER_SID}adm -c "hdbsql -U SYSTEM 'SELECT DATABASE_NAME, ACTIVE_STATUS FROM M_DATABASES' -a" 2>&1)
        log "$SYSTEMDB"

        log ""
        log "4. Checking healing script logs:"
        LATEST_LOG=$(ls -t /tmp/db/auto/*/auto_db_eligibility*.log 2>/dev/null | head -1)
        if [ -n "$LATEST_LOG" ]; then
            log "Latest log: $LATEST_LOG"
            log "Last 20 lines:"
            tail -20 "$LATEST_LOG" | tee -a "$LOG_FILE"
        else
            log "WARNING: No healing script logs found"
        fi
        ;;

    *)
        log "ERROR: Unknown script name: $SCRIPT_NAME"
        log "Supported scripts:"
        log "  - auto_db_userstoremanagement"
        log "  - auto_db_metadata"
        log "  - auto_db_dbintegrations"
        log "  - auto_db_eligibility"
        exit 1
        ;;
esac

log ""
log "========================================"
log "VERIFICATION COMPLETED"
log "========================================"
log "Full verification log saved to: $LOG_FILE"
log ""

# Check for errors in healing logs
if [ -n "$LATEST_LOG" ]; then
    ERROR_COUNT=$(grep -i "error" "$LATEST_LOG" 2>/dev/null | wc -l)
    if [ "$ERROR_COUNT" -gt 0 ]; then
        log "⚠ WARNING: Found $ERROR_COUNT error messages in healing log"
        log "Review required: $LATEST_LOG"
        exit 1
    else
        log "✓ No errors found in healing log"
        exit 0
    fi
else
    log "⚠ WARNING: Unable to verify healing - log not found"
    exit 2
fi
