#!/usr/bin/env bash
# Requires ~/.kaggle/kaggle.json and accepting the competition rules on kaggle.com first.
set -euo pipefail
cd "$(dirname "$0")/../data/raw"
kaggle competitions download -c store-sales-time-series-forecasting
unzip -o store-sales-time-series-forecasting.zip
rm store-sales-time-series-forecasting.zip
ls -lh
