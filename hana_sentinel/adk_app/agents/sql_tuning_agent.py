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
        Analyzes a specific SQL statement using EXPLAIN PLAN.
        """
        try:
            explain_query = f"EXPLAIN PLAN FOR {statement_string}"
            self.hana_client.execute_query(explain_query)
            plan_result = self.hana_client.execute_query(
                "SELECT OPERATOR_NAME, OPERATOR_DETAILS, TABLE_NAME, EXECUTION_ENGINE "
                "FROM EXPLAIN_PLAN_TABLE ORDER BY OPERATOR_ID"
            )
            if plan_result:
                plan_lines = []
                for row in plan_result:
                    op = row.get('OPERATOR_NAME', '')
                    details = row.get('OPERATOR_DETAILS', '')
                    table = row.get('TABLE_NAME', '')
                    engine = row.get('EXECUTION_ENGINE', '')
                    plan_lines.append(f"  {op} | {details} | table={table} | engine={engine}")
                return (
                    f"EXPLAIN PLAN for: {statement_string[:80]}...\n"
                    + "\n".join(plan_lines)
                )
            return (
                f"EXPLAIN PLAN executed for: {statement_string[:80]}... "
                "but returned no plan rows. The statement may be invalid or unsupported."
            )
        except Exception as e:
            return (
                f"Could not analyze statement: {statement_string[:80]}...\n"
                f"EXPLAIN PLAN failed: {str(e)}\n"
                "Check that the SQL syntax is valid and the referenced tables exist."
            )
