"""Head-to-head inventory simulation over 12 months of real demand (v3).

Lesson from v1/v2: the daily forecaster (train_forecaster.py) only uses lags >= 16 days,
because it was built for a 16-day-ahead benchmark. At a review day it therefore knows less
than a simple 28-day average that uses data up to today. v3 trains a decision-focused model:

  target   = total demand over the next P = LEAD_DAYS + REVIEW_DAYS days
  features = everything known on the review day (recent averages up to today, same period
             last year, promotions planned for the next P days, holidays/paydays, store, family)
  loss     = Tweedie on raw units (predicts the mean, no log bias)

Policies (same simulator: LEAD_DAYS delivery delay, review every REVIEW_DAYS):
  1. Store manager - order up to 28-day avg * P * bias (bias per item 0.75-1.5), no safety stock
  2. Textbook      - order up to 28-day avg * P + z * daily_std * sqrt(P)
  3. ML            - order up to forecast of next-P-day demand + z * RMSE of past P-day forecasts

No leakage: models are retrained every RETRAIN_DAYS on origins whose P-day target was fully
observed before the period started; error RMSE uses only forecasts whose outcome is known.
"""
import json
import sys
from pathlib import Path

import lightgbm as lgb
import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from train_forecaster import load_data  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
KEYS = ["store_nbr", "family"]
HISTORY_START = pd.Timestamp("2014-01-01")
TRAIN_START = pd.Timestamp("2015-01-01")
SIM_START, SIM_END = pd.Timestamp("2016-08-16"), pd.Timestamp("2017-08-15")
LEAD_DAYS, REVIEW_DAYS = 3, 7
P = LEAD_DAYS + REVIEW_DAYS
ERR_WINDOW = 56
RETRAIN_DAYS = 91
ORIGIN_STEP = 2            # training origins every 2 days
Z_GRID = [0.5, 1.0, 1.645, 2.33]
MAIN_Z = 1.645
OVERSTOCK_DAYS = 21
SEED = 42

PARAMS = {
    "objective": "tweedie", "tweedie_variance_power": 1.2,
    "learning_rate": 0.05, "num_leaves": 127, "min_data_in_leaf": 100,
    "feature_fraction": 0.8, "bagging_fraction": 0.8, "bagging_freq": 1,
    "lambda_l2": 1.0, "verbose": -1, "seed": 42,
}
N_ROUNDS = 600


# ------------------------------------------------------------------ matrices
def build_matrices(sales, stores, holidays, future):
    sales = sales.copy()
    future = future.copy()
    sales["date"] = pd.to_datetime(sales["date"])
    future["date"] = pd.to_datetime(future["date"])
    hist_dates = pd.date_range(HISTORY_START, sales["date"].max(), freq="D")
    all_dates = pd.date_range(HISTORY_START, future["date"].max(), freq="D")

    A = (sales.pivot_table(index=KEYS, columns="date", values="sales", observed=True)
              .reindex(columns=hist_dates).fillna(0.0))
    promo_src = pd.concat([sales[["date"] + KEYS + ["onpromotion"]], future[["date"] + KEYS + ["onpromotion"]]])
    PR = (promo_src.pivot_table(index=KEYS, columns="date", values="onpromotion", observed=True)
                   .reindex(index=A.index, columns=all_dates).fillna(0.0))

    h = holidays[(~holidays["transferred"]) & (holidays["type"] != "Work Day") & (holidays["locale"] == "National")]
    hol = all_dates.isin(pd.to_datetime(h["date"])).astype(float)
    payday = ((all_dates.day == 15) | all_dates.is_month_end).astype(float)

    meta = A.index.to_frame(index=False).merge(stores, on="store_nbr", how="left")
    meta["family_code"] = meta["family"].astype("category").cat.codes
    meta["type_code"] = meta["type"].astype("category").cat.codes
    return A, PR.to_numpy(), hol, payday, meta, hist_dates, all_dates


