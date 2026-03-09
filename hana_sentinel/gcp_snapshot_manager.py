#!/usr/bin/env python3
"""
GCP Disk Snapshot Manager using gcloud CLI
===========================================

Creates and manages disk snapshots for vlgdbzo3 instance.
Uses gcloud commands - no SSH needed!
"""

import os
import subprocess
import json
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

# Configuration
PROJECT = os.getenv("GOOGLE_CLOUD_PROJECT", "")
ZONE = os.getenv("GCP_TOOLKIT_ZONE", "")
INSTANCE = os.getenv("GCP_TOOLKIT_INSTANCE_NAME", "")

def run_gcloud(command):
    """Run gcloud command and return result"""
    try:
        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=120
        )
        return {
            "status": "success" if result.returncode == 0 else "error",
            "returncode": result.returncode,
            "stdout": result.stdout.strip(),
            "stderr": result.stderr.strip()
        }
    except subprocess.TimeoutExpired:
        return {"status": "error", "error": "Command timeout"}
    except Exception as e:
        return {"status": "error", "error": str(e)}

def list_instance_disks():
    """List all disks attached to the instance"""
    print("=" * 70)
    print("Listing Disks Attached to Instance")
    print("=" * 70)

    cmd = f"""gcloud compute instances describe {INSTANCE} \
        --zone={ZONE} \
        --project={PROJECT} \
        --format="json(disks)" """

    result = run_gcloud(cmd)

    if result["status"] == "success":
        try:
            data = json.loads(result["stdout"])
            disks = data.get("disks", [])

            print(f"Found {len(disks)} disk(s):\n")

            disk_names = []
            for i, disk in enumerate(disks, 1):
                source = disk.get("source", "")
                disk_name = source.split("/")[-1]
                device_name = disk.get("deviceName", "unknown")
                boot = disk.get("boot", False)

                print(f"{i}. Disk: {disk_name}")
                print(f"   Device: {device_name}")
                print(f"   Boot: {boot}")
                print()

                disk_names.append(disk_name)

            return disk_names
        except json.JSONDecodeError as e:
            print(f"Error parsing JSON: {e}")
            return []
    else:
        print(f"Error: {result.get('stderr', 'Unknown error')}")
        return []

def create_snapshot(disk_name, description=None):
    """Create a snapshot of a specific disk"""
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    snapshot_name = f"{disk_name}-snapshot-{timestamp}"

    print(f"\nCreating snapshot: {snapshot_name}")
    print(f"Source disk: {disk_name}")

    cmd = f"""gcloud compute disks snapshot {disk_name} \
        --snapshot-names={snapshot_name} \
        --zone={ZONE} \
        --project={PROJECT}"""

    if description:
        cmd += f' --description="{description}"'

    result = run_gcloud(cmd)

    if result["status"] == "success":
        print(f"[OK] Snapshot created successfully: {snapshot_name}")
        return {"status": "success", "snapshot_name": snapshot_name}
    else:
        print(f"[FAIL] Failed to create snapshot: {result.get('stderr')}")
        return {"status": "error", "error": result.get("stderr")}

def create_all_snapshots(description=None):
    """Create snapshots of all disks attached to the instance"""
    print("=" * 70)
    print("Creating Snapshots of All Instance Disks")
    print("=" * 70)
    print()

    disks = list_instance_disks()

    if not disks:
        print("No disks found or error listing disks")
        return

    results = []
    for disk_name in disks:
        result = create_snapshot(disk_name, description)
        results.append({"disk": disk_name, **result})

    print()
    print("=" * 70)
    print("Snapshot Summary")
    print("=" * 70)

    for result in results:
        status_icon = "[OK]" if result["status"] == "success" else "[FAIL]"
        print(f"{status_icon} {result['disk']}: {result.get('snapshot_name', 'FAILED')}")

    return results

def list_snapshots():
    """List all snapshots for this project"""
    print("=" * 70)
    print("Listing All Snapshots")
    print("=" * 70)

    cmd = f"""gcloud compute snapshots list \
        --project={PROJECT} \
        --format="table(name,sourceDisk.basename(),diskSizeGb,creationTimestamp)" \
        --filter="sourceDisk.scope()~{INSTANCE}" """

    result = run_gcloud(cmd)

    if result["status"] == "success":
        print(result["stdout"])
    else:
        print(f"Error: {result.get('stderr')}")

def delete_snapshot(snapshot_name):
    """Delete a specific snapshot"""
    print(f"\nDeleting snapshot: {snapshot_name}")

    cmd = f"""gcloud compute snapshots delete {snapshot_name} \
        --project={PROJECT} \
        --quiet"""

    result = run_gcloud(cmd)

    if result["status"] == "success":
        print(f"[OK] Snapshot deleted: {snapshot_name}")
        return {"status": "success"}
    else:
        print(f"[FAIL] Failed to delete snapshot: {result.get('stderr')}")
        return {"status": "error", "error": result.get("stderr")}

def main():
    """Main menu"""
    import sys

    if len(sys.argv) < 2:
        print("GCP Disk Snapshot Manager")
        print("=" * 70)
        print()
        print("Configuration:")
        print(f"  Project: {PROJECT}")
        print(f"  Zone: {ZONE}")
        print(f"  Instance: {INSTANCE}")
        print()
        print("Usage:")
        print("  python gcp_snapshot_manager.py list-disks")
        print("  python gcp_snapshot_manager.py list-snapshots")
        print("  python gcp_snapshot_manager.py create-all")
        print("  python gcp_snapshot_manager.py create <disk-name>")
        print("  python gcp_snapshot_manager.py delete <snapshot-name>")
        print()
        return

    command = sys.argv[1]

    if command == "list-disks":
        list_instance_disks()

    elif command == "list-snapshots":
        list_snapshots()

    elif command == "create-all":
        description = "Auto snapshot from HANA Sentinel"
        create_all_snapshots(description)

    elif command == "create":
        if len(sys.argv) < 3:
            print("Error: Missing disk name")
            print("Usage: python gcp_snapshot_manager.py create <disk-name>")
            return
        disk_name = sys.argv[2]
        description = "Manual snapshot from HANA Sentinel"
        create_snapshot(disk_name, description)

    elif command == "delete":
        if len(sys.argv) < 3:
            print("Error: Missing snapshot name")
            print("Usage: python gcp_snapshot_manager.py delete <snapshot-name>")
            return
        snapshot_name = sys.argv[2]
        delete_snapshot(snapshot_name)

    else:
        print(f"Unknown command: {command}")
        print("Valid commands: list-disks, list-snapshots, create-all, create, delete")

if __name__ == "__main__":
    main()
