"""Smart Retail Demand Forecasting & Inventory Optimization - REST API.

Run:  uvicorn api.main:app --reload
Docs: http://localhost:8000/docs
"""
import json
import os
from contextlib import asynccontextmanager
from datetime import date
from pathlib import Path
from statistics import NormalDist
from typing import Literal

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from api.db import connect, fetch_all, fetch_one
from api.prices import DEFAULT, FAMILY_PRICES

ROOT = Path(__file__).resolve().parent.parent
LEAD_DAYS, REVIEW_DAYS = 3, 7           # must match scripts/replenish.py
BASE_Z = 1.645
Status = Literal["LOW_STOCK", "REORDER", "OVERSTOCK", "OK"]

@asynccontextmanager
async def lifespan(_app):
    """Create/refresh the family_prices table (assumed INR prices) on startup."""
    with connect() as conn, conn.cursor() as cur:
        cur.execute("""CREATE TABLE IF NOT EXISTS family_prices (
                         family TEXT PRIMARY KEY, department TEXT NOT NULL, price_inr NUMERIC(10,2) NOT NULL)""")
        cur.execute("SELECT DISTINCT family FROM sales")
        families = [r["family"] for r in cur.fetchall()]
        for f in families:
            dept, price = FAMILY_PRICES.get(f, DEFAULT)
            cur.execute("""INSERT INTO family_prices VALUES (%s, %s, %s)
                           ON CONFLICT (family) DO UPDATE SET department = EXCLUDED.department,
                                                              price_inr = EXCLUDED.price_inr""", (f, dept, price))
        conn.commit()
    yield


app = FastAPI(
    lifespan=lifespan,
    title="Smart Retail Demand Forecasting API",
    version="1.0.0",
    description="Demand forecasts, reorder recommendations, stock alerts and what-if analysis "
                "for 54 stores x 33 product families (Corporacion Favorita data).",
)
# Comma-separated list, e.g. "http://localhost:5173,https://shelfiq.example.com"
CORS_ORIGINS = os.getenv("CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173,http://localhost:8080")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in CORS_ORIGINS.split(",") if o.strip()],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ------------------------------------------------------------------ helpers
def _filters(store_nbr: int | None, family: str | None, alias: str = "") -> tuple[str, dict]:
    p = f"{alias}." if alias else ""
    clauses, params = [], {}
    if store_nbr is not None:
        clauses.append(f"{p}store_nbr = %(store_nbr)s")
        params["store_nbr"] = store_nbr
    if family is not None:
        clauses.append(f"{p}family = %(family)s")
        params["family"] = family
    return (" AND " + " AND ".join(clauses)) if clauses else "", params


def _latest_run() -> date:
    row = fetch_one("SELECT MAX(run_date) AS d FROM reorder_recommendations")
    if not row or row["d"] is None:
        raise HTTPException(503, "No recommendations yet - run scripts/replenish.py")
    return row["d"]


def _read_json(name: str) -> dict | None:
    f = ROOT / "models" / name
    return json.loads(f.read_text()) if f.exists() else None


# ------------------------------------------------------------------ models
class Store(BaseModel):
    store_nbr: int
    city: str
    state: str
    type: str
    cluster: int


class Recommendation(BaseModel):
    store_nbr: int
    family: str
    status: Status
    on_hand: float | None
    on_order: float | None
    forecast_10d: float | None
    days_cover: float | None
    safety_stock: float
    reorder_point: float
    order_qty: float


class WhatIfRequest(BaseModel):
    store_nbr: int
    family: str
    demand_change_pct: float = Field(0, ge=-90, le=500, description="Seasonality / demand shift, e.g. 20 = +20%")
    promotion: bool = Field(False, description="Apply this family's historical promotion lift")
    service_level: float = Field(0.95, gt=0.5, lt=0.999, description="Target probability of no stockout")
    lead_days: int = Field(LEAD_DAYS, ge=1, le=30)


class Scenario(BaseModel):
    forecast_period: float
    safety_stock: float
    order_qty: float
    days_cover: float | None
    status: Status


