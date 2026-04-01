#!/bin/bash
# scrape-wrapper.sh - stdoutとstderrをローカルとNASの両方に出力するラッパー
#
# Usage: scrape-wrapper.sh <source_name> [extra_args...]
#   例: scrape-wrapper.sh ars_technica --include-content
#
# ログ出力先:
#   ローカル: logs/scrape-{source}.log, logs/scrape-{source}-error.log
#   NAS:     /Volumes/personal_folder/logs/scrape-{source}.log, scrape-{source}-error.log

set -euo pipefail

SOURCE="$1"
shift

# ハイフン区切りに統一 (ars_technica -> ars-technica)
LOG_NAME="scrape-$(echo "$SOURCE" | tr '_' '-')"

LOCAL_LOG_DIR="/Users/yuki/Desktop/note-finance/logs"
NAS_LOG_DIR="/Volumes/personal_folder/logs"

LOCAL_OUT="${LOCAL_LOG_DIR}/${LOG_NAME}.log"
LOCAL_ERR="${LOCAL_LOG_DIR}/${LOG_NAME}-error.log"

# NAS がマウントされていればNASログも有効化
if [ -d "/Volumes/personal_folder" ]; then
    mkdir -p "${NAS_LOG_DIR}"
    NAS_OUT="${NAS_LOG_DIR}/${LOG_NAME}.log"
    NAS_ERR="${NAS_LOG_DIR}/${LOG_NAME}-error.log"
else
    NAS_OUT=""
    NAS_ERR=""
fi

cd /Users/yuki/Desktop/note-finance

if [ -n "${NAS_OUT}" ]; then
    /Users/yuki/.local/bin/uv run python scripts/scrape_finance_news.py \
        --sources "$SOURCE" "$@" \
        > >(tee -a "$LOCAL_OUT" >> "$NAS_OUT") \
        2> >(tee -a "$LOCAL_ERR" >> "$NAS_ERR" >&2)
else
    /Users/yuki/.local/bin/uv run python scripts/scrape_finance_news.py \
        --sources "$SOURCE" "$@" \
        >> "$LOCAL_OUT" 2>> "$LOCAL_ERR"
fi
