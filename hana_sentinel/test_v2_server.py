import os
import sys
import requests
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

# Load environment variables
from dotenv import load_dotenv
load_dotenv()

# Configuration
URL = os.getenv("REMOTE_EXEC_URL", "http://10.238.36.146:9999")
API_KEY = os.getenv("REMOTE_EXEC_API_KEY", "")

headers = {"X-API-Key": API_KEY}

print("=" * 70)
print("Testing Remote Exec Server V2")
print("=" * 70)
print()

# Test 1: Health check
print("-" * 70)
print("Test 1: Health Check")
print("-" * 70)
try:
    response = requests.get(f"{URL}/health", headers=headers, timeout=10)
    print(f"Status: {response.status_code}")
    if response.status_code == 200:
        data = response.json()
        print(f"Hostname: {data.get('hostname')}")
        print(f"User: {data.get('user')}")
        print(f"HANA SID: {data.get('hana_sid')}")
        print("[PASS]")
    else:
        print(f"[FAIL] {response.text}")
except Exception as e:
    print(f"[ERROR] {e}")

print()

# Test 2: Run diagnostics
print("-" * 70)
print("Test 2: Run Diagnostics")
print("-" * 70)
try:
    response = requests.get(f"{URL}/diagnostics", headers=headers, timeout=60)
    print(f"Status: {response.status_code}")
    if response.status_code == 200:
        data = response.json()
        print(f"Timestamp: {data.get('timestamp')}")

        diagnostics = data.get('diagnostics', {})
        for check_name, result in diagnostics.items():
            status = result.get('status', 'unknown')
            print(f"  {check_name}: {status}")

        print("[PASS]")
    else:
        print(f"[FAIL] {response.text}")
except Exception as e:
    print(f"[ERROR] {e}")

print()

# Test 3: List healing options
print("-" * 70)
print("Test 3: Healing Options")
print("-" * 70)
try:
    response = requests.get(f"{URL}/healing/options", headers=headers, timeout=10)
    print(f"Status: {response.status_code}")
    if response.status_code == 200:
        data = response.json()
        options = data.get('healing_options', [])
        print(f"Available healing operations: {len(options)}")
        for option in options:
            print(f"  - {option['name']}: {option['description']}")
            print(f"    Risk: {option['risk_level']} ({option['risk_points']} points)")
        print("[PASS]")
    else:
        print(f"[FAIL] {response.text}")
except Exception as e:
    print(f"[ERROR] {e}")

print()

# Test 4: Execute healing (dry run)
print("-" * 70)
print("Test 4: Execute Healing (Dry Run)")
print("-" * 70)
try:
    response = requests.post(
        f"{URL}/healing/execute/trace_cleanup?dry_run=true",
        headers=headers,
        timeout=30
    )
    print(f"Status: {response.status_code}")
    if response.status_code == 200:
        data = response.json()
        print(f"Operation: {data.get('operation')}")
        print(f"Dry Run: {data.get('dry_run')}")
        print(f"Actions: {data.get('actions', [])}")
        print("[PASS]")
    else:
        print(f"[FAIL] {response.text}")
except Exception as e:
    print(f"[ERROR] {e}")

print()
print("=" * 70)
print("V2 Server Test Complete!")
print("=" * 70)