class WhatIfResponse(BaseModel):
    store_nbr: int
    family: str
    on_hand: float
    on_order: float
    period_days_baseline: int
    period_days_scenario: int
    promo_lift_estimate: float
    demand_multiplier: float
    baseline: Scenario
    scenario: Scenario


# ------------------------------------------------------------------ endpoints
@app.get("/health", tags=["meta"])
def health():
    row = fetch_one("SELECT MAX(date) AS last_sales_date FROM sales")
    return {"status": "ok", "last_sales_date": row["last_sales_date"] if row else None}


@app.get("/stores", response_model=list[Store], tags=["reference"])
def stores():
    return fetch_all("SELECT store_nbr, city, state, type, cluster FROM stores ORDER BY store_nbr")


@app.get("/families", response_model=list[str], tags=["reference"])
def families():
    return [r["family"] for r in fetch_all("SELECT DISTINCT family FROM sales ORDER BY family")]


@app.get("/kpis", tags=["dashboard"])
def kpis():
    trend = fetch_one("""
        WITH m AS (SELECT MAX(date) AS d FROM sales)
        SELECT
          SUM(s.sales) FILTER (WHERE date >  m.d - 28)                                  AS last_28d,
          SUM(s.sales) FILTER (WHERE date <= m.d - 28 AND date > m.d - 56)              AS prev_28d,
          SUM(s.sales * p.price_inr) FILTER (WHERE date >  m.d - 28)                    AS inr_28d,
          SUM(s.sales * p.price_inr) FILTER (WHERE date <= m.d - 28 AND date > m.d - 56) AS inr_prev,
          MAX(m.d) AS as_of
        FROM sales s JOIN family_prices p USING (family), m WHERE date > m.d - 56
    """)
    lines = fetch_one("""
        SELECT COUNT(*) AS total, COUNT(*) FILTER (WHERE on_hand > 0) AS in_stock
        FROM reorder_recommendations WHERE run_date = (SELECT MAX(run_date) FROM reorder_recommendations)
    """)
    run = _latest_run()
    status = {r["status"]: r["n"] for r in fetch_all(
        "SELECT status, COUNT(*) AS n FROM reorder_recommendations WHERE run_date = %s GROUP BY status", (run,))}
    units = fetch_one("SELECT COALESCE(SUM(order_qty), 0) AS u FROM reorder_recommendations WHERE run_date = %s", (run,))

    last, prev = float(trend["last_28d"] or 0), float(trend["prev_28d"] or 0)
    inr, inr_prev = float(trend["inr_28d"] or 0), float(trend["inr_prev"] or 0)
    forecaster = _read_json("lgbm_v1_metrics.json")
    policy = _read_json("policy_comparison.json")
    return {
        "as_of": trend["as_of"],
        "sales_last_28d": last,
        "sales_change_pct": round(100 * (last / prev - 1), 2) if prev else None,
        "sales_inr_28d": inr,
        "sales_inr_change_pct": round(100 * (inr / inr_prev - 1), 2) if inr_prev else None,
        "lines_total": lines["total"],
        "lines_in_stock": lines["in_stock"],
        "recommendation_run": run,
        "alerts": {s: status.get(s, 0) for s in ["LOW_STOCK", "REORDER", "OVERSTOCK", "OK"]},
        "units_to_order": float(units["u"]),
        "forecast_backtest": forecaster["backtest"] if forecaster else None,
        "policy_simulation": policy["summary"] if policy else None,
    }


@app.get("/sales", tags=["dashboard"])
def sales(store_nbr: int | None = None, family: str | None = None,
          days: int = Query(90, ge=7, le=1700)):
    where, params = _filters(store_nbr, family)
    params["days"] = days
    return fetch_all(f"""
        SELECT date, SUM(sales)::float8 AS sales, SUM(onpromotion)::int AS items_on_promo
        FROM sales
        WHERE date > (SELECT MAX(date) FROM sales) - %(days)s {where}
        GROUP BY date ORDER BY date
    """, params)


