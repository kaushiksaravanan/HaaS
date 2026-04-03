# SAP HANA Operations Knowledge Base

## Common SQL Views for Monitoring

### M_BACKUP_CATALOG
Stores metadata about all backup operations. Key columns:
- BACKUP_ID: Unique backup identifier
- ENTRY_TYPE_NAME: Type (complete data backup, log backup, differential backup)
- STATE_NAME: Status (successful, running, failed, cancel pending)
- SYS_START_TIME, SYS_END_TIME: Backup time window
- MESSAGE: Error details if failed

**Example queries:**
```sql
-- Last 10 backups
SELECT TOP 10 BACKUP_ID, ENTRY_TYPE_NAME, STATE_NAME, SYS_START_TIME, SYS_END_TIME
FROM M_BACKUP_CATALOG ORDER BY SYS_END_TIME DESC;

-- Failed backups in the last 7 days
SELECT * FROM M_BACKUP_CATALOG
WHERE STATE_NAME = 'failed' AND SYS_END_TIME > ADD_DAYS(CURRENT_TIMESTAMP, -7);
```

### M_SERVICE_MEMORY
Shows memory consumption per HANA service.
- HOST, PORT, SERVICE_NAME
- EFFECTIVE_ALLOCATION_LIMIT: Max memory allowed
- TOTAL_MEMORY_USED_SIZE: Current usage
- HEAP_MEMORY_ALLOCATED_SIZE, SHARED_MEMORY_ALLOCATED_SIZE

### M_CONNECTIONS
Active database connections.
- CONNECTION_ID, TRANSACTION_ID
- CONNECTION_STATUS: RUNNING, IDLE
- CLIENT_HOST, CLIENT_PID
- START_TIME

### M_SQL_PLAN_CACHE
Cached SQL execution plans — useful for finding expensive queries.
- STATEMENT_HASH: Unique query identifier
- EXECUTION_COUNT: Times executed
- TOTAL_EXECUTION_TIME: Cumulative runtime (microseconds)
- AVG_EXECUTION_TIME: Average runtime
- STATEMENT_STRING: The SQL text

**Example:**
```sql
-- Top 20 expensive queries by total execution time
SELECT TOP 20 STATEMENT_HASH, EXECUTION_COUNT,
  TOTAL_EXECUTION_TIME / 1000000 AS TOTAL_SEC,
  AVG_EXECUTION_TIME / 1000 AS AVG_MS,
  SUBSTR(STATEMENT_STRING, 1, 200) AS SQL_TEXT
FROM M_SQL_PLAN_CACHE
ORDER BY TOTAL_EXECUTION_TIME DESC;
```

## Memory Management

### Memory OOM (Out of Memory)
SAP HANA allocates memory from the OS. Key thresholds:
- **global_allocation_limit**: Max memory HANA can use (global.ini → [memorymanager])
- If exceeded, HANA starts rejecting new allocations
- Emergency: HANA may kill sessions consuming most memory

**Troubleshooting OOM:**
1. Check `M_SERVICE_MEMORY` for per-service memory
2. Check `M_HEAP_MEMORY` for top memory consumers
3. Look at `M_EXPENSIVE_STATEMENTS` for queries causing spikes
4. Review `indexserver alert` for alert ID 1 (Host memory usage)

### Column Store vs Row Store
- Column store: Analytical/read queries, columnar compression
- Row store: OLTP, frequent updates, small result sets
- Check with `SELECT * FROM M_CS_TABLES` and `M_RS_TABLES`

## Backup Strategy

### Types of Backups
1. **Complete Data Backup**: Full backup of all data. Required as baseline.
2. **Differential Backup**: Changes since last full backup. Faster than full.
3. **Incremental Backup**: Changes since any last backup. Smallest size.
4. **Log Backup**: Transaction log segments. For point-in-time recovery.

### Best Practices
- Full backup weekly or daily
- Log backups every 15 minutes (or based on log volume)
- Keep at least 2 generations of full backups
- Test recovery on a schedule

## Alert Handling

### Common HANA Alerts
| Alert ID | Name | Description |
|----------|------|-------------|
| 1 | Host memory usage | Physical memory utilization exceeds threshold |
| 2 | Disk usage | Data/log volume running low |
| 3 | Inactive services | An expected HANA service is not running |
| 5 | Replication delay | System replication lag exceeds threshold |
| 17 | Long-running statements | Statements running longer than threshold |
| 39 | License expiration | SAP HANA license nearing expiry |
| 40 | Certificate expiration | SSL certificate nearing expiry |

### Response Matrix
- **Alert 1 (Memory)**: Check M_SERVICE_MEMORY, identify top consumer, consider increasing global_allocation_limit or freeing caches
- **Alert 2 (Disk)**: Check df -h, clean old backups/traces, increase disk if needed
- **Alert 3 (Inactive)**: Check sapcontrol GetProcessList, restart affected service
- **Alert 5 (Replication)**: Check M_SERVICE_REPLICATION, examine network latency
- **Alert 17 (Long running)**: Check M_EXPENSIVE_STATEMENTS, consider killing long sessions

## System Replication (HSR)

SAP HANA System Replication provides high availability and disaster recovery.

### Modes
- **SYNC**: Primary waits for secondary acknowledgment. Zero data loss.
- **SYNCMEM**: Primary waits until redo log is in secondary memory. Near-zero data loss.
- **ASYNC**: Primary does not wait. Possible data loss but no performance impact.

### Monitoring
```sql
SELECT * FROM M_SERVICE_REPLICATION;
SELECT * FROM SYS_DATABASES.M_SYSTEM_REPLICATION;
```

### Common Issues
- **Replication not active**: Check `hdbnsutil -sr_state` on both nodes
- **Log shipping delay**: Network bandwidth or secondary I/O bottleneck
- **Takeover failed**: Check prerequisite conditions with `hdbnsutil -sr_takeover --test`

## Parameter Tuning

### Key global.ini Parameters
| Section | Parameter | Description | Default |
|---------|-----------|-------------|---------|
| memorymanager | global_allocation_limit | Max memory (MB) | 0 (auto) |
| persistence | log_mode | normal/overwrite | normal |
| trace | defaulttracelevel | Trace verbosity | info |
| indexserver | max_concurrency | Max parallel threads | 0 (auto) |

### Changing Parameters
```sql
ALTER SYSTEM ALTER CONFIGURATION ('global.ini', 'SYSTEM')
SET ('memorymanager', 'global_allocation_limit') = '120000'
WITH RECONFIGURE;
```

**WARNING:** Always verify parameter changes. Wrong values can crash the database.
