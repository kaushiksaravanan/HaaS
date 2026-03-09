#!/usr/bin/env python3
"""
Boot Disk Snapshot Manager
===========================

Creates snapshots of ONLY the boot disk (not the huge 850GB data disk!)
"""

import os
import subprocess
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

PROJECT = os.getenv("GOOGLE_CLOUD_PROJECT", "")
ZONE = os.getenv("GCP_TOOLKIT_ZONE", "")
INSTANCE = os.getenv("GCP_TOOLKIT_INSTANCE_NAME", "")
BOOT_DISK = os.getenv("GCP_BOOT_DISK", "")  # Boot disk name

def create_boot_snapshot(description=None):
    """Create snapshot of boot disk only"""
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    snapshot_name = f"{BOOT_DISK}-snapshot-{timestamp}"

    print("=" * 70)
    print("Creating Boot Disk Snapshot")
    print("=" * 70)
    print(f"Snapshot name: {snapshot_name}")
    print(f"Boot disk: {BOOT_DISK} (20 GB)")
    print()

    cmd = f"""gcloud compute disks snapshot {BOOT_DISK} \
        --snapshot-names={snapshot_name} \
        --zone={ZONE} \
        --project={PROJECT}"""

    if description:
        cmd += f' --description="{description}"'

    try:
        result = subprocess.run(
            cmd,
            shell=True,
            capture_output=True,
            text=True,
            timeout=180
        )

        if result.returncode == 0:
            print("[OK] Snapshot created successfully!")
            print(f"Snapshot: {snapshot_name}")
            return {"status": "success", "snapshot_name": snapshot_name}
        else:
            print(f"[FAIL] {result.stderr}")
            return {"status": "error", "error": result.stderr}

    except Exception as e:
        print(f"[ERROR] {e}")
        return {"status": "error", "error": str(e)}

def list_boot_snapshots():
    """List boot disk snapshots only"""
    print("=" * 70)
    print("Boot Disk Snapshots")
    print("=" * 70)

    cmd = f"""gcloud compute snapshots list \
        --project={PROJECT} \
        --format="table(name,diskSizeGb,creationTimestamp,status)" \
        --filter="sourceDisk:{BOOT_DISK}" """

    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    print(result.stdout)

def delete_snapshot(snapshot_name):
    """Delete a snapshot"""
    print(f"Deleting snapshot: {snapshot_name}")

    cmd = f"""gcloud compute snapshots delete {snapshot_name} \
        --project={PROJECT} \
        --quiet"""

    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)

    if result.returncode == 0:
        print("[OK] Deleted")
    else:
        print(f"[FAIL] {result.stderr}")

if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Boot Disk Snapshot Manager")
        print("=" * 70)
        print()
        print(f"Boot disk: {BOOT_DISK} (20 GB)")
        print(f"Data disk: NOT SNAPSHOTTED (850 GB - too large!)")
        print()
        print("Usage:")
        print("  python boot_snapshot.py create")
        print("  python boot_snapshot.py list")
        print("  python boot_snapshot.py delete <snapshot-name>")
        print()
        sys.exit(0)

    command = sys.argv[1]

    if command == "create":
        create_boot_snapshot("HANA Sentinel auto snapshot")

    elif command == "list":
        list_boot_snapshots()

    elif command == "delete":
        if len(sys.argv) < 3:
            print("Error: Missing snapshot name")
            sys.exit(1)
        delete_snapshot(sys.argv[2])

    else:
        print(f"Unknown command: {command}")
        sys.exit(1)
