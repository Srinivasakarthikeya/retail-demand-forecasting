"""Database access helpers (psycopg 3, one short-lived connection per request)."""
import os
from contextlib import contextmanager

import psycopg
from dotenv import load_dotenv
from psycopg.rows import dict_row

load_dotenv()
DB_URL = os.getenv("DATABASE_URL", "postgresql://retail:retail@localhost:5432/retail")


@contextmanager
def connect():
    with psycopg.connect(DB_URL, row_factory=dict_row) as conn:
        yield conn


def fetch_all(sql: str, params: dict | tuple | None = None) -> list[dict]:
    with connect() as conn, conn.cursor() as cur:
        cur.execute(sql, params)
        return cur.fetchall()


def fetch_one(sql: str, params: dict | tuple | None = None) -> dict | None:
    rows = fetch_all(sql, params)
    return rows[0] if rows else None
