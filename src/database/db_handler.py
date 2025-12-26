import pymysql
from typing import Any, Optional, Sequence


class DBHandler:
    """
    MySQL Database Handler

    - Connection management
    - Transaction handling
    - Dict-based cursor
    """

    def __init__(self, config: dict):
        """
        config example:
        {
            "host": "localhost",
            "port": 3306,
            "user": "smartcart",
            "password": "password",
            "database": "smart_cart",
            "charset": "utf8mb4"
        }
        """
        self.config = config
        self._conn = None

    # =========================
    # Connection
    # =========================
    def _get_connection(self):
        if self._conn is None or not self._conn.open:
            self._conn = pymysql.connect(
                host=self.config["host"],
                port=self.config.get("port", 3306),
                user=self.config["user"],
                password=self.config["password"],
                database=self.config["database"],
                charset=self.config.get("charset", "utf8mb4"),
                cursorclass=pymysql.cursors.DictCursor,
                autocommit=False,  # 명시적 commit
            )
        return self._conn

    # =========================
    # Execute (INSERT / UPDATE / DELETE)
    # =========================
    def execute(
        self,
        sql: str,
        params: Optional[Sequence[Any]] = None,
        commit: bool = True,
    ) -> int:
        """
        Execute write query

        :return: affected rows
        """
        conn = self._get_connection()
        try:
            with conn.cursor() as cursor:
                affected = cursor.execute(sql, params)
            if commit:
                conn.commit()
            return affected
        except Exception:
            conn.rollback()
            raise

    # =========================
    # Fetch one
    # =========================
    def fetch_one(
        self,
        sql: str,
        params: Optional[Sequence[Any]] = None,
    ) -> Optional[dict]:
        conn = self._get_connection()
        with conn.cursor() as cursor:
            cursor.execute(sql, params)
            return cursor.fetchone()

    # =========================
    # Fetch all
    # =========================
    def fetch_all(
        self,
        sql: str,
        params: Optional[Sequence[Any]] = None,
    ) -> list[dict]:
        conn = self._get_connection()
        with conn.cursor() as cursor:
            cursor.execute(sql, params)
            return cursor.fetchall()

    # =========================
    # Transaction control
    # =========================
    def begin(self):
        conn = self._get_connection()
        conn.begin()

    def commit(self):
        conn = self._get_connection()
        conn.commit()

    def rollback(self):
        conn = self._get_connection()
        conn.rollback()

    # =========================
    # Close
    # =========================
    def close(self):
        if self._conn:
            self._conn.close()
            self._conn = None
