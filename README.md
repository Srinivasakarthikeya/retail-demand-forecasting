# Smart Retail Demand Forecasting & Inventory Optimization

Forecasts daily product demand per store and turns forecasts into inventory
actions: reorder points, safety stock, low-stock/overstock alerts, and
promotion what-if analysis.

**Data:** [Corporación Favorita Store Sales](https://www.kaggle.com/competitions/store-sales-time-series-forecasting)
(54 stores x 33 product families, 2013-2017). Inventory levels are simulated
from real sales, since the public data has none.

## Quickstart
```bash
cp .env.example .env
docker compose up -d                 # Postgres + schema
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
./scripts/download_data.sh
python scripts/load_data.py
```

## Status
- [x] Phase 1: data pipeline into Postgres
- [ ] Phase 2: EDA + inventory simulation
- [ ] Phase 3: LightGBM forecaster
- [ ] Phase 4: inventory optimization + alerts
- [ ] Phase 5: FastAPI
- [ ] Phase 6: React dashboard
- [ ] Phase 7: Dockerized deployment
