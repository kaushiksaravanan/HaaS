from typing import Dict, Any
from ..tools.hana_client import HanaClient


class CapacityAgent:
    def __init__(self, hana_client: HanaClient):
        self.hana_client = hana_client
        self.name = "CapacityAgent"
        self.description = "Monitors and predicts capacity usage for disk and memory."

    def check_capacity_trends(self) -> Dict[str, Any]:
        """
        Analyzes growth trends.
        """
        # Simplified trend analysis
        disk_query = "SELECT SUM(USED_SIZE) as TOTAL_USED FROM M_DISK_USAGE"
        memory_query = "SELECT TOTAL_MEMORY_USED_SIZE FROM M_SERVICE_MEMORY"

        disk_usage = self.hana_client.execute_query(disk_query)
        memory_usage = self.hana_client.execute_query(memory_query)

        disk_total = disk_usage[0]["TOTAL_USED"] if disk_usage else None
        mem_total = memory_usage[0]["TOTAL_MEMORY_USED_SIZE"] if memory_usage else None

        return {
            "disk_total_used": disk_total if disk_total is not None else "unavailable",
            "memory_total_used": mem_total if mem_total is not None else "unavailable",
            "forecast": "unavailable — no trend data collected yet",
        }