@app.get("/forecasts", tags=["dashboard"])
def forecasts(store_nbr: int | None = None, family: str | None = None,
              history_days: int = Query(60, ge=7, le=365),
              metric: Literal["units", "inr"] = "units"):
    """Actuals for the last `history_days`, the 16-day backtest, and the 16-day forecast.
    metric=inr multiplies units by the assumed price per family."""
    where, params = _filters(store_nbr, family, alias="t")
    params["h"] = history_days
    mult = "* p.price_inr" if metric == "inr" else ""
    actual = fetch_all(f"""
        SELECT t.date, SUM(t.sales {mult})::float8 AS value
        FROM sales t JOIN family_prices p USING (family)
        WHERE t.date > (SELECT MAX(date) FROM sales) - %(h)s {where}
        GROUP BY t.date ORDER BY t.date
    """, params)
    fc = fetch_all(f"""
        SELECT t.date, t.model_version, SUM(t.predicted {mult})::float8 AS value
        FROM forecasts t JOIN family_prices p USING (family)
        WHERE t.model_version IN ('lgbm_v1', 'lgbm_v1_backtest') {where}
        GROUP BY t.date, t.model_version ORDER BY t.date
    """, params)
    return {
        "actual": actual,
        "backtest": [r | {"model_version": None} for r in fc if r["model_version"] == "lgbm_v1_backtest"],
        "forecast": [r | {"model_version": None} for r in fc if r["model_version"] == "lgbm_v1"],
    }


@app.get("/recommendations", response_model=list[Recommendation], tags=["inventory"])
def recommendations(status: Status | None = None, store_nbr: int | None = None, family: str | None = None,
                    sort: Literal["order_qty", "days_cover", "store"] = "order_qty",
                    limit: int = Query(200, ge=1, le=2000)):
    where, params = _filters(store_nbr, family)
    if status:
        where += " AND status = %(status)s"
        params["status"] = status
    order = {"order_qty": "order_qty DESC", "days_cover": "days_cover DESC NULLS LAST",
             "store": "store_nbr, family"}[sort]
    params.update(run=_latest_run(), limit=limit)
    return fetch_all(f"""
        SELECT store_nbr, family, status,
               on_hand::float8, on_order::float8, forecast_period::float8 AS forecast_10d,
               days_cover::float8, safety_stock::float8, reorder_point::float8, order_qty::float8
        FROM reorder_recommendations
        WHERE run_date = %(run)s {where}
        ORDER BY {order} LIMIT %(limit)s
    """, params)


@app.get("/alerts", tags=["inventory"])
def alerts(limit: int = Query(20, ge=1, le=500)):
    run = _latest_run()
    low = fetch_all("""
        SELECT store_nbr, family, on_hand::float8, forecast_period::float8 AS forecast_10d,
               order_qty::float8, days_cover::float8,
               (forecast_period * %(share)s - on_hand)::float8 AS shortfall_before_delivery
        FROM reorder_recommendations
        WHERE run_date = %(run)s AND status = 'LOW_STOCK'
        ORDER BY shortfall_before_delivery DESC LIMIT %(limit)s
    """, {"run": run, "limit": limit, "share": LEAD_DAYS / (LEAD_DAYS + REVIEW_DAYS)})
    over = fetch_all("""
        SELECT store_nbr, family, on_hand::float8, forecast_period::float8 AS forecast_10d,
               days_cover::float8
        FROM reorder_recommendations
        WHERE run_date = %(run)s AND status = 'OVERSTOCK'
        ORDER BY days_cover DESC NULLS LAST LIMIT %(limit)s
    """, {"run": run, "limit": limit})
    return {"run_date": run, "low_stock": low, "overstock": over}


