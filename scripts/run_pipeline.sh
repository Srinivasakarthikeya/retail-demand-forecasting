#!/usr/bin/env bash
# Full batch run. Expects the Kaggle CSVs in data/raw (see scripts/download_data.sh).
#   Inside Docker:  docker compose --profile pipeline run --rm pipeline
#   Locally:        bash scripts/run_pipeline.sh            (add --with-eval for the 12-month simulation)
set -euo pipefail
cd "$(dirname "$0")/.."

echo "== 1/4 Load CSVs into Postgres";        python scripts/load_data.py
echo "== 2/4 Simulate baseline inventory";    python scripts/simulate_inventory.py
echo "== 3/4 Train daily forecaster";         python scripts/train_forecaster.py
if [[ "${1:-}" == "--with-eval" ]]; then
  echo "== 3b  12-month policy simulation";   python scripts/compare_policies.py
fi
echo "== 4/4 Replenishment recommendations";  python scripts/replenish.py
echo "Pipeline finished."
