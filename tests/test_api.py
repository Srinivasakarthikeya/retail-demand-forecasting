"""Smoke tests against the running database (docker compose up -d first)."""
from fastapi.testclient import TestClient

from api.main import app

client = TestClient(app)


def test_health():
    r = client.get("/health")
    assert r.status_code == 200 and r.json()["status"] == "ok"


def test_reference_lists():
    assert len(client.get("/stores").json()) > 0
    assert len(client.get("/families").json()) > 0


def test_kpis_shape():
    k = client.get("/kpis").json()
    assert {"sales_last_28d", "alerts", "units_to_order"} <= k.keys()


def test_sales_and_filters():
    store = client.get("/stores").json()[0]["store_nbr"]
    rows = client.get("/sales", params={"store_nbr": store, "days": 30}).json()
    assert 25 <= len(rows) <= 30


def test_forecasts_have_16_days():
    fc = client.get("/forecasts").json()
    assert len(fc["forecast"]) == 16 and len(fc["actual"]) > 0


def test_recommendations_filter_by_status():
    for row in client.get("/recommendations", params={"status": "REORDER", "limit": 5}).json():
        assert row["status"] == "REORDER"


def test_whatif_promotion_raises_order():
    rec = client.get("/recommendations", params={"limit": 1}).json()[0]
    body = {"store_nbr": rec["store_nbr"], "family": rec["family"], "demand_change_pct": 30}
    r = client.post("/whatif", json=body).json()
    assert r["scenario"]["forecast_period"] > r["baseline"]["forecast_period"]


def test_whatif_unknown_item_404():
    assert client.post("/whatif", json={"store_nbr": 9999, "family": "NOPE"}).status_code == 404
