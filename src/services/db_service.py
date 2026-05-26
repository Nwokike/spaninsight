"""Database service — SQLAlchemy engine and query execution."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING
import pandas as pd
from sqlalchemy import create_engine, inspect, text

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


class DatabaseService:
    """Orchestrates database connections and metadata querying via SQLAlchemy."""

    @staticmethod
    def test_connection(connection_url: str) -> tuple[bool, str]:
        """Test if a database connection URL is valid and reachable."""
        try:
            if "sqlite" in connection_url:
                engine = create_engine(connection_url)
            else:
                engine = create_engine(
                    connection_url, connect_args={"connect_timeout": 5}
                )

            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            return True, "Connection successful!"
        except Exception as e:
            logger.error("Database connection test failed: %s", e)
            err_msg = str(e).split("\n")[0]
            if "timeout" in err_msg.lower():
                return (
                    False,
                    "Connection timed out. Please check host, port, or firewall settings.",
                )
            if "denied" in err_msg.lower():
                return False, "Access denied. Please check username and password."
            return False, f"Connection failed: {err_msg}"

    @staticmethod
    def list_tables(connection_url: str) -> list[str]:
        """Fetch a list of user table names from the database."""
        try:
            engine = create_engine(connection_url)
            inspector = inspect(engine)
            return sorted(inspector.get_table_names())
        except Exception as e:
            logger.error("Failed to list tables: %s", e)
            return []

    @staticmethod
    def load_table(
        connection_url: str, table_name: str, max_rows: int = 100000
    ) -> pd.DataFrame:
        """Load a database table into a DataFrame, capping rows to prevent OOM."""
        try:
            engine = create_engine(connection_url)
            query = text(
                'SELECT * FROM "' + table_name.replace('"', '""') + '" LIMIT :limit'
            )
            df = pd.read_sql_query(query, engine, params={"limit": max_rows})
            logger.info("Loaded table %s: %d rows", table_name, len(df))
            return df
        except Exception as e:
            logger.error("Failed to load table %s: %s", table_name, e)
            raise RuntimeError(f"Failed to read table: {e}")
