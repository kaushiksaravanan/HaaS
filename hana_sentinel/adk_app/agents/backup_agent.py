from typing import Dict, Any
from ..tools.hana_client import HanaClient
import datetime


class BackupAgent:
    def __init__(self, hana_client: HanaClient):
        self.hana_client = hana_client
        self.name = "BackupAgent"
        self.description = "Manages SAP HANA backups and verification."

    def check_backup_status(self) -> Dict[str, Any]:
        """
        Checks the status of the last backup.
        """
        query = """
            SELECT TOP 1 BACKUP_ID, STATE_NAME, SYS_END_TIME 
            FROM M_BACKUP_CATALOG 
            WHERE ENTRY_TYPE_NAME = 'COMPLETE DATA BACKUP' 
            ORDER BY SYS_END_TIME DESC
        """
        results = self.hana_client.execute_query(query)

        if not results:
            return {"status": "UNKNOWN", "message": "No backup found"}

        last_backup = results[0]
        backup_time = last_backup["SYS_END_TIME"]

        # Check if backup is older than 24 hours
        if (datetime.datetime.now() - backup_time).days > 1:
            return {
                "status": "WARNING",
                "message": "Last full backup is older than 24 hours",
            }

        if last_backup["STATE_NAME"] != "successful":
            return {
                "status": "CRITICAL",
                "message": f"Last backup failed with status: {last_backup['STATE_NAME']}",
            }

        return {"status": "OK", "message": "Backup is up to date and successful"}

    def trigger_backup(self, backup_prefix: str) -> str:
        """
        Triggers a data backup.
        """
        # This is a dangerous operation, would normally require risk budget check
        statement = f"BACKUP DATA USING FILE ('{backup_prefix}')"
        try:
            self.hana_client.execute_statement(statement)
            return "Backup initiated successfully"
        except Exception as e:
            return f"Backup failed: {e}"
