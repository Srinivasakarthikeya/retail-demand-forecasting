"""Train a LightGBM demand forecaster (16 days ahead, every store x family).

Pipeline:
  1. Load sales, stores, holidays from Postgres + future promo plan (test.csv).
  2. Build features. All lags are >= 16 days, so one model forecasts the whole
     16-day horizon without feeding predictions back in (direct strategy).
  3. Backtest on the last 16 days vs two baselines:
       - seasonal naive (same weekday, 3 weeks earlier)
       - 28-day moving average (what the baseline store manager uses)
  4. Retrain on all data, forecast the next 16 days, save to the forecasts table.
"""
import json
import os
from pathlib import Path

import lightgbm as lgb
import numpy as np
import pandas as pd
import psycopg
from dotenv import load_dotenv

load_dotenv()
DB_URL = os.getenv("DATABASE_URL", "postgresql://retail:retail@localhost:5432/retail")
ROOT = Path(__file__).resolve().parent.parent
MODEL_DIR = ROOT / "models"
MODEL_VERSION = "lgbm_v1"

HORIZON = 16
HISTORY_START = "2014-01-01"     # enough history for the 364-day lag
TRAIN_START = "2015-01-01"
LAGS = [16, 21, 28, 35, 42, 364]
WINDOWS = [7, 14, 28, 56]
KEYS = ["store_nbr", "family"]

PARAMS = {
    "objective": "regression",      # on log1p(sales) -> optimises RMSLE
    "learning_rate": 0.05,
    "num_leaves": 127,
    "min_data_in_leaf": 100,
    "feature_fraction": 0.8,
    "bagging_fraction": 0.8,
    "bagging_freq": 1,
    "lambda_l2": 1.0,
    "verbose": -1,
    "seed": 42,
}


# ---------------------------------------------------------------- data loading
def load_data():
    with psycopg.connect(DB_URL) as conn:
        sales = pd.read_sql(
            "SELECT date, store_nbr, family, sales::float8 AS sales, onpromotion "
            "FROM sales WHERE date >= %(d)s", conn, params={"d": HISTORY_START})
        stores = pd.read_sql("SELECT * FROM stores", conn)
        holidays = pd.read_sql("SELECT * FROM holidays", conn)
    future = pd.read_csv(ROOT / "data" / "raw" / "test.csv").drop(columns="id")
    return sales, stores, holidays, future


# ---------------------------------------------------------------- features
def holiday_flags(frame, holidays):
    h = holidays[(~holidays["transferred"]) & (holidays["type"] != "Work Day")].copy()
    h["date"] = pd.to_datetime(h["date"])
    nat = set(h.loc[h["locale"] == "National", "date"])
    reg = set(zip(h.loc[h["locale"] == "Regional", "date"], h.loc[h["locale"] == "Regional", "locale_name"]))
    loc = set(zip(h.loc[h["locale"] == "Local", "date"], h.loc[h["locale"] == "Local", "locale_name"]))

    is_nat = frame["date"].isin(nat)
    is_reg = pd.Series([k in reg for k in zip(frame["date"], frame["state"])], index=frame.index)
    is_loc = pd.Series([k in loc for k in zip(frame["date"], frame["city"])], index=frame.index)
    return (is_nat | is_reg | is_loc).astype(int), is_nat.astype(int)


def build_frame(sales, stores, holidays, future):
    df = pd.concat([sales, future.assign(sales=np.nan)], ignore_index=True)
    df["date"] = pd.to_datetime(df["date"])

    # Complete grid: the data skips Dec 25 (stores closed). Fill so lags stay aligned.
    dates = pd.date_range(df["date"].min(), df["date"].max(), freq="D")
    pairs = df[KEYS].drop_duplicates()
    grid = pairs.merge(pd.DataFrame({"date": dates}), how="cross")
    df = grid.merge(df, on=["date"] + KEYS, how="left")
    last_actual = sales["date"].max()
    is_hist = df["date"] <= pd.Timestamp(last_actual)
    df.loc[is_hist, "sales"] = df.loc[is_hist, "sales"].fillna(0)
    df["onpromotion"] = df["onpromotion"].fillna(0)

    df = df.merge(stores, on="store_nbr", how="left")
    df = df.sort_values(KEYS + ["date"]).reset_index(drop=True)

    # Calendar
    df["dow"] = df["date"].dt.dayofweek
    df["day"] = df["date"].dt.day
    df["month"] = df["date"].dt.month
    df["weekofyear"] = df["date"].dt.isocalendar().week.astype(int)
    df["is_payday"] = ((df["day"] == 15) | df["date"].dt.is_month_end).astype(int)
    df["holiday"], df["national_holiday"] = holiday_flags(df, holidays)

    # Target + lag features (all shifted >= HORIZON days)
    df["y"] = np.log1p(df["sales"])
    g = df.groupby(KEYS, sort=False)
    for lag in LAGS:
        df[f"lag_{lag}"] = g["y"].shift(lag)
    df["dow_mean"] = df[["lag_21", "lag_28", "lag_35", "lag_42"]].mean(axis=1)

    shifted = g["y"].shift(HORIZON)
    shifted_raw = g["sales"].shift(HORIZON)
    keys = [df[k] for k in KEYS]
    for w in WINDOWS:
        df[f"rmean_{w}"] = shifted.groupby(keys).transform(lambda s: s.rolling(w, min_periods=1).mean())
    df["rstd_28"] = shifted.groupby(keys).transform(lambda s: s.rolling(28, min_periods=2).std())
    df["promo_rmean_28"] = g["onpromotion"].transform(lambda s: s.rolling(28, min_periods=1).mean())

    # Baselines on the raw scale (same information cutoff as the model)
    df["base_ma28"] = shifted_raw.groupby(keys).transform(lambda s: s.rolling(28, min_periods=1).mean())
    df["base_naive"] = g["sales"].shift(21)
    df["recent_raw_56"] = shifted_raw.groupby(keys).transform(lambda s: s.rolling(56, min_periods=1).sum())

    for c in ["store_nbr", "family", "type", "cluster", "city"]:
        df[c] = df[c].astype("category")
    return df, pd.Timestamp(last_actual)


