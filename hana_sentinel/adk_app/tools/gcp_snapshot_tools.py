"""
GCP Snapshot Tools — Create and manage VM snapshots for HANA instances.
Implements daily VM snapshot backup strategy for vlgdbzo3 instance.
"""

import os
import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional
from google.cloud import compute_v1
from adk_app.tools.gcloud_auth import get_service_account_credentials

logger = logging.getLogger(__name__)


class GCPSnapshotManager:
    """Manages VM snapshots for GCP Compute instances."""

    def __init__(
        self,
        project_id: str = None,
        zone: str = None,
        instance_name: str = None
    ):
        """Initialize snapshot manager.

        Args:
            project_id: GCP project ID (defaults to GCP_TOOLKIT_PROJECT_ID from env)
            zone: GCP zone (defaults to GCP_TOOLKIT_ZONE from env)
            instance_name: Instance name (defaults to GCP_TOOLKIT_INSTANCE_NAME from env)
        """
        self.project_id = project_id or os.getenv("GCP_TOOLKIT_PROJECT_ID", "")
        self.zone = zone or os.getenv("GCP_TOOLKIT_ZONE", "us-central1-a")
        self.instance_name = instance_name or os.getenv("GCP_TOOLKIT_INSTANCE_NAME", "")

        if not self.project_id or not self.instance_name:
            raise ValueError("Project ID and instance name must be provided")

        # Get authenticated credentials
        credentials = get_service_account_credentials()
        if not credentials:
            raise ValueError("Service account credentials not available. Call authenticate_with_service_key() first.")

        # Initialize compute clients
        self.disks_client = compute_v1.DisksClient(credentials=credentials)
        self.snapshots_client = compute_v1.SnapshotsClient(credentials=credentials)
        self.instances_client = compute_v1.InstancesClient(credentials=credentials)

    def get_instance_disks(self) -> List[str]:
        """Get list of disk names attached to the instance.

        Returns:
            List of disk names
        """
        try:
            instance = self.instances_client.get(
                project=self.project_id,
                zone=self.zone,
                instance=self.instance_name
            )

            disk_names = []
            for disk in instance.disks:
                # Extract disk name from source URL
                # Format: https://www.googleapis.com/compute/v1/projects/{project}/zones/{zone}/disks/{disk}
                disk_name = disk.source.split('/')[-1]
                disk_names.append(disk_name)

            logger.info(f"Found {len(disk_names)} disks for instance {self.instance_name}: {disk_names}")
            return disk_names

        except Exception as e:
            logger.error(f"Failed to get instance disks: {e}")
            raise

    def create_snapshot(
        self,
        disk_name: str,
        snapshot_name: str = None,
        description: str = None
    ) -> Dict[str, str]:
        """Create a snapshot of a disk.

        Args:
            disk_name: Name of the disk to snapshot
            snapshot_name: Name for the snapshot (auto-generated if None)
            description: Snapshot description

        Returns:
            dict with snapshot details
        """
        if not snapshot_name:
            timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
            snapshot_name = f"{self.instance_name}-{disk_name}-{timestamp}"

        if not description:
            description = f"Daily snapshot of {disk_name} for {self.instance_name}"

        try:
            logger.info(f"Creating snapshot {snapshot_name} for disk {disk_name}")

            snapshot_resource = compute_v1.Snapshot()
            snapshot_resource.name = snapshot_name
            snapshot_resource.description = description
            snapshot_resource.source_disk = f"projects/{self.project_id}/zones/{self.zone}/disks/{disk_name}"

            operation = self.disks_client.create_snapshot(
                project=self.project_id,
                zone=self.zone,
                disk=disk_name,
                snapshot_resource=snapshot_resource
            )

            # Wait for operation to complete
            logger.info(f"Snapshot creation initiated. Operation: {operation.name}")

            return {
                "status": "success",
                "snapshot_name": snapshot_name,
                "disk_name": disk_name,
                "operation": operation.name,
                "timestamp": datetime.now().isoformat()
            }

        except Exception as e:
            logger.error(f"Failed to create snapshot: {e}")
            return {
                "status": "error",
                "error_message": str(e),
                "disk_name": disk_name
            }

    def create_daily_snapshot(self) -> Dict[str, Any]:
        """Create daily snapshot of all instance disks.

        Only creates one snapshot per day. Checks if snapshot already exists for today.

        Returns:
            dict with results for each disk
        """
        results = {
            "status": "success",
            "instance": self.instance_name,
            "snapshots": [],
            "skipped": [],
            "errors": []
        }

        try:
            # Get all disks for instance
            disk_names = self.get_instance_disks()

            # Check existing snapshots for today
            today = datetime.now().strftime("%Y%m%d")

            for disk_name in disk_names:
                # Check if snapshot already exists for today
                existing = self.get_snapshots_for_disk(disk_name, days=1)

                # Filter for today's snapshots
                today_snapshots = [
                    s for s in existing
                    if s['creation_time'].startswith(today)
                ]

                if today_snapshots:
                    logger.info(f"Snapshot already exists for {disk_name} today: {today_snapshots[0]['name']}")
                    results['skipped'].append({
                        "disk_name": disk_name,
                        "reason": "Snapshot already exists for today",
                        "existing_snapshot": today_snapshots[0]['name']
                    })
                    continue

                # Create snapshot
                result = self.create_snapshot(
                    disk_name=disk_name,
                    description=f"Daily snapshot - {datetime.now().strftime('%Y-%m-%d')}"
                )

                if result['status'] == 'success':
                    results['snapshots'].append(result)
                else:
                    results['errors'].append(result)

            if results['errors']:
                results['status'] = 'partial' if results['snapshots'] else 'error'

            logger.info(f"Daily snapshot completed: {len(results['snapshots'])} created, {len(results['skipped'])} skipped, {len(results['errors'])} errors")
            return results

        except Exception as e:
            logger.error(f"Failed to create daily snapshots: {e}")
            return {
                "status": "error",
                "error_message": str(e),
                "instance": self.instance_name
            }

    def get_snapshots_for_disk(
        self,
        disk_name: str,
        days: int = 7
    ) -> List[Dict[str, str]]:
        """Get recent snapshots for a specific disk.

        Args:
            disk_name: Name of the disk
            days: Number of days to look back

        Returns:
            List of snapshot details
        """
        try:
            # List all snapshots in project
            request = compute_v1.ListSnapshotsRequest(project=self.project_id)
            snapshots = self.snapshots_client.list(request=request)

            # Filter for this disk
            cutoff_date = datetime.now() - timedelta(days=days)
            disk_source = f"projects/{self.project_id}/zones/{self.zone}/disks/{disk_name}"

            matching_snapshots = []
            for snapshot in snapshots:
                # Check if snapshot is for this disk
                if snapshot.source_disk and disk_source in snapshot.source_disk:
                    # Parse creation timestamp
                    creation_time = snapshot.creation_timestamp

                    # Add to list
                    matching_snapshots.append({
                        "name": snapshot.name,
                        "id": str(snapshot.id),
                        "creation_time": creation_time,
                        "description": snapshot.description or "",
                        "disk_size_gb": snapshot.disk_size_gb,
                        "status": snapshot.status
                    })

            # Sort by creation time (newest first)
            matching_snapshots.sort(key=lambda x: x['creation_time'], reverse=True)

            logger.info(f"Found {len(matching_snapshots)} snapshots for {disk_name} in last {days} days")
            return matching_snapshots

        except Exception as e:
            logger.error(f"Failed to list snapshots: {e}")
            return []

    def get_all_snapshots(self) -> List[Dict[str, str]]:
        """Get all snapshots for the instance.

        Returns:
            List of all snapshot details
        """
        try:
            disk_names = self.get_instance_disks()

            all_snapshots = []
            for disk_name in disk_names:
                snapshots = self.get_snapshots_for_disk(disk_name, days=365)  # Get all from last year
                all_snapshots.extend(snapshots)

            # Sort by creation time (newest first)
            all_snapshots.sort(key=lambda x: x['creation_time'], reverse=True)

            logger.info(f"Found {len(all_snapshots)} total snapshots for instance {self.instance_name}")
            return all_snapshots

        except Exception as e:
            logger.error(f"Failed to get all snapshots: {e}")
            return []

    def get_snapshot_details(self, snapshot_name: str) -> Optional[Dict[str, Any]]:
        """Get details of a specific snapshot.

        Args:
            snapshot_name: Name of the snapshot

        Returns:
            Snapshot details or None if not found
        """
        try:
            snapshot = self.snapshots_client.get(
                project=self.project_id,
                snapshot=snapshot_name
            )

            return {
                "name": snapshot.name,
                "id": str(snapshot.id),
                "creation_time": snapshot.creation_timestamp,
                "description": snapshot.description or "",
                "disk_size_gb": snapshot.disk_size_gb,
                "storage_bytes": snapshot.storage_bytes,
                "storage_bytes_status": snapshot.storage_bytes_status,
                "status": snapshot.status,
                "source_disk": snapshot.source_disk,
                "self_link": snapshot.self_link
            }

        except Exception as e:
            logger.error(f"Failed to get snapshot details: {e}")
            return None


