import os
import requests
from dotenv import load_dotenv

load_dotenv()

URL = os.getenv("REMOTE_EXEC_URL", "http://10.238.36.146:9999")
API_KEY = os.getenv("REMOTE_EXEC_API_KEY", "")
headers = {"X-API-Key": API_KEY}

print("=" * 70)
print("Testing Node Architecture Endpoints")
print("=" * 70)
print()

# Test 1: Node Info
print("-" * 70)
print("Test 1: Node Info (Architecture)")
print("-" * 70)
try:
    response = requests.get(f"{URL}/node/info", headers=headers, timeout=30)
    if response.status_code == 200:
        data = response.json()
        print(f"Node Type: {data.get('node_type')}")
        print(f"Instance: {data.get('instance_name')}")

        system = data.get('system', {})
        print(f"\nSystem:")
        print(f"  Hostname: {system.get('hostname')}")
        print(f"  OS: {system.get('os')}")
        print(f"  Architecture: {system.get('architecture')}")

        hardware = data.get('hardware', {})
        print(f"\nHardware:")
        print(f"  CPU Cores: {hardware.get('cpu_count')}")
        print(f"  Memory: {hardware.get('memory_gb')} GB")
        print(f"  HANA Disks: {len(hardware.get('disks', []))}")

        hana = data.get('hana', {})
        print(f"\nHANA:")
        print(f"  SID: {hana.get('sid')}")
        print(f"  Instance: {hana.get('instance_number')}")
        print(f"  User: {hana.get('user')}")

        print("\n[PASS]")
    else:
        print(f"[FAIL] Status {response.status_code}")
except Exception as e:
    print(f"[ERROR] {e}")

print()

# Test 2: Node Capabilities
print("-" * 70)
print("Test 2: Node Capabilities")
print("-" * 70)
try:
    response = requests.get(f"{URL}/node/capabilities", headers=headers, timeout=10)
    if response.status_code == 200:
        data = response.json()
        print(f"Node: {data.get('node_name')}")
        print(f"Type: {data.get('node_type')}")

        diagnostics = data.get('diagnostics', {})
        print(f"\nDiagnostics Available: {diagnostics.get('available')}")
        print(f"  Checks: {len(diagnostics.get('checks', []))}")

        healing = data.get('healing', {})
        print(f"\nHealing Available: {healing.get('available')}")
        print(f"  Operations: {len(healing.get('operations', []))}")

        for op in healing.get('operations', []):
            print(f"    - {op['name']}: {op['risk_level']} ({op['risk_points']} points)")

        print("\n[PASS]")
    else:
        print(f"[FAIL] Status {response.status_code}")
except Exception as e:
    print(f"[ERROR] {e}")

print()

# Test 3: System Health
print("-" * 70)
print("Test 3: System Health (Observability)")
print("-" * 70)
try:
    response = requests.get(f"{URL}/observability/system-health", headers=headers, timeout=30)
    if response.status_code == 200:
        data = response.json()
        print(f"Health Status: {data.get('health_status')}")
        print(f"Timestamp: {data.get('timestamp')}")

        memory = data.get('memory', {})
        print(f"\nMemory Status: {memory.get('status')}")

        disk = data.get('disk', {})
        print(f"Disk Status: {disk.get('status')}")

        sys_params = data.get('system_parameters', {})
        if sys_params.get('status') == 'success':
            params = sys_params.get('parameters', {})
            for param_name, param_data in params.items():
                status = param_data.get('status', 'unknown')
                value = param_data.get('value', 'N/A')
                print(f"  {param_name}: {value} [{status}]")

        print("\n[PASS]")
    else:
        print(f"[FAIL] Status {response.status_code}")
except Exception as e:
    print(f"[ERROR] {e}")

print()

# Test 4: Resource Utilization
print("-" * 70)
print("Test 4: Resource Utilization")
print("-" * 70)
try:
    response = requests.get(f"{URL}/observability/resource-utilization", headers=headers, timeout=30)
    if response.status_code == 200:
        data = response.json()
        print(f"Load Average: {data.get('load_average')}")

        mem = data.get('memory_details', {})
        if 'MemTotal' in mem:
            print(f"Memory Total: {mem.get('MemTotal')}")
            print(f"Memory Available: {mem.get('MemAvailable')}")

        print("\n[PASS]")
    else:
        print(f"[FAIL] Status {response.status_code}")
except Exception as e:
    print(f"[ERROR] {e}")

print()

# Test 5: Capacity Growth
print("-" * 70)
print("Test 5: Capacity Growth Analysis")
print("-" * 70)
try:
    response = requests.get(f"{URL}/capacity/growth-analysis", headers=headers, timeout=30)
    if response.status_code == 200:
        data = response.json()
        disk_summary = data.get('disk_usage', [])
        print(f"Monitored Disks: {len(disk_summary)}")

        for disk in disk_summary[:5]:  # Show first 5
            print(f"  {disk['mount']}: {disk['use_percent']} ({disk['used']}/{disk['size']})")

        print("\n[PASS]")
    else:
        print(f"[FAIL] Status {response.status_code}")
except Exception as e:
    print(f"[ERROR] {e}")

print()

# Test 6: Backup Status
print("-" * 70)
print("Test 6: Backup Status")
print("-" * 70)
try:
    response = requests.get(f"{URL}/operational/backup-status", headers=headers, timeout=10)
    if response.status_code == 200:
        data = response.json()
        backup_dirs = data.get('backup_directories', {})
        print(f"Backup Info Available: {backup_dirs.get('status')}")
        print("\n[PASS]")
    else:
        print(f"[FAIL] Status {response.status_code}")
except Exception as e:
    print(f"[ERROR] {e}")

print()

# Test 7: Version Info
print("-" * 70)
print("Test 7: Version Info")
print("-" * 70)
try:
    response = requests.get(f"{URL}/operational/version-info", headers=headers, timeout=30)
    if response.status_code == 200:
        data = response.json()
        print(f"HANA SID: {data.get('hana_sid')}")
        print(f"Instance: {data.get('instance_number')}")
        print(f"OS: {data.get('os_info')}")
        print("\n[PASS]")
    else:
        print(f"[FAIL] Status {response.status_code}")
except Exception as e:
    print(f"[ERROR] {e}")

print()
print("=" * 70)
print("Node Architecture Tests Complete!")
print("=" * 70)