FEATURES = (
    ["store_nbr", "family", "type", "cluster", "city", "onpromotion", "promo_rmean_28",
     "dow", "day", "month", "weekofyear", "is_payday", "holiday", "national_holiday",
     "dow_mean", "rstd_28"]
    + [f"lag_{l}" for l in LAGS]
    + [f"rmean_{w}" for w in WINDOWS]
)


# ---------------------------------------------------------------- evaluation
def predict(model, frame):
    pred = np.expm1(model.predict(frame[FEATURES], num_iteration=model.best_iteration or None))
    pred = np.clip(pred, 0, None)
    pred[frame["recent_raw_56"].to_numpy() == 0] = 0   # nothing sold in 8 weeks -> forecast 0
    return pred


def metrics(y, p):
    y, p = np.asarray(y), np.clip(np.asarray(p, dtype=float), 0, None)
    return {
        "RMSLE": float(np.sqrt(np.mean((np.log1p(p) - np.log1p(y)) ** 2))),
        "MAE": float(np.mean(np.abs(p - y))),
        "WAPE_%": float(100 * np.abs(p - y).sum() / y.sum()),
    }


# ---------------------------------------------------------------- main
def main():
    print("Loading data ...")
    sales, stores, holidays, future = load_data()
    print("Building features ...")
    df, last_actual = build_frame(sales, stores, holidays, future)

    val_start = last_actual - pd.Timedelta(days=HORIZON - 1)
    hist = df[(df["date"] >= TRAIN_START) & (df["date"] <= last_actual)]
    train = hist[hist["date"] < val_start]
    val = hist[hist["date"] >= val_start]
    print(f"Train: {train['date'].min().date()} -> {train['date'].max().date()} ({len(train):,} rows)")
    print(f"Valid: {val['date'].min().date()} -> {val['date'].max().date()} ({len(val):,} rows)")

    print("Training (backtest) ...")
    dtrain = lgb.Dataset(train[FEATURES], train["y"])
    dval = lgb.Dataset(val[FEATURES], val["y"], reference=dtrain)
    model = lgb.train(PARAMS, dtrain, num_boost_round=2000, valid_sets=[dval],
                      callbacks=[lgb.early_stopping(100), lgb.log_evaluation(200)])

    val = val.copy()
    val["pred"] = predict(model, val)
    results = {
        "Seasonal naive (3 wks ago)": metrics(val["sales"], val["base_naive"].fillna(0)),
        "28-day moving avg (baseline)": metrics(val["sales"], val["base_ma28"].fillna(0)),
        "LightGBM": metrics(val["sales"], val["pred"]),
    }
    print("\nBacktest on last 16 days:")
    print(pd.DataFrame(results).T.round(3).to_string())

    imp = pd.Series(model.feature_importance("gain"), index=FEATURES).sort_values(ascending=False)
    print("\nTop 10 features (by gain):")
    print((100 * imp / imp.sum()).round(1).head(10).to_string())

    print("\nRetraining on all data and forecasting the next 16 days ...")
    best_iter = model.best_iteration
    full = lgb.train(PARAMS, lgb.Dataset(hist[FEATURES], hist["y"]), num_boost_round=best_iter)
    fut = df[df["date"] > last_actual].copy()
    fut["pred"] = predict(full, fut)

    MODEL_DIR.mkdir(exist_ok=True)
    full.save_model(MODEL_DIR / f"{MODEL_VERSION}.txt")
    with open(MODEL_DIR / f"{MODEL_VERSION}_metrics.json", "w") as f:
        json.dump({"best_iteration": best_iter, "backtest": results,
                   "feature_importance_pct": (100 * imp / imp.sum()).round(2).to_dict()}, f, indent=2)

    rows = [(d.date(), int(s), str(fa), round(float(p), 3), MODEL_VERSION)
            for d, s, fa, p in fut[["date", "store_nbr", "family", "pred"]].itertuples(index=False)]
    rows += [(d.date(), int(s), str(fa), round(float(p), 3), f"{MODEL_VERSION}_backtest")
             for d, s, fa, p in val[["date", "store_nbr", "family", "pred"]].itertuples(index=False)]
    with psycopg.connect(DB_URL) as conn, conn.cursor() as cur:
        cur.execute("DELETE FROM forecasts WHERE model_version IN (%s, %s)",
                    (MODEL_VERSION, f"{MODEL_VERSION}_backtest"))
        with cur.copy("COPY forecasts (date, store_nbr, family, predicted, model_version) FROM STDIN") as cp:
            for r in rows:
                cp.write_row(r)
        conn.commit()

    print(f"Saved model to models/{MODEL_VERSION}.txt")
    print(f"Saved {len(fut):,} future + {len(val):,} backtest forecasts to the forecasts table "
          f"({fut['date'].min().date()} -> {fut['date'].max().date()})")


if __name__ == "__main__":
    main()
