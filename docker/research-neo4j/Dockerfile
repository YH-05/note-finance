# Research Neo4j - 銘柄・マクロ調査専用
# カスタムビルドが必要な場合に使用（通常は docker-compose.yml の image で十分）
#
# Usage:
#   docker build -t research-neo4j:latest -f docker/research-neo4j/Dockerfile .
#   docker run -d --name research-neo4j \
#     -p 7475:7474 -p 7688:7687 \
#     -v /Volumes/NeoData/neo4j-research/data:/data \
#     research-neo4j:latest

FROM neo4j:5-community

# メタデータ
LABEL maintainer="YH-05"
LABEL description="Research Neo4j for equity and macro analysis"
LABEL version="1.0"

# APOC プラグイン有効化
ENV NEO4J_PLUGINS='["apoc"]'
ENV NEO4J_apoc_export_file_enabled=true
ENV NEO4J_apoc_import_file_enabled=true
ENV NEO4J_apoc_import_file_use__neo4j__config=true

# メモリ設定
ENV NEO4J_server_memory_heap_initial__size=256m
ENV NEO4J_server_memory_heap_max__size=512m
ENV NEO4J_server_memory_pagecache_size=256m

# 初期化スクリプトをコピー（コンテナ起動時に自動実行）
COPY docker/research-neo4j/init/ /docker-entrypoint-initdb.d/

EXPOSE 7474 7687
