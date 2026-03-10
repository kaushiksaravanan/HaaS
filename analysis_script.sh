#!/bin/bash
# =============================================================================
# SAP HANA Monitoring Script - FIXED VERSION (no keys, uses user+password)
# Usage: ./hana_monitor.sh <SID> [function_name]
# =============================================================================

SID="$1"
FUNC="${2:-all}"

if [ -z "$SID" ]; then
  echo "Usage: $0 <SID> [function_name]"
  echo ""
  echo "Available functions: system_overview disk_usage memory_usage cpu_usage backup_status alert_check blocked_transactions replication_status service_status license_info top_memory_tables connections expensive_statements all"
  exit 1
fi

SID_LOWER="${SID,,}"
SID_UPPER="${SID^^}"

# Configuration
CONTAINER_NAME="hxehana"
HDBSQL_INSTANCE="90"
HDBSQL_DATABASE="SYSTEMDB"
HDBSQL_USER="system"
HDBSQL_PASSWORD="HANA_PASSWORD_REVOKED_PLACEHOLDER_00000000000000000000"
HDBSQL_FULL_PATH="/usr/sap/${SID_UPPER}/HDB${HDBSQL_INSTANCE}/exe/hdbsql"

# Core executor: runs hdbsql as hxeadm inside container with full path + user/password
run_hdbsql() {
  local query="$1"
  local db="${2:-$HDBSQL_DATABASE}"

  local output
  output=$(docker exec -u "${SID_LOWER}adm" "${CONTAINER_NAME}" \
    "${HDBSQL_FULL_PATH}" \
    -i "${HDBSQL_INSTANCE}" \
    -u "${HDBSQL_USER}" \
    -p "${HDBSQL_PASSWORD}" \
    -d "${db}" \
    -C -A -j -x \
    "${query}" 2>&1)

  local rc=$?
  if [ $rc -ne 0 ]; then
    echo "ERROR: hdbsql returned exit code $rc" >&2
    echo "$output" >&2
    return $rc
  fi

  echo "$output"
  return 0
}

print_header() {
  local title="$1"
  echo ""
  echo "============================================================================="
  echo "  $title  |  SID: $SID_UPPER  |  $(date '+%Y-%m-%d %H:%M:%S')"
  echo "============================================================================="
}

# =============================================================================
# All monitoring functions ΓÇô single-line SQL
# =============================================================================

get_system_overview() {
  print_header "SYSTEM OVERVIEW"
  local result
  result=$(run_hdbsql "SELECT DATABASE_NAME, VERSION, USAGE, START_TIME, ACTIVE_STATUS FROM SYS.M_DATABASE")
  [ $? -eq 0 ] && echo "$result" | column -t -s $'\t' || echo "Failed to retrieve system overview."
}

get_disk_usage() {
  print_header "DISK USAGE"
  local result
  result=$(run_hdbsql "SELECT HOST, USAGE_TYPE, ROUND(TOTAL_SIZE / 1024 / 1024 / 1024, 2) AS TOTAL_GB, ROUND(USED_SIZE / 1024 / 1024 / 1024, 2) AS USED_GB, ROUND((USED_SIZE * 100.0) / NULLIF(TOTAL_SIZE, 0), 1) AS USED_PCT FROM SYS.M_DISKS ORDER BY USED_SIZE DESC")
  [ $? -eq 0 ] && echo "$result" | column -t -s $'\t' || echo "Failed to retrieve disk usage."
}

get_memory_usage() {
  print_header "MEMORY USAGE"
  local result
  result=$(run_hdbsql "SELECT HOST, ROUND(FREE_PHYSICAL_MEMORY / 1024 / 1024 / 1024, 2) AS FREE_PHYS_GB, ROUND(USED_PHYSICAL_MEMORY / 1024 / 1024 / 1024, 2) AS USED_PHYS_GB, ROUND(FREE_SWAP_SPACE / 1024 / 1024 / 1024, 2) AS FREE_SWAP_GB, ROUND(INSTANCE_TOTAL_MEMORY_USED_SIZE / 1024 / 1024 / 1024, 2) AS HANA_USED_GB, ROUND(ALLOCATION_LIMIT / 1024 / 1024 / 1024, 2) AS ALLOC_LIMIT_GB, ROUND((INSTANCE_TOTAL_MEMORY_USED_SIZE * 100.0) / NULLIF(ALLOCATION_LIMIT, 0), 1) AS USED_PCT FROM SYS.M_HOST_RESOURCE_UTILIZATION")
  [ $? -eq 0 ] && echo "$result" | column -t -s $'\t' || echo "Failed to retrieve memory usage."
}