@app.get("/analytics/stores", tags=["analytics"])
def store_analytics(days: int = Query(28, ge=7, le=365)):
    return fetch_all("""
        WITH s AS (
            SELECT store_nbr, SUM(sales) AS sales FROM sales
            WHERE date > (SELECT MAX(date) FROM sales) - %(days)s GROUP BY store_nbr
        ),
        r AS (
            SELECT store_nbr,
                   COUNT(*) FILTER (WHERE status = 'LOW_STOCK') AS low_stock,
                   COUNT(*) FILTER (WHERE status = 'OVERSTOCK') AS overstock,
                   SUM(order_qty) AS units_to_order
            FROM reorder_recommendations
            WHERE run_date = (SELECT MAX(run_date) FROM reorder_recommendations)
            GROUP BY store_nbr
        )
        SELECT st.store_nbr, st.city, st.type, COALESCE(s.sales, 0)::float8 AS sales,
               COALESCE(r.low_stock, 0)::int AS low_stock, COALESCE(r.overstock, 0)::int AS overstock,
               COALESCE(r.units_to_order, 0)::float8 AS units_to_order
        FROM stores st LEFT JOIN s USING (store_nbr) LEFT JOIN r USING (store_nbr)
        ORDER BY sales DESC
    """, {"days": days})


@app.get("/analytics/families", tags=["analytics"])
def family_analytics(days: int = Query(28, ge=7, le=365)):
    return fetch_all("""
        WITH m AS (SELECT MAX(date) AS d FROM sales),
        s AS (
            SELECT family,
                   SUM(sales) FILTER (WHERE date > m.d - %(days)s) AS sales,
                   SUM(sales) FILTER (WHERE date <= m.d - %(days)s) AS prev_sales,
                   AVG(sales) FILTER (WHERE date > m.d - %(days)s AND onpromotion > 0) AS promo_avg,
                   AVG(sales) FILTER (WHERE date > m.d - %(days)s AND onpromotion = 0) AS base_avg
            FROM sales, m WHERE date > m.d - 2 * %(days)s GROUP BY family
        ),
        r AS (
            SELECT family,
                   COUNT(*) FILTER (WHERE status = 'LOW_STOCK') AS low_stock,
                   COUNT(*) FILTER (WHERE status = 'OVERSTOCK') AS overstock
            FROM reorder_recommendations
            WHERE run_date = (SELECT MAX(run_date) FROM reorder_recommendations)
            GROUP BY family
        )
        SELECT s.family, p.department, s.sales::float8,
               (s.sales * p.price_inr)::float8 AS sales_inr,
               ROUND((100 * s.sales / SUM(s.sales) OVER ())::numeric, 2)::float8 AS share_pct,
               ROUND((100 * (s.sales / NULLIF(s.prev_sales, 0) - 1))::numeric, 1)::float8 AS growth_pct,
               ROUND((s.promo_avg / NULLIF(s.base_avg, 0))::numeric, 2)::float8 AS promo_lift,
               COALESCE(r.low_stock, 0)::int AS low_stock, COALESCE(r.overstock, 0)::int AS overstock
        FROM s JOIN family_prices p USING (family) LEFT JOIN r USING (family)
        ORDER BY sales_inr DESC
    """, {"days": days})


@app.get("/analytics/departments", tags=["analytics"])
def department_analytics(days: int = Query(28, ge=7, le=365)):
    return fetch_all("""
        SELECT p.department, SUM(s.sales * p.price_inr)::float8 AS sales_inr,
               ROUND((100 * SUM(s.sales * p.price_inr) / SUM(SUM(s.sales * p.price_inr)) OVER ())::numeric, 1)::float8 AS share_pct
        FROM sales s JOIN family_prices p USING (family)
        WHERE s.date > (SELECT MAX(date) FROM sales) - %(days)s
        GROUP BY p.department ORDER BY sales_inr DESC
    """, {"days": days})


@app.get("/analytics/store-types", tags=["analytics"])
def store_type_analytics(days: int = Query(28, ge=7, le=365)):
    return fetch_all("""
        SELECT st.type, COUNT(DISTINCT st.store_nbr)::int AS stores,
               SUM(s.sales * p.price_inr)::float8 AS sales_inr,
               ROUND((100 * SUM(s.sales * p.price_inr) / SUM(SUM(s.sales * p.price_inr)) OVER ())::numeric, 1)::float8 AS share_pct
        FROM sales s JOIN stores st USING (store_nbr) JOIN family_prices p USING (family)
        WHERE s.date > (SELECT MAX(date) FROM sales) - %(days)s
        GROUP BY st.type ORDER BY sales_inr DESC
    """, {"days": days})


