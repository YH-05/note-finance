#!/usr/bin/env bash
# 週次 KG 品質計測ラッパー。
# cron や手動で実行し、make kg-quality の出力をログファイルに保存する。
set -euo pipefail
cd "$(dirname "$0")/.."

mkdir -p data/processed/kg_quality

make kg-quality 2>&1 | tee "data/processed/kg_quality/run_$(date +%Y%m%d).log"
