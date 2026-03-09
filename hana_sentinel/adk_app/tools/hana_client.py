import hdbcli.dbapi
import logging
from typing import List, Dict, Any, Optional


class HanaClient:
    def __init__(self, host: str, port: int, user: str, password: str):
        self.host = host
        self.port = port
        self.user = user
        self.password = password
        self.connection = None

    def connect(self):
        try:
            self.connection = hdbcli.dbapi.connect(
                address=self.host,
                port=self.port,
                user=self.user,
                password=self.password,
            )
            logging.info(f"Connected to HANA at {self.host}:{self.port}")
        except Exception as e:
            logging.error(f"Failed to connect to HANA: {e}")
            raise

    def execute_query(self, query: str) -> List[Dict[str, Any]]:
        if not self.connection:
            self.connect()

        cursor = self.connection.cursor()
        try:
            cursor.execute(query)
            columns = [col[0] for col in cursor.description]
            return [dict(zip(columns, row)) for row in cursor.fetchall()]
        except Exception as e:
            logging.error(f"Query failed: {e}")
            raise
        finally:
            cursor.close()

    def execute_statement(self, statement: str):
        if not self.connection:
            self.connect()

        cursor = self.connection.cursor()
        try:
            cursor.execute(statement)
            self.connection.commit()
            logging.info("Statement executed successfully")
        except Exception as e:
            logging.error(f"Statement failed: {e}")
            self.connection.rollback()
            raise
        finally:
            cursor.close()

    def close(self):
        if self.connection:
            self.connection.close()
