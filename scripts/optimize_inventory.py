"""Turn ML forecasts into reorder recommendations and stock alerts.

For each store x family, using the latest inventory snapshot:
  - Safety stock  = z * sigma_daily * sqrt(LEAD_DAYS + REVIEW_DAYS)
      sigma_daily = std of the model's daily errors in the backtest (per series)
  - Target level  = forecast demand over the next LEAD+REVIEW days + safety stock
  - Order qty     = max(0, target - on_hand - on_order)
  - Reorder point = forecast demand during the lead time + safety stock
Status (most urgent first):
  LOW_STOCK  on_hand can't cover demand until a new order could arrive
  OVERSTOCK  more than OVERSTOCK_DAYS of forecast demand on hand
  REORDER    inventory position is below target -> place an order
  OK         nothing to do
"""
import os

import numpy as np
import pandas as pd
import psycopg
from dotenv import load_dotenv

load_dotenv()
DB_URL = os.getenv("DATABASE_URL", "postgresql://retail:retail@localhost:5432/retail")

MODEL_VERSION = "lgbm_v1"
LEAD_DAYS, REVIEW_DAYS = 3, 7
SERVICE_Z = 1.645          # 95% cycle service level
OVERSTOCK_DAYS = 21
KEYS = ["store_nbr", "family"]


def fetch(conn):
    def q(sql, params=None):
        with conn.cursor() as cur:
            cur.execute(sql, params)
            cols = [d.name for d in cur.description]
            return pd.DataFrame(cur.fetchall(), columns=cols)

    snap = q("""
        SELECT date AS run_date, store_nbr, family, on_hand::float8, on_order::float8
        FROM inventory_snapshots
        WHERE date = (SELECT MAX(date) FROM inventory_snapshots)
    """)
    fc = q("""
        SELECT date, store_nbr, family, predicted::float8
        FROM forecasts WHERE model_version = %s ORDER BY date
    """, (MODEL_VERSION,))
    errors = q("""
        SELECT f.store_nbr, f.family, (s.sales - f.predicted)::float8 AS err
        FROM forecasts f JOIN sales s USING (date, store_nbr, family)
        WHERE f.model_version = %s
    """, (f"{MODEL_VERSION}_backtest",))
    return snap, fc, errors


def recommend(snap, fc, errors):
    fc = fc.sort_values(KEYS + ["date"]).copy()
    fc["day_n"] = fc.groupby(KEYS).cumcount() + 1
    P = LEAD_DAYS + REVIEW_DAYS

    demand = fc.groupby(KEYS).agg(
        avg_daily=("predicted", "mean"),
        lead_demand=("predicted", lambda s: s.iloc[:LEAD_DAYS].sum()),
        period_demand=("predicted", lambda s: s.iloc[:P].sum()),
    ).reset_index()

    sigma = errors.groupby(KEYS)["err"].std().rename("sigma").reset_index()

    df = snap.merge(demand, on=KEYS, how="inner").merge(sigma, on=KEYS, how="left")
    df["sigma"] = df["sigma"].fillna(0.0)

    df["safety_stock"] = SERVICE_Z * df["sigma"] * np.sqrt(P)
    df.loc[df["period_demand"] <= 0, "safety_stock"] = 0.0   # no forecast demand -> no buffer
    df["reorder_point"] = df["lead_demand"] + df["safety_stock"]
    target = df["period_demand"] + df["safety_stock"]
    position = df["on_hand"] + df["on_order"]
    df["order_qty"] = (target - position).clip(lower=0)
    df["days_cover"] = np.where(df["avg_daily"] > 0, df["on_hand"] / df["avg_daily"], np.inf)

    low = (df["on_hand"] < df["lead_demand"]) & (df["avg_daily"] > 0)
    over = (df["days_cover"] > OVERSTOCK_DAYS) & (df["on_hand"] > 0)
    reorder = df["order_qty"] > 0
    df["status"] = np.select([low, over, reorder], ["LOW_STOCK", "OVERSTOCK", "REORDER"], "OK")
    # Never order more for an overstocked item
    df.loc[df["status"] == "OVERSTOCK", "order_qty"] = 0.0

    for c in ["safety_stock", "reorder_point", "order_qty", "days_cover"]:
        df[c] = df[c].replace(np.inf, np.nan).round(3)
    return df


def save(conn, df):
    run_date = df["run_date"].iloc[0]
    with conn.cursor() as cur:
        cur.execute("DELETE FROM reorder_recommendations WHERE run_date = %s", (run_date,))
        with cur.copy(
            "COPY reorder_recommendations "
            "(run_date, store_nbr, family, reorder_point, safety_stock, order_qty, status) FROM STDIN"
        ) as cp:
            for r in df[["run_date", "store_nbr", "family", "reorder_point",
                         "safety_stock", "order_qty", "status"]].itertuples(index=False):
                cp.write_row(tuple(r))
    conn.commit()


def main():
    with psycopg.connect(DB_URL) as conn:
        snap, fc, errors = fetch(conn)
        df = recommend(snap, fc, errors)
        save(conn, df)

    print(f"Run date: {df['run_date'].iloc[0]}  |  {len(df):,} store-product recommendations\n")
    counts = df["status"].value_counts()
    for s in ["LOW_STOCK", "REORDER", "OVERSTOCK", "OK"]:
        print(f"  {s:<10} {counts.get(s, 0):>5}")
    print(f"\nTotal units to order: {df['order_qty'].sum():,.0f}")

    cols = ["store_nbr", "family", "on_hand", "lead_demand", "order_qty"]
    print("\nMost urgent LOW_STOCK items (biggest shortfall before delivery):")
    low = df[df["status"] == "LOW_STOCK"].assign(shortfall=lambda d: d["lead_demand"] - d["on_hand"])
    print(low.sort_values("shortfall", ascending=False)[cols + ["shortfall"]].head(10).round(1).to_string(index=False))

    print("\nWorst OVERSTOCK items (days of cover):")
    over = df[df["status"] == "OVERSTOCK"].sort_values("days_cover", ascending=False)
    print(over[["store_nbr", "family", "on_hand", "avg_daily", "days_cover"]].head(10).round(1).to_string(index=False))


if __name__ == "__main__":
    main()
