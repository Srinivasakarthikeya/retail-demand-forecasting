"""Bulk-load the Favorita CSVs into Postgres using COPY (fast for ~3M rows)."""
import os
from pathlib import Path

import psycopg
from dotenv import load_dotenv

load_dotenv()
DB_URL = os.getenv("DATABASE_URL", "postgresql://retail:retail@localhost:5432/retail")
RAW = Path(__file__).resolve().parent.parent / "data" / "raw"

# Order matters: stores first (FK target).
TABLES = [
    ("stores",       "stores.csv",          "store_nbr, city, state, type, cluster"),
    ("holidays",     "holidays_events.csv", "date, type, locale, locale_name, description, transferred"),
    ("oil",          "oil.csv",             "date, dcoilwtico"),
    ("transactions", "transactions.csv",    "date, store_nbr, transactions"),
    ("sales",        "train.csv",           "id, date, store_nbr, family, sales, onpromotion"),
]


def copy_csv(cur, table, filename, columns):
    path = RAW / filename
    if not path.exists():
        raise FileNotFoundError(f"{path} missing - run scripts/download_data.sh")
    sql = f"COPY {table} ({columns}) FROM STDIN WITH (FORMAT csv, HEADER true)"
    with cur.copy(sql) as copy, open(path, "rb") as fh:
        while chunk := fh.read(1 << 20):
            copy.write(chunk)


def main():
    with psycopg.connect(DB_URL) as conn, conn.cursor() as cur:
        cur.execute(
            "TRUNCATE sales, transactions, oil, holidays, stores RESTART IDENTITY CASCADE"
        )
        for table, filename, columns in TABLES:
            print(f"Loading {filename:<22} -> {table} ...", end=" ", flush=True)
            copy_csv(cur, table, filename, columns)
            cur.execute(f"SELECT COUNT(*) FROM {table}")
            print(f"{cur.fetchone()[0]:,} rows")
        conn.commit()

        cur.execute("""
            SELECT MIN(date), MAX(date), COUNT(DISTINCT store_nbr), COUNT(DISTINCT family)
            FROM sales
        """)
        lo, hi, n_stores, n_fam = cur.fetchone()
        print(f"\nSales: {lo} -> {hi} | {n_stores} stores | {n_fam} product families")


if __name__ == "__main__":
    main()
