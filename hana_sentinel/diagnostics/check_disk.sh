#!/bin/bash
# Disk Usage Check
# Location: /home/zo3adm/diagnostics/check_disk.sh

# Check disk usage for HANA-related partitions
df -h | grep -E 'hana|hdb|ZO3|Filesystem'
