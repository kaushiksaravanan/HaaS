#!/bin/bash
# System Parameters Check
# Location: /home/zo3adm/diagnostics/check_system_params.sh

echo "=== System Parameters ==="
echo "Swappiness (should be 10):"
cat /proc/sys/vm/swappiness

echo ""
echo "Transparent Huge Pages (should be [never]):"
cat /sys/kernel/mm/transparent_hugepage/enabled

echo ""
echo "ASLR (should be 0):"
cat /proc/sys/kernel/randomize_va_space

echo ""
echo "Hostname:"
hostname
