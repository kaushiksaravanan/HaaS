#!/bin/bash
# Backup Status Check
# Location: /home/zo3adm/diagnostics/check_backups.sh

# Check backup directories
echo "=== Backup Directories ==="
ls -lh /hdb/ZO3/backup/data 2>/dev/null || echo "Data backup dir not found"
ls -lh /hdb/ZO3/backup/log 2>/dev/null || echo "Log backup dir not found"

echo ""
echo "=== Recent Backups ==="
find /hdb/ZO3/backup -type f -mtime -1 2>/dev/null | head -10 || echo "No recent backups found"
