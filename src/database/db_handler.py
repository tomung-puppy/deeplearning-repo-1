import mysql.connector
from mysql.connector import pooling
import logging

class DBHandler:
    _instance = None
    _pool = None

    def __new__(cls, config=None):
        """싱글톤 패턴을 사용하여 하나의 커넥션 풀만 유지"""
        if cls._instance is None:
            cls._instance = super(DBHandler, cls).__new__(cls)
            if config:
                cls._instance._init_pool(config)
        return cls._instance

    def _init_pool(self, config):
        """AWS RDS 접속 정보로 커넥션 풀 초기화"""
        try:
            self._pool = pooling.MySQLConnectionPool(
                pool_name="cart_pool",
                pool_size=10,  # 동시 접속 대응을 위한 풀 크기
                host=config['host'],
                port=config.get('port', 3306),
                user=config['user'],
                password=config['password'],
                database=config['database']
            )
            print("DB Connection Pool initialized successfully.")
        except mysql.connector.Error as e:
            logging.error(f"Error creating connection pool: {e}")
            raise

    def get_connection(self):
        """풀에서 가용한 커넥션 하나를 반환"""
        if self._pool:
            return self._pool.get_connection()
        return None