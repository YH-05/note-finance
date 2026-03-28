# 議論メモ: Docker 再起動ポリシー設定（n8n / note-finance Neo4j）

**日付**: 2026-03-28
**参加**: ユーザー + AI

## 背景・コンテキスト

n8n Docker コンテナの自動起動設定を確認したところ、restart ポリシーが `always` になっていることが判明。
加えて n8n の compose ファイル（`/Users/yuki/Desktop/n8n/docker-compose.yml`）が消失していた。

note-finance の3つの Neo4j コンテナは `unless-stopped` になっていたが、明示的に `always` へ変更することになった。

## 議論のサマリー

- **n8n**: オンデマンドで使うツールのため自動起動不要 → `restart: "no"` に変更
- **Neo4j 3コンテナ**: プロジェクト中核インフラとして常時起動が必要 → `restart: always` に変更
- compose ファイルが消失していた n8n は `/Users/yuki/Desktop/n8n/docker-compose.yml` を再作成

## 決定事項

1. **n8n の restart ポリシー**: `no`（Docker Desktop 起動時に自動起動しない）
2. **note-finance Neo4j 3コンテナの restart ポリシー**: `always`（常に自動起動）
3. **n8n compose ファイル再作成**: `/Users/yuki/Desktop/n8n/docker-compose.yml`
   - `image: n8n-n8n`（既存のローカルビルドイメージを使用）
   - `volumes.n8n_data.external: true`（既存ボリューム `n8n_n8n_data` を参照してデータ保持）

## 対応内容

### n8n compose ファイル（新規作成）

```yaml
# /Users/yuki/Desktop/n8n/docker-compose.yml
services:
  n8n:
    image: n8n-n8n
    container_name: n8n
    restart: "no"
    ports:
      - "5678:5678"
    volumes:
      - n8n_data:/home/node/.n8n
    environment:
      - N8N_HOST=localhost
      - N8N_PORT=5678
      - N8N_PROTOCOL=http
      - N8N_BASIC_AUTH_ACTIVE=false
      - GENERIC_TIME_ZONE=Asia/Tokyo

volumes:
  n8n_data:
    external: true
    name: n8n_n8n_data
```

### note-finance docker-compose.yml 変更

```
neo4j-note / neo4j-research / neo4j-creator:
  restart: unless-stopped → always
```

`docker compose up -d` で全コンテナに即時反映済み。

## 最終ステータス確認

```
/note-neo4j:    restart=always  status=running
/research-neo4j: restart=always status=running
/creator-neo4j: restart=always  status=running
/n8n:           restart=no      status=running
```

## アクションアイテム

なし（全て対応済み）

## 次回の議論トピック

- n8n を手動起動する際のコマンド手順の整備（必要に応じて）