class FeatureBuilder:
    def __init__(self, A, PR, hol, payday, meta, all_dates):
        self.A = A
        self.cs = np.concatenate([np.zeros((A.shape[0], 1)), np.cumsum(A, axis=1)], axis=1)
        self.cs2 = np.concatenate([np.zeros((A.shape[0], 1)), np.cumsum(A ** 2, axis=1)], axis=1)
        self.PR, self.hol, self.payday, self.meta, self.dates = PR, hol, payday, meta, all_dates

    def wsum(self, t, w, cs=None):
        cs = self.cs if cs is None else cs
        return cs[:, t + 1] - cs[:, t + 1 - w]

    def features(self, t):
        f = {}
        for w in (7, 14, 28, 56):
            f[f"m{w}"] = self.wsum(t, w) / w
        var = self.wsum(t, 28, self.cs2) / 28 - f["m28"] ** 2
        f["std28"] = np.sqrt(np.clip(var, 0, None))
        f["ly_next"] = self.cs[:, t - 364 + P + 1] - self.cs[:, t - 364 + 1]   # same P days last year
        f["ly_m28"] = self.wsum(t - 364, 28) / 28
        f["promo_next"] = self.PR[:, t + 1:t + 1 + P].sum(axis=1)
        f["promo_m28"] = self.PR[:, t - 27:t + 1].mean(axis=1)
        n = self.A.shape[0]
        f["hol_next"] = np.full(n, self.hol[t + 1:t + 1 + P].sum())
        f["payday_next"] = np.full(n, self.payday[t + 1:t + 1 + P].sum())
        f["dow"] = np.full(n, self.dates[t].dayofweek)
        f["month"] = np.full(n, self.dates[t + P // 2].month)
        f["store_nbr"] = self.meta["store_nbr"].to_numpy()
        f["family_code"] = self.meta["family_code"].to_numpy()
        f["type_code"] = self.meta["type_code"].to_numpy()
        f["cluster"] = self.meta["cluster"].to_numpy()
        return pd.DataFrame(f)

    def target(self, t):
        return self.cs[:, t + P + 1] - self.cs[:, t + 1]


CATS = ["store_nbr", "family_code", "type_code", "cluster"]


def train_model(fb, t_first, t_last):
    X = pd.concat([fb.features(t) for t in range(t_first, t_last + 1, ORIGIN_STEP)], ignore_index=True)
    y = np.concatenate([fb.target(t) for t in range(t_first, t_last + 1, ORIGIN_STEP)])
    return lgb.train(PARAMS, lgb.Dataset(X, y, categorical_feature=CATS), num_boost_round=N_ROUNDS), len(X)


# ------------------------------------------------------------------ simulation
def simulate(actual, s0, e0, target_fn):
    n, T = actual.shape
    stock = actual[:, s0 - 28:s0].mean(axis=1) * P
    outstanding = np.zeros(n)
    arrivals = np.zeros((n, T + LEAD_DAYS + 1))
    on_hand = np.zeros((n, e0 - s0 + 1))
    lost = np.zeros_like(on_hand)
    for k, t in enumerate(range(s0, e0 + 1)):
        stock += arrivals[:, t]
        outstanding -= arrivals[:, t]
        sold = np.minimum(stock, actual[:, t])
        lost[:, k] = actual[:, t] - sold
        stock -= sold
        if k % REVIEW_DAYS == 0:
            qty = np.clip(target_fn(t) - stock - outstanding, 0, None)
            arrivals[:, t + LEAD_DAYS] += qty
            outstanding += qty
        on_hand[:, k] = stock
    return on_hand, lost


def summarise(name, z, actual, on_hand, lost, s0, e0):
    demand = actual[:, s0:e0 + 1]
    avg_d = demand.mean(axis=1, keepdims=True)
    cover = np.divide(on_hand, avg_d, out=np.full_like(on_hand, np.nan), where=avg_d > 0)
    return {"policy": name, "z": z,
            "fill_rate_%": 100 * (1 - lost.sum() / demand.sum()),
            "stockout_days_%": 100 * (lost > 1e-9).mean(),
            "lost_units": float(lost.sum()),
            "avg_inventory_units": float(on_hand.sum(axis=0).mean()),
            "overstock_days_%": 100 * np.nanmean(cover > OVERSTOCK_DAYS)}


# ------------------------------------------------------------------ main
def main():
    print("Loading data ...")
    sales, stores, holidays, future = load_data()
    A_df, PR, hol, payday, meta, hist_dates, all_dates = build_matrices(sales, stores, holidays, future)
    A = A_df.to_numpy()
    fb = FeatureBuilder(A, PR, hol, payday, meta, all_dates)

    idx = hist_dates.get_loc
    s0, e0 = idx(SIM_START), idx(SIM_END)
    warm = s0 - ERR_WINDOW - P                     # forecasts from here feed the first error window
    t_train0 = idx(TRAIN_START)

    # Retraining schedule: (first origin served, last origin served)
    starts = [warm] + [idx(d) for d in pd.date_range(SIM_START + pd.Timedelta(days=RETRAIN_DAYS),
                                                      SIM_END - pd.Timedelta(days=30), freq=f"{RETRAIN_DAYS}D")]
    pred = np.full(A.shape, np.nan)                # pred[:, t] = forecast of next-P-day demand made at t
    print("Training decision-focused models (quarterly retraining) ...")
    for i, a in enumerate(starts):
        b = starts[i + 1] - 1 if i + 1 < len(starts) else e0
        model, n_rows = train_model(fb, t_train0, a - P - 1)   # targets fully known before day a
        print(f"  Model {i + 1}/{len(starts)}: origins <= {hist_dates[a - P - 1].date()} "
              f"({n_rows:,} rows), serves {hist_dates[a].date()} -> {hist_dates[b].date()}")
        for t in range(a, b + 1):
            pred[:, t] = np.clip(model.predict(fb.features(t)), 0, None)

    # Realised P-day errors (known only P days after the forecast)
    err = np.full(A.shape, np.nan)
    for t in range(warm, e0 - P + 1):
        err[:, t] = fb.target(t) - pred[:, t]

    keep = A[:, s0:e0 + 1].sum(axis=1) > 0
    A_k, pred_k, err_k = A[keep], pred[keep], err[keep]

    rng = np.random.default_rng(SEED)
    bias = rng.uniform(0.75, 1.5, size=A_k.shape[0])

    def manager(_z):
        return lambda t: A_k[:, t - 28:t].mean(axis=1) * P * bias

    def textbook(z):
        def fn(t):
            h = A_k[:, t - 28:t]
            return h.mean(axis=1) * P + z * h.std(axis=1) * np.sqrt(P)
        return fn

    def ml(z):
        def fn(t):
            e = err_k[:, t - P - ERR_WINDOW + 1:t - P + 1]          # outcomes already observed
            rmse = np.sqrt(np.nanmean(e ** 2, axis=1))
            f = pred_k[:, t]
            return f + np.where(f > 0, z * rmse, 0.0)
        return fn

    print(f"\nSimulating {keep.sum():,} series over {e0 - s0 + 1} days ...\n")
    results = [summarise("Store manager", None, A_k, *simulate(A_k, s0, e0, manager(None)), s0, e0)]
    for z in Z_GRID:
        results.append(summarise("Textbook", z, A_k, *simulate(A_k, s0, e0, textbook(z)), s0, e0))
        results.append(summarise("ML", z, A_k, *simulate(A_k, s0, e0, ml(z)), s0, e0))

    # Forecast accuracy of the P-day demand forecast vs the textbook's 28-day average * P
    span = range(s0, e0 - P + 1)
    actual_p = np.stack([fb.target(t)[keep] for t in span], axis=1)
    ml_p = pred_k[:, s0:e0 - P + 1]
    ma_p = np.stack([A_k[:, t - 27:t + 1].mean(axis=1) * P for t in span], axis=1)
    wape = lambda f: 100 * np.abs(f - actual_p).sum() / actual_p.sum()  # noqa: E731
    acc = {"wape_ml_%": wape(ml_p), "wape_28d_avg_%": wape(ma_p)}

    table = pd.DataFrame(results)
    pd.set_option("display.width", 200)
    print(table.round(2).to_string(index=False))
    print(f"\n10-day demand forecast WAPE: ML {acc['wape_ml_%']:.1f}% vs 28-day avg {acc['wape_28d_avg_%']:.1f}%")

    tb = table[table["policy"] == "Textbook"]
    mlz = table[(table["policy"] == "ML") & (table["z"] == MAIN_Z)].iloc[0]
    base = table.iloc[0]
    summary = dict(acc)

    print(f"\nML (z={MAIN_Z}) vs store manager:")
    print(f"  Lost sales:     {100 * (1 - mlz['lost_units'] / base['lost_units']):+.1f}% reduction")
    print(f"  Avg inventory:  {100 * (mlz['avg_inventory_units'] / base['avg_inventory_units'] - 1):+.1f}%")

    print("\nML vs textbook at EQUAL inventory (interpolated on the textbook trade-off curve):")
    by_inv = tb.sort_values("avg_inventory_units")
    by_lost = tb.sort_values("lost_units")
    for _, m in table[table["policy"] == "ML"].iterrows():
        line = f"  ML z={m['z']:<5}: "
        if by_inv["avg_inventory_units"].min() <= m["avg_inventory_units"] <= by_inv["avg_inventory_units"].max():
            tb_lost = np.interp(m["avg_inventory_units"], by_inv["avg_inventory_units"], by_inv["lost_units"])
            pct = 100 * (1 - m["lost_units"] / tb_lost)
            summary[f"z{m['z']}_lost_sales_vs_textbook_equal_inventory_%"] = pct
            line += f"{abs(pct):.1f}% {'fewer' if pct > 0 else 'more'} lost sales at the same inventory"
        else:
            line += "inventory outside textbook range"
        if by_lost["lost_units"].min() <= m["lost_units"] <= by_lost["lost_units"].max():
            tb_inv = np.interp(m["lost_units"], by_lost["lost_units"], by_lost["avg_inventory_units"])
            pct = 100 * (1 - m["avg_inventory_units"] / tb_inv)
            summary[f"z{m['z']}_inventory_vs_textbook_equal_service_%"] = pct
            line += f" | {abs(pct):.1f}% {'less' if pct > 0 else 'more'} inventory for the same lost sales"
        print(line)

    out = ROOT / "models" / "policy_comparison.json"
    out.write_text(json.dumps({"version": 3, "sim_start": str(SIM_START.date()), "sim_end": str(SIM_END.date()),
                               "lead_days": LEAD_DAYS, "review_days": REVIEW_DAYS, "retrain_days": RETRAIN_DAYS,
                               "results": results, "summary": summary}, indent=2, default=float))
    print(f"\nSaved {out.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