# Convenience functions for ADK tools

def create_instance_snapshot(
    instance_name: str = None,
    project_id: str = None,
    zone: str = None
) -> Dict[str, Any]:
    """Create daily snapshot for HANA instance.

    Args:
        instance_name: Instance name (defaults to env)
        project_id: Project ID (defaults to env)
        zone: Zone (defaults to env)

    Returns:
        Snapshot creation results
    """
    try:
        manager = GCPSnapshotManager(
            project_id=project_id,
            zone=zone,
            instance_name=instance_name
        )

        return manager.create_daily_snapshot()

    except Exception as e:
        logger.error(f"Failed to create instance snapshot: {e}")
        return {
            "status": "error",
            "error_message": str(e)
        }


def list_instance_snapshots(
    instance_name: str = None,
    project_id: str = None,
    zone: str = None
) -> List[Dict[str, str]]:
    """List all snapshots for HANA instance.

    Args:
        instance_name: Instance name (defaults to env)
        project_id: Project ID (defaults to env)
        zone: Zone (defaults to env)

    Returns:
        List of snapshots
    """
    try:
        manager = GCPSnapshotManager(
            project_id=project_id,
            zone=zone,
            instance_name=instance_name
        )

        return manager.get_all_snapshots()

    except Exception as e:
        logger.error(f"Failed to list instance snapshots: {e}")
        return []