@app.get("/analytics/spikes", tags=["analytics"])
def demand_spikes(threshold: float = Query(1.5, ge=1.1, le=10), limit: int = Query(5, ge=1, le=100)):
    """Store x family lines whose last-7-day average is >= threshold x their previous 28-day average."""
    rows = fetch_all("""
        WITH m AS (SELECT MAX(date) AS d FROM sales),
        a AS (
            SELECT store_nbr, family,
                   AVG(sales) FILTER (WHERE date > m.d - 7) AS recent,
                   AVG(sales) FILTER (WHERE date <= m.d - 7) AS normal
            FROM sales, m WHERE date > m.d - 35 GROUP BY store_nbr, family
        )
        SELECT store_nbr, family, recent::float8 AS recent_daily, normal::float8 AS normal_daily,
               ROUND((100 * (recent / normal - 1))::numeric, 0)::float8 AS change_pct
        FROM a WHERE normal >= 5 AND recent >= %(t)s * normal
        ORDER BY recent / normal DESC
    """, {"t": threshold})
    return {"count": len(rows), "threshold": threshold, "items": rows[:limit]}


@app.post("/whatif", response_model=WhatIfResponse, tags=["inventory"])
def whatif(req: WhatIfRequest):
    """Re-plan one item under a different demand level, promotion, service level or lead time."""
    rec = fetch_one("""
        SELECT on_hand::float8, on_order::float8, forecast_period::float8 AS f, safety_stock::float8 AS ss
        FROM reorder_recommendations
        WHERE run_date = (SELECT MAX(run_date) FROM reorder_recommendations)
          AND store_nbr = %(s)s AND family = %(f)s
    """, {"s": req.store_nbr, "f": req.family})
    if rec is None:
        raise HTTPException(404, f"No recommendation for store {req.store_nbr} / {req.family}")

    lift_row = fetch_one("""
        SELECT AVG(sales) FILTER (WHERE onpromotion > 0) / NULLIF(AVG(sales) FILTER (WHERE onpromotion = 0), 0) AS lift
        FROM sales WHERE family = %(f)s AND date > (SELECT MAX(date) FROM sales) - 365
    """, {"f": req.family})
    lift = float(lift_row["lift"]) if lift_row and lift_row["lift"] else 1.0
    lift = min(max(lift, 1.0), 3.0)   # capped: raw lift is confounded with seasonality (see EDA)

    p0 = LEAD_DAYS + REVIEW_DAYS
    p1 = req.lead_days + REVIEW_DAYS
    mult = (1 + req.demand_change_pct / 100) * (lift if req.promotion else 1.0)
    rmse = rec["ss"] / BASE_Z if rec["f"] > 0 else 0.0
    z = NormalDist().inv_cdf(req.service_level)

    def plan(f: float, ss: float, lead: int, period: int) -> Scenario:
        order = max(0.0, f + ss - rec["on_hand"] - rec["on_order"])
        daily = f / period
        cover = rec["on_hand"] / daily if daily > 0 else None
        if daily > 0 and rec["on_hand"] < daily * lead:
            status = "LOW_STOCK"
        elif cover is not None and cover > 21 and rec["on_hand"] > 0:
            status, order = "OVERSTOCK", 0.0
        elif order > 0:
            status = "REORDER"
        else:
            status = "OK"
        return Scenario(forecast_period=round(f, 2), safety_stock=round(ss, 2), order_qty=round(order, 2),
                        days_cover=round(cover, 1) if cover is not None else None, status=status)

    base = plan(rec["f"], rec["ss"], LEAD_DAYS, p0)
    f1 = rec["f"] * mult * p1 / p0
    ss1 = z * rmse * mult * (p1 / p0) ** 0.5 if f1 > 0 else 0.0
    return WhatIfResponse(
        store_nbr=req.store_nbr, family=req.family, on_hand=rec["on_hand"], on_order=rec["on_order"],
        period_days_baseline=p0, period_days_scenario=p1, promo_lift_estimate=round(lift, 2),
        demand_multiplier=round(mult, 3), baseline=base, scenario=plan(f1, ss1, req.lead_days, p1),
    )
