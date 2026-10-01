"""Simulate daily inventory for every store x product family from real sales.

The public dataset has no stock levels, so we simulate a deliberately
imperfect baseline "store manager" policy:
  - Reviews stock every REVIEW_DAYS days and orders up to a target level.
  - Target = avg daily demand (last 28 days) * (LEAD_DAYS + REVIEW_DAYS) * bias
  - bias is random per store/family (0.75-1.5): some over-order, some under-order.
  - Orders arrive after LEAD_DAYS. Demand that can't be met is lost (stockout_qty).

Later phases replace this heuristic with ML forecasts and compare the two.
"""
import os

import numpy as np
import pandas as pd
import psycopg
from dotenv import load_dotenv

load_dotenv()
DB_URL = os.getenv("DATABASE_URL", "postgresql://retail:retail@localhost:5432/retail")

START, END = "2016-08-16", "2017-08-15"   # last 12 months of data
WINDOW = 28                               # days of history for the moving average
LEAD_DAYS, REVIEW_DAYS = 3, 7
BIAS_RANGE = (0.75, 1.5)
SEED = 42


def fetch_sales(conn):
    sql = """
        SELECT date, store_nbr, family, sales::float8
        FROM sales
        WHERE date > %s::date - %s AND date <= %s
        ORDER BY store_nbr, family, date
    """
    with conn.cursor() as cur:
        cur.execute(sql, (START, WINDOW + 5, END))
        rows = cur.fetchall()
    return pd.DataFrame(rows, columns=["date", "store_nbr", "family", "sales"])


def simulate(demand, warmup, bias):
    """Run the reorder policy over one series. Returns arrays for the sim period."""
    n = len(demand)
    on_hand = np.zeros(n)
    on_order = np.zeros(n)
    lost = np.zeros(n)
    arrivals = {}

    stock = demand[warmup - WINDOW:warmup].mean() * (LEAD_DAYS + REVIEW_DAYS) * bias
    outstanding = 0.0

    for t in range(warmup, n):
        arrived = arrivals.pop(t, 0.0)
        stock += arrived
        outstanding -= arrived

        sold = min(stock, demand[t])
        lost[t] = demand[t] - sold
        stock -= sold

        if (t - warmup) % REVIEW_DAYS == 0:
            avg = demand[t - WINDOW:t].mean()
            target = avg * (LEAD_DAYS + REVIEW_DAYS) * bias
            qty = max(0.0, target - stock - outstanding)
            if qty > 0:
                arrivals[t + LEAD_DAYS] = arrivals.get(t + LEAD_DAYS, 0.0) + qty
                outstanding += qty

        on_hand[t] = stock
        on_order[t] = outstanding

    return on_hand[warmup:], on_order[warmup:], lost[warmup:]


def main():
    rng = np.random.default_rng(SEED)
    with psycopg.connect(DB_URL) as conn:
        print("Fetching sales ...")
        df = fetch_sales(conn)
        start = pd.Timestamp(START).date()

        rows, total_demand, total_lost, stockout_days, sim_days = [], 0.0, 0.0, 0, 0
        skipped = 0

        for (store, family), g in df.groupby(["store_nbr", "family"], sort=False):
            dates = g["date"].to_numpy()
            demand = g["sales"].to_numpy()
            warmup = int((dates < start).sum())
            if warmup < WINDOW or demand[warmup:].sum() == 0:
                skipped += 1   # product never sold in this store
                continue

            bias = rng.uniform(*BIAS_RANGE)
            on_hand, on_order, lost = simulate(demand, warmup, bias)

            total_demand += demand[warmup:].sum()
            total_lost += lost.sum()
            stockout_days += int((lost > 1e-9).sum())
            sim_days += len(lost)

            for d, oh, oo, l in zip(dates[warmup:], on_hand, on_order, lost):
                rows.append((d, store, family, round(oh, 3), round(oo, 3), round(l, 3)))

        print(f"Simulated {len(rows):,} rows ({skipped} never-sold series skipped). Writing ...")
        with conn.cursor() as cur:
            cur.execute("TRUNCATE inventory_snapshots")
            with cur.copy(
                "COPY inventory_snapshots "
                "(date, store_nbr, family, on_hand, on_order, stockout_qty) FROM STDIN"
            ) as copy:
                for r in rows:
                    copy.write_row(r)
        conn.commit()

    print("\nBaseline policy results (what the ML system must beat):")
    print(f"  Fill rate:        {100 * (1 - total_lost / total_demand):.1f}% of demand met")
    print(f"  Stockout days:    {100 * stockout_days / sim_days:.1f}% of store-product-days")
    print(f"  Lost sales units: {total_lost:,.0f}")


if __name__ == "__main__":
    main()
