from typing import List, Dict, Any
from ..tools.hana_client import HanaClient


class SQLTuningAgent:
    def __init__(self, hana_client: HanaClient):
        self.hana_client = hana_client
        self.name = "SQLTuningAgent"
        self.description = "Identifies and optimizes expensive SQL statements."

    def find_expensive_statements(self) -> List[Dict[str, Any]]:
        """
        Queries M_EXPENSIVE_STATEMENTS to find slow queries.
        """
        query = """
            SELECT TOP 10 STATEMENT_STRING, DURATION_MICROSEC, CPU_TIME, START_TIME
            FROM M_EXPENSIVE_STATEMENTS
            ORDER BY DURATION_MICROSEC DESC
        """
        return self.hana_client.execute_query(query)

    def analyze_statement(self, statement_string: str) -> str:
        """
        Analyzes a specific SQL statement.
        In a real scenario, this would use EXPLAIN PLAN and RAG.
        """
        # Placeholder for complex analysis logic
        return f"Analysis for: {statement_string[:50]}... -> Suggest adding index on frequently filtered columns."
