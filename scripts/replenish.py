"""Live replenishment: today's order quantities and stock alerts from the 10-day demand model.

Replaces optimize_inventory.py (which used the 16-day-lag daily model). Uses the
decision-focused model validated in compare_policies.py:
  1. Final model: trained on every origin whose 10-day outcome is known.
  2. Holdout model: trained ERR_WINDOW + P days earlier, scored on the last ERR_WINDOW
     origins -> out-of-sample RMSE per item, used to size safety stock.
  3. For each store x family (latest inventory snapshot):
       forecast_period = predicted demand over the next P = LEAD + REVIEW days
       safety_stock    = z * RMSE
       order_qty       = max(0, forecast_period + safety_stock - on_hand - on_order)
       reorder_point   = lead-time share of forecast + z * RMSE * sqrt(LEAD / P)
     Status: LOW_STOCK > OVERSTOCK > REORDER > OK
"""
import os
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import psycopg
from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).resolve().parent))
from compare_policies import (ERR_WINDOW, LEAD_DAYS, P, TRAIN_START,  # noqa: E402
                              FeatureBuilder, build_matrices, train_model)
from train_forecaster import load_data  # noqa: E402

load_dotenv()
DB_URL = os.getenv("DATABASE_URL", "postgresql://retail:retail@localhost:5432/retail")
ROOT = Path(__file__).resolve().parent.parent
MODEL_VERSION = "replenish_v1"
Z = 1.645
OVERSTOCK_DAYS = 21
KEYS = ["store_nbr", "family"]


def fetch_snapshot(conn):
    with conn.cursor() as cur:
        cur.execute("""
            SELECT date, store_nbr, family, on_hand::float8, on_order::float8
            FROM inventory_snapshots
            WHERE date = (SELECT MAX(date) FROM inventory_snapshots)
        """)
        return pd.DataFrame(cur.fetchall(), columns=["run_date"] + KEYS + ["on_hand", "on_order"])


def forecast_and_errors(A_df, PR, hol, payday, meta, hist_dates, all_dates):
    A = A_df.to_numpy()
    fb = FeatureBuilder(A, PR, hol, payday, meta, all_dates)
    t_last = len(hist_dates) - 1
    t0 = hist_dates.get_loc(TRAIN_START)

    # Holdout model -> out-of-sample errors on the last ERR_WINDOW origins with known outcomes
    eval_first, eval_last = t_last - P - ERR_WINDOW + 1, t_last - P
    print(f"Training holdout model (origins <= {hist_dates[eval_first - P - 1].date()}) ...")
    holdout, _ = train_model(fb, t0, eval_first - P - 1)
    def predict(model, t):   # nothing sold in the last 8 weeks -> forecast 0
        return np.where(fb.wsum(t, 56) > 0, np.clip(model.predict(fb.features(t)), 0, None), 0.0)

    errs = np.stack([fb.target(t) - predict(holdout, t) for t in range(eval_first, eval_last + 1)], axis=1)
    rmse = np.sqrt(np.mean(errs ** 2, axis=1))

    print(f"Training final model (origins <= {hist_dates[t_last - P - 1].date()}) ...")
    final, _ = train_model(fb, t0, t_last - P - 1)
    final.save_model(str(ROOT / "models" / f"{MODEL_VERSION}.txt"))
    forecast = predict(final, t_last)

    out = A_df.index.to_frame(index=False)
    out["forecast_period"] = forecast
    out["rmse"] = rmse
    return out, hist_dates[t_last]


def recommend(snap, fc):
    df = snap.merge(fc, on=KEYS, how="inner")
    df["safety_stock"] = np.where(df["forecast_period"] > 0, Z * df["rmse"], 0.0)
    lead_share = LEAD_DAYS / P
    df["lead_demand"] = df["forecast_period"] * lead_share
    df["reorder_point"] = df["lead_demand"] + df["safety_stock"] * np.sqrt(lead_share)
    target = df["forecast_period"] + df["safety_stock"]
    df["order_qty"] = (target - df["on_hand"] - df["on_order"]).clip(lower=0)
    daily = df["forecast_period"] / P
    df["days_cover"] = np.where(daily > 0, df["on_hand"] / daily, np.nan)

    low = (df["on_hand"] < df["lead_demand"]) & (daily > 0)
    over = (df["days_cover"] > OVERSTOCK_DAYS) & (df["on_hand"] > 0)
    reorder = df["order_qty"] > 0
    df["status"] = np.select([low, over, reorder], ["LOW_STOCK", "OVERSTOCK", "REORDER"], "OK")
    df.loc[df["status"] == "OVERSTOCK", "order_qty"] = 0.0
    return df


def save(conn, df):
    cols = ["run_date", "store_nbr", "family", "reorder_point", "safety_stock", "order_qty", "status",
            "on_hand", "on_order", "forecast_period", "days_cover", "model_version"]
    df = df.assign(model_version=MODEL_VERSION)
    with conn.cursor() as cur:
        for col, typ in [("on_hand", "NUMERIC(12,3)"), ("on_order", "NUMERIC(12,3)"),
                         ("forecast_period", "NUMERIC(12,3)"), ("days_cover", "NUMERIC(12,2)"),
                         ("model_version", "TEXT")]:
            cur.execute(f"ALTER TABLE reorder_recommendations ADD COLUMN IF NOT EXISTS {col} {typ}")
        cur.execute("DELETE FROM reorder_recommendations WHERE run_date = %s", (df["run_date"].iloc[0],))
        with cur.copy(f"COPY reorder_recommendations ({', '.join(cols)}) FROM STDIN") as cp:
            for r in df[cols].itertuples(index=False):
                cp.write_row([None if (isinstance(v, float) and np.isnan(v)) else
                              (round(v, 3) if isinstance(v, float) else v) for v in r])
    conn.commit()


def main():
    print("Loading data ...")
    sales, stores, holidays, future = load_data()
    mats = build_matrices(sales, stores, holidays, future)
    fc, last_day = forecast_and_errors(*mats)

    with psycopg.connect(DB_URL) as conn:
        snap = fetch_snapshot(conn)
        df = recommend(snap, fc)
        save(conn, df)

    print(f"\nRun date: {df['run_date'].iloc[0]} (data through {last_day.date()}) | "
          f"{len(df):,} recommendations | model {MODEL_VERSION}\n")
    counts = df["status"].value_counts()
    for s in ["LOW_STOCK", "REORDER", "OVERSTOCK", "OK"]:
        print(f"  {s:<10} {counts.get(s, 0):>5}")
    print(f"\nTotal units to order: {df['order_qty'].sum():,.0f}")

    pd.set_option("display.width", 200)
    low = df[df["status"] == "LOW_STOCK"].assign(shortfall=lambda d: d["lead_demand"] - d["on_hand"])
    print("\nMost urgent LOW_STOCK items:")
    print(low.sort_values("shortfall", ascending=False)
             [["store_nbr", "family", "on_hand", "lead_demand", "order_qty", "shortfall"]]
             .head(10).round(1).to_string(index=False))
    print("\nWorst OVERSTOCK items:")
    print(df[df["status"] == "OVERSTOCK"].sort_values("days_cover", ascending=False)
            [["store_nbr", "family", "on_hand", "forecast_period", "days_cover"]]
            .head(10).round(1).to_string(index=False))


if __name__ == "__main__":
    main()