get_cpu_usage() {
  print_header "CPU USAGE"
  local result
  result=$(run_hdbsql "SELECT HOST, TOTAL_CPU_USER_TIME, TOTAL_CPU_SYSTEM_TIME, TOTAL_CPU_IDLE_TIME, TOTAL_CPU_WIO_TIME FROM SYS.M_HOST_RESOURCE_UTILIZATION")
  [ $? -eq 0 ] && echo "$result" | column -t -s $'\t' || echo "Failed to retrieve CPU usage."
}

get_backup_status() {
  print_header "BACKUP STATUS (Last 10)"
  local result
  result=$(run_hdbsql "SELECT TOP 10 ENTRY_ID, BACKUP_ID, ENTRY_TYPE_NAME, STATE_NAME, SYS_START_TIME, SYS_END_TIME, ROUND(BACKUP_SIZE / 1024 / 1024, 2) AS SIZE_MB, MESSAGE FROM SYS.M_BACKUP_CATALOG ORDER BY SYS_START_TIME DESC")
  [ $? -eq 0 ] && echo "$result" | column -t -s $'\t' || echo "Failed to retrieve backup status."
}

get_alert_check() {
  print_header "ACTIVE ALERTS"
  local result
  result=$(run_hdbsql "SELECT ALERT_ID, ALERT_RATING, ALERT_NAME, ALERT_DETAILS, ALERT_TIMESTAMP, HOST FROM _SYS_STATISTICS.STATISTICS_CURRENT_ALERTS WHERE ALERT_RATING >= 3 ORDER BY ALERT_RATING DESC, ALERT_TIMESTAMP DESC")
  if [ $? -eq 0 ]; then
    [ -z "$result" ] && echo "No active alerts with rating >= 3." || echo "$result" | column -t -s $'\t'
  else
    echo "Failed to retrieve alerts."
  fi
}

get_blocked_transactions() {
  print_header "BLOCKED / LONG-RUNNING TRANSACTIONS"
  local result
  result=$(run_hdbsql "SELECT HOST, CONNECTION_ID, TRANSACTION_ID, TRANSACTION_TYPE, IDLE_TIME, ROUND(LIFETIME / 1000, 1) AS LIFETIME_SEC, STATEMENT_STRING FROM SYS.M_TRANSACTIONS WHERE CONNECTION_ID > 0 AND IDLE_TIME > 600 ORDER BY IDLE_TIME DESC LIMIT 20")
  if [ $? -eq 0 ]; then
    [ -z "$result" ] && echo "No blocked or long-running transactions found." || echo "$result" | column -t -s $'\t'
  else
    echo "Failed to retrieve transaction info."
  fi
}

get_replication_status() {
  print_header "SYSTEM REPLICATION STATUS"
  local result
  result=$(run_hdbsql "SELECT HOST, PORT, SITE_ID, SITE_NAME, SECONDARY_HOST, SECONDARY_SITE_ID, SECONDARY_SITE_NAME, REPLICATION_MODE, REPLICATION_STATUS, REPLICATION_STATUS_DETAILS FROM SYS.M_SERVICE_REPLICATION")
  if [ $? -eq 0 ]; then
    [ -z "$result" ] && echo "System replication is not configured." || echo "$result" | column -t -s $'\t'
  else
    echo "Failed to retrieve replication status."
  fi
}

