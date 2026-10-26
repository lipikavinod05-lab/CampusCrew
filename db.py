
import os
import mysql.connector
from mysql.connector import pooling
from dotenv import load_dotenv

load_dotenv()

class Database:
    """Creates a small MySQL connection pool for the CampusCrew app."""

    def __init__(self):
        self.config = {
            "host": os.getenv("DB_HOST", "localhost"),
            "port": int(os.getenv("DB_PORT", "3306")),
            "user": os.getenv("DB_USER", "root"),
            "password": os.getenv("DB_PASSWORD"),
            "database": os.getenv("DB_NAME", "campuscrew"),
        }
        self.pool = None

    def connect(self):
        if self.pool is None:
            self.pool = pooling.MySQLConnectionPool(
                pool_name="campuscrew_pool",
                pool_size=5,
                **self.config
            )
        return self.pool.get_connection()

db = Database()
