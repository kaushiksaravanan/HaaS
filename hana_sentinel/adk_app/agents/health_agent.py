from typing import Dict, Any
from ..tools.hana_client import HanaClient


class HealthAgent:
    def __init__(self, hana_client: HanaClient):
        self.hana_client = hana_client
        self.name = "HealthAgent"
        self.description = (
            "Monitors SAP HANA system health including memory, disk, and services."
        )

    def check_system_health(self) -> Dict[str, Any]:
        """
        Checks the overall health of the HANA system.
        """
        health_status = {
            "services": self._check_services(),
            "disk_usage": self._check_disk_usage(),
            # Add more checks as needed
        }
        return health_status

    def _check_services(self) -> str:
        query = "SELECT SERVICE_NAME, ACTIVE_STATUS FROM M_SERVICES"
        results = self.hana_client.execute_query(query)
        # Simple logic: if any service is not active, return warning
        all_active = all(r["ACTIVE_STATUS"] == "YES" for r in results)
        return "OK" if all_active else "WARNING: Some services are down"

    def _check_disk_usage(self) -> str:
        query = "SELECT USAGE_TYPE, USED_SIZE, TOTAL_SIZE FROM M_DISK_USAGE"
        results = self.hana_client.execute_query(query)
        # Logic to check if any disk is > 90% full
        for disk in results:
            if (
                disk["TOTAL_SIZE"] > 0
                and (disk["USED_SIZE"] / disk["TOTAL_SIZE"]) > 0.9
            ):
                return "CRITICAL: Disk usage above 90%"
        return "OK"
