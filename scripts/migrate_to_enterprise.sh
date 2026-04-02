#!/bin/bash
# Neo4j Community → Enterprise 移行スクリプト
# Phase 0: バックアップ + Phase 2: Enterprise起動・リストア
#
# 前提: Docker Desktop が再起動済みで、全コンテナが停止していること
# 使い方: bash scripts/migrate_to_enterprise.sh

set -euo pipefail

DUMPS_DIR="/Volumes/NeoData/enterprise-migration/dumps"
ENTERPRISE_DIR="/Volumes/NeoData/enterprise"
NEO4J_IMAGE="neo4j:5.26-enterprise"
NEO4J_PASSWORD="${NEO4J_PASSWORD:-gomasuke}"

echo "=== Neo4j Enterprise Migration ==="
echo ""

# -------------------------------------------------------
# Phase 0: バックアップ（dump）
# -------------------------------------------------------
echo "--- Phase 0: Backing up all databases ---"
mkdir -p "$DUMPS_DIR"

# 稼働中のneo4jコンテナがあれば停止
echo "Stopping any running neo4j containers..."
docker stop note-neo4j research-neo4j creator-neo4j quants-neo4j 2>/dev/null || true
docker rm note-neo4j research-neo4j creator-neo4j quants-neo4j 2>/dev/null || true
sleep 3

# note-neo4j (Docker volume)
echo ""
echo "[1/4] Dumping note-neo4j..."
docker run --rm \
  -v note-finance_note_neo4j-data:/data \
  -v "$DUMPS_DIR":/dumps \
  "$NEO4J_IMAGE" \
  neo4j-admin database dump neo4j --to-path=/dumps/note --overwrite-destination=true \
  && echo "  -> note dump OK" || echo "  -> note dump FAILED"

# research-neo4j (NeoData bind mount)
echo "[2/4] Dumping research-neo4j..."
docker run --rm \
  -v /Volumes/NeoData/neo4j-research/data:/data \
  -v "$DUMPS_DIR":/dumps \
  "$NEO4J_IMAGE" \
  neo4j-admin database dump neo4j --to-path=/dumps/research --overwrite-destination=true \
  && echo "  -> research dump OK" || echo "  -> research dump FAILED"

# creator-neo4j (NeoData bind mount)
echo "[3/4] Dumping creator-neo4j..."
docker run --rm \
  -v /Volumes/NeoData/neo4j-creator/data:/data \
  -v "$DUMPS_DIR":/dumps \
  "$NEO4J_IMAGE" \
  neo4j-admin database dump neo4j --to-path=/dumps/creator --overwrite-destination=true \
  && echo "  -> creator dump OK" || echo "  -> creator dump FAILED"

# quants-neo4j (NeoData bind mount)
echo "[4/4] Dumping quants-neo4j..."
docker run --rm \
  -v /Volumes/NeoData/docker/quants-neo4j/data:/data \
  -v "$DUMPS_DIR":/dumps \
  "$NEO4J_IMAGE" \
  neo4j-admin database dump neo4j --to-path=/dumps/quants --overwrite-destination=true \
  && echo "  -> quants dump OK" || echo "  -> quants dump FAILED"

