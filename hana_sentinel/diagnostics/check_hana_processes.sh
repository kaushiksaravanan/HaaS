#!/bin/bash
# HANA Process Status Check
# Location: /home/zo3adm/diagnostics/check_hana_processes.sh

INSTANCE_NR="${INSTANCE_NR:-00}"

# Run sapcontrol to check process list
sapcontrol -nr "$INSTANCE_NR" -function GetProcessList 2>&1
