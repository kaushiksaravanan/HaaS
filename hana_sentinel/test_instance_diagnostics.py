#!/usr/bin/env python3
"""
Test Instance Diagnostics via HTTP API
=======================================

Tests the updated instance_diagnostics.py to ensure it works with HTTP API.
"""

import sys
import os

# Add adk_app to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dotenv import load_dotenv
from adk_app.tools.instance_diagnostics import InstanceDiagnostics, run_instance_diagnostic

load_dotenv()

print("=" * 70)
print("Testing Instance Diagnostics via HTTP API")
print("=" * 70)
print()

# Test 1: Initialize diagnostics
print("-" * 70)
print("Test 1: Initialize Instance Diagnostics")
print("-" * 70)
try:
    diagnostics = InstanceDiagnostics()
    print(f"Instance: {diagnostics.instance_name}")
    print(f"SID: {diagnostics.sid}")
    print(f"Zone: {diagnostics.zone}")
    print(f"HTTP Configured: {diagnostics.executor.is_configured()}")
    print("[PASS]")
except Exception as e:
    print(f"[FAIL] {e}")

print()

# Test 2: Run full diagnostic
print("-" * 70)
print("Test 2: Run Full Diagnostic")
print("-" * 70)
try:
    result = run_instance_diagnostic()

    print(f"Diagnostic ID: {result.get('diagnostic_id')}")
    print(f"Timestamp: {result.get('timestamp')}")
    print(f"Overall Status: {result.get('overall_status')}")
    print(f"Issues Detected: {result.get('issue_count')}")

    checks = result.get('checks', {})
    print(f"\nChecks Run: {len(checks)}")

    for check_name, check_result in checks.items():
        status = check_result.get('status')
        severity = check_result.get('severity', 'unknown')
        print(f"  {check_name}: {status} (severity: {severity})")

    if result.get('issues_detected'):
        print("\nIssues:")
        for issue in result.get('issues_detected', []):
            print(f"  - {issue}")

    print("\n[PASS]")
except Exception as e:
    print(f"[FAIL] {e}")

print()

# Test 3: Individual check - Process Status
print("-" * 70)
print("Test 3: Check HANA Process Status")
print("-" * 70)
try:
    diagnostics = InstanceDiagnostics()
    result = diagnostics.check_hana_process_status()

    print(f"Status: {result.get('status')}")
    print(f"Severity: {result.get('severity')}")
    print(f"All Green: {result.get('all_green')}")

    processes = result.get('processes', [])
    print(f"Processes: {len(processes)}")
    for proc in processes[:5]:
        print(f"  {proc.get('name')}: {proc.get('status')}")

    print("[PASS]")
except Exception as e:
    print(f"[FAIL] {e}")

print()

# Test 4: Individual check - System Health
print("-" * 70)
print("Test 4: Check Memory Usage")
print("-" * 70)
try:
    diagnostics = InstanceDiagnostics()
    result = diagnostics.check_memory_usage()

    print(f"Status: {result.get('status')}")
    print(f"Severity: {result.get('severity')}")
    print(f"Usage: {result.get('usage_percent')}%")

    memory_info = result.get('memory_info', {})
    print(f"Total: {memory_info.get('total')}")
    print(f"Used: {memory_info.get('used')}")
    print(f"Available: {memory_info.get('available')}")

    print("[PASS]")
except Exception as e:
    print(f"[FAIL] {e}")

print()

# Test 5: Individual check - Disk Usage
print("-" * 70)
print("Test 5: Check Disk Usage")
print("-" * 70)
try:
    diagnostics = InstanceDiagnostics()
    result = diagnostics.check_disk_usage()

    print(f"Status: {result.get('status')}")
    print(f"Severity: {result.get('severity')}")
    print(f"Max Usage: {result.get('max_usage')}%")

    partitions = result.get('partitions', [])
    print(f"Partitions: {len(partitions)}")
    for part in partitions[:5]:
        print(f"  {part.get('mount_point')}: {part.get('use_percent')}% ({part.get('size')})")

    print("[PASS]")
except Exception as e:
    print(f"[FAIL] {e}")

print()

# Test 6: Individual check - System Parameters
print("-" * 70)
print("Test 6: Check System Parameters")
print("-" * 70)
try:
    diagnostics = InstanceDiagnostics()
    result = diagnostics.check_system_parameters()

    print(f"Status: {result.get('status')}")
    print(f"Severity: {result.get('severity')}")
    print(f"All OK: {result.get('all_ok')}")

    parameters = result.get('parameters', {})
    for param_name, param_data in parameters.items():
        status = "[OK]" if param_data.get('ok') else "[FAIL]"
        print(f"  {param_name}: {param_data.get('value')} (expected: {param_data.get('expected')}) {status}")

    print("[PASS]")
except Exception as e:
    print(f"[FAIL] {e}")

print()
print("=" * 70)
print("Instance Diagnostics Tests Complete!")
print("=" * 70)
