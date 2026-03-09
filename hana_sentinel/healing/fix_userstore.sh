#!/bin/bash
# Userstore Fix Script
# Location: /home/zo3adm/healing/fix_userstore.sh
# Risk: MEDIUM (6 points)

set -e

DRY_RUN="${DRY_RUN:-false}"

echo "=== Userstore Management Healing Script ==="
echo "Dry run: $DRY_RUN"
echo ""

# Check required keys
REQUIRED_KEYS=("BKPMON" "SAPDBCTRL" "SYSTEM" "TRANSPORT")

for key in "${REQUIRED_KEYS[@]}"; do
    echo "Checking key: $key"

    if hdbuserstore list | grep -q "$key"; then
        echo "  [OK] Key $key exists"
    else
        echo "  [WARNING] Key $key missing"

        if [ "$DRY_RUN" = "false" ]; then
            echo "  [ACTION] Would recreate key $key (manual configuration needed)"
            # Note: Actual key creation requires passwords, should be done manually
        fi
    fi
done

echo ""
echo "=== Userstore check complete ==="
