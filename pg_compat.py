import os
import re
import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv

load_dotenv(".env")

def get_neon_url():
    u = os.environ.get("DATABASE_URL", "").strip()
    if u.startswith("psql "):
        u = u[5:].strip()
    return u.strip("'\"")

class PgCursorWrapper:
    def __init__(self, cur, conn):
        self._cur = cur
        self._conn = conn

    @property
    def rowcount(self):
        return self._cur.rowcount

    @property
    def lastrowid(self):
        return None

    def _translate(self, sql):
        s = sql.replace("?", "%s")
        s = re.sub(r"INTEGER\s+PRIMARY\s+KEY\s+AUTOINCREMENT", "SERIAL PRIMARY KEY", s, flags=re.IGNORECASE)
        s = re.sub(r"AUTOINCREMENT", "", s, flags=re.IGNORECASE)
        s = re.sub(r"DATETIME\s+DEFAULT\s+CURRENT_TIMESTAMP", "TIMESTAMP DEFAULT CURRENT_TIMESTAMP", s, flags=re.IGNORECASE)
        return s

    def execute(self, sql, params=None):
        translated = self._translate(sql)
        try:
            if params is not None:
                self._cur.execute(translated, params)
            else:
                self._cur.execute(translated)
            return self
        except Exception:
            self._conn.rollback()
            raise

    def fetchone(self):
        return self._cur.fetchone()

    def fetchall(self):
        return self._cur.fetchall()

class PgConnWrapper:
    def __init__(self, dsn):
        self._conn = psycopg2.connect(dsn)
        self.row_factory = None

    def cursor(self):
        return PgCursorWrapper(self._conn.cursor(cursor_factory=RealDictCursor), self._conn)

    def commit(self):
        self._conn.commit()

    def rollback(self):
        self._conn.rollback()

    def close(self):
        self._conn.close()

def connect(_db_path=None):
    return PgConnWrapper(get_neon_url())