get_service_status() {
  print_header "SERVICE STATUS"
  local result
  result=$(run_hdbsql "SELECT HOST, PORT, SERVICE_NAME, PROCESS_ID, ACTIVE_STATUS, SQL_PORT, COORDINATOR_TYPE FROM SYS.M_SERVICES ORDER BY HOST, PORT")
  [ $? -eq 0 ] && echo "$result" | column -t -s $'\t' || echo "Failed to retrieve service status."
}

get_license_info() {
  print_header "LICENSE INFORMATION"
  local result
  result=$(run_hdbsql "SELECT HARDWARE_KEY, SYSTEM_ID, INSTALL_NO, SYSTEM_NO, PRODUCT_LIMIT, PRODUCT_USAGE, START_DATE, EXPIRATION_DATE, PERMANENT, VALID, ENFORCED FROM SYS.M_LICENSE")
  [ $? -eq 0 ] && echo "$result" | column -t -s $'\t' || echo "Failed to retrieve license info."
}

get_top_memory_tables() {
  print_header "TOP 20 TABLES BY MEMORY"
  local result
  result=$(run_hdbsql "SELECT TOP 20 SCHEMA_NAME, TABLE_NAME, TABLE_TYPE, ROUND(MEMORY_SIZE_IN_TOTAL / 1024 / 1024, 2) AS TOTAL_MB, RECORD_COUNT FROM SYS.M_CS_TABLES ORDER BY MEMORY_SIZE_IN_TOTAL DESC")
  [ $? -eq 0 ] && echo "$result" | column -t -s $'\t' || echo "Failed to retrieve table memory usage."
}

get_connections() {
  print_header "ACTIVE CONNECTIONS"
  local result
  result=$(run_hdbsql "SELECT HOST, CONNECTION_STATUS, USER_NAME, CLIENT_HOST, CLIENT_PID, CONNECTION_TYPE, START_TIME, IDLE_TIME FROM SYS.M_CONNECTIONS WHERE CONNECTION_STATUS = 'RUNNING' OR IDLE_TIME > 300 ORDER BY IDLE_TIME DESC LIMIT 30")
  if [ $? -eq 0 ]; then
    echo "$result" | column -t -s $'\t'
  else
    echo "Failed to retrieve connection info."
  fi

  echo ""
  echo "--- Connection Summary ---"
  local summary
  summary=$(run_hdbsql "SELECT CONNECTION_STATUS, COUNT(*) AS CNT FROM SYS.M_CONNECTIONS GROUP BY CONNECTION_STATUS ORDER BY CNT DESC")
  [ $? -eq 0 ] && echo "$summary" | column -t -s $'\t'
}

get_expensive_statements() {
  print_header "TOP 10 EXPENSIVE SQL STATEMENTS"
  local result
  result=$(run_hdbsql "SELECT TOP 10 HOST, ROUND(DURATION_MICROSEC / 1000000, 2) AS DURATION_SEC, ROUND(CPU_TIME / 1000000, 2) AS CPU_SEC, ROUND(MEMORY_SIZE / 1024 / 1024, 2) AS MEM_MB, RECORDS, OPERATION, SUBSTR(STATEMENT_STRING, 1, 120) AS SQL_PREVIEW FROM SYS.M_EXPENSIVE_STATEMENTS ORDER BY DURATION_MICROSEC DESC")
  if [ $? -eq 0 ]; then
    [ -z "$result" ] && echo "No expensive statements recorded." || echo "$result" | column -t -s $'\t'
  else
    echo "Failed to retrieve expensive statements."
  fi
}

run_all() {
  get_system_overview
  get_service_status
  get_memory_usage
  get_cpu_usage
  get_disk_usage
  get_backup_status
  get_alert_check
  get_blocked_transactions
  get_replication_status
  get_license_info
  get_top_memory_tables
  get_connections
  get_expensive_statements
}

case "$FUNC" in
  system_overview|disk_usage|memory_usage|cpu_usage|backup_status|alert_check|blocked_transactions|replication_status|service_status|license_info|top_memory_tables|connections|expensive_statements|all) ;;
  *) echo "ERROR: Unknown function '$FUNC'"; exit 1 ;;
esac

"${FUNC}" || run_all

echo ""
echo "=== Done ==="