echo ""
echo "Dump files:"
ls -lh "$DUMPS_DIR"/*/neo4j.dump 2>/dev/null || ls -lhR "$DUMPS_DIR"
echo ""

# -------------------------------------------------------
# Phase 2: Enterprise 起動・DB作成・リストア
# -------------------------------------------------------
echo "--- Phase 2: Starting Enterprise & Restoring ---"

# Enterprise データディレクトリ作成
mkdir -p "$ENTERPRISE_DIR"/{data,logs,plugins,import}

# Enterprise コンテナ起動
echo "Starting neo4j-enterprise container..."
cd /Users/yukihata/Desktop/note-finance
docker compose up -d neo4j

echo "Waiting for Neo4j to become ready..."
for i in $(seq 1 30); do
  if docker exec neo4j-enterprise wget --no-verbose --tries=1 --spider http://localhost:7474 2>/dev/null; then
    echo "  -> Neo4j is ready"
    break
  fi
  echo "  waiting... ($i/30)"
  sleep 5
done

# DB作成
echo ""
echo "Creating databases..."
docker exec neo4j-enterprise cypher-shell \
  -u neo4j -p "$NEO4J_PASSWORD" \
  "CREATE DATABASE note IF NOT EXISTS;"
docker exec neo4j-enterprise cypher-shell \
  -u neo4j -p "$NEO4J_PASSWORD" \
  "CREATE DATABASE research IF NOT EXISTS;"
docker exec neo4j-enterprise cypher-shell \
  -u neo4j -p "$NEO4J_PASSWORD" \
  "CREATE DATABASE creator IF NOT EXISTS;"
docker exec neo4j-enterprise cypher-shell \
  -u neo4j -p "$NEO4J_PASSWORD" \
  "CREATE DATABASE quants IF NOT EXISTS;"

echo "Databases created. Verifying..."
docker exec neo4j-enterprise cypher-shell \
  -u neo4j -p "$NEO4J_PASSWORD" \
  "SHOW DATABASES YIELD name, currentStatus RETURN name, currentStatus;"

# DB停止 → ロード → 再起動
echo ""
echo "Stopping databases for data load..."
for db in note research creator quants; do
  docker exec neo4j-enterprise cypher-shell \
    -u neo4j -p "$NEO4J_PASSWORD" \
    "STOP DATABASE $db;" 2>/dev/null || true
done
sleep 3

echo ""
echo "Loading dump data..."

# note
echo "[1/4] Loading note..."
docker exec neo4j-enterprise neo4j-admin database load note \
  --from-path=/var/lib/neo4j/import/note \
  --overwrite-destination=true 2>/dev/null \
  && echo "  -> note load OK" \
  || {
    # ダンプファイルをimportにコピーしてリトライ
    echo "  -> Copying dump to container..."
    docker cp "$DUMPS_DIR/note" neo4j-enterprise:/var/lib/neo4j/import/note
    docker exec neo4j-enterprise neo4j-admin database load note \
      --from-path=/var/lib/neo4j/import/note \
      --overwrite-destination=true \
      && echo "  -> note load OK (retry)" || echo "  -> note load FAILED"
  }

# research
echo "[2/4] Loading research..."
docker cp "$DUMPS_DIR/research" neo4j-enterprise:/var/lib/neo4j/import/research
docker exec neo4j-enterprise neo4j-admin database load research \
  --from-path=/var/lib/neo4j/import/research \
  --overwrite-destination=true \
  && echo "  -> research load OK" || echo "  -> research load FAILED"

# creator
echo "[3/4] Loading creator..."
docker cp "$DUMPS_DIR/creator" neo4j-enterprise:/var/lib/neo4j/import/creator
docker exec neo4j-enterprise neo4j-admin database load creator \
  --from-path=/var/lib/neo4j/import/creator \
  --overwrite-destination=true \
  && echo "  -> creator load OK" || echo "  -> creator load FAILED"

# quants
echo "[4/4] Loading quants..."
docker cp "$DUMPS_DIR/quants" neo4j-enterprise:/var/lib/neo4j/import/quants
docker exec neo4j-enterprise neo4j-admin database load quants \
  --from-path=/var/lib/neo4j/import/quants \
  --overwrite-destination=true \
  && echo "  -> quants load OK" || echo "  -> quants load FAILED"

# DB再起動
echo ""
echo "Starting databases..."
for db in note research creator quants; do
  docker exec neo4j-enterprise cypher-shell \
    -u neo4j -p "$NEO4J_PASSWORD" \
    "START DATABASE $db;" 2>/dev/null || true
done
sleep 5

# 検証
echo ""
echo "=== Verification ==="
docker exec neo4j-enterprise cypher-shell \
  -u neo4j -p "$NEO4J_PASSWORD" \
  "SHOW DATABASES YIELD name, currentStatus, store RETURN name, currentStatus, store;"

echo ""
echo "Node counts per database:"
for db in note research creator quants; do
  count=$(docker exec neo4j-enterprise cypher-shell \
    -u neo4j -p "$NEO4J_PASSWORD" \
    -d "$db" \
    "MATCH (n) RETURN count(n) AS count;" 2>/dev/null | tail -1)
  echo "  $db: $count nodes"
done

echo ""
echo "=== Migration Complete ==="
echo "Enterprise running at bolt://localhost:7687"
echo "Browser UI at http://localhost:7474"
