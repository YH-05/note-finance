# 議論メモ: Neo4j データを SSD（NeoData）からローカル PC へ移行

**日付**: 2026-04-27
**参加**: ユーザー + AI

## 背景・コンテキスト

外付けSSD `/Volumes/NeoData` 上の Docker コンテナで Neo4j Enterprise をホストしていると認識していたが、SSDマウントへの依存を外してローカルPCで起動・保存する構成に変えたい、という相談から開始。

## 議論のサマリー

### 現状調査の結果（重要な発見）

`docker inspect neo4j-enterprise` で確認したところ、**実行中のコンテナは既に `/Users/yukihata/neo4j-data/enterprise/` をバインド** していた。一方 `docker-compose.yml` は `/Volumes/NeoData/enterprise/...` のままで設定と実態が乖離。

| 項目 | パス | サイズ | 状態 |
|------|------|--------|------|
| 動いているコンテナ実体 | `/Users/yukihata/neo4j-data/enterprise/` | 2.2G | 現用（最新） |
| `docker-compose.yml` の記述 | `/Volumes/NeoData/enterprise/` | 1.5G | 旧データ |

過去に手動 `docker run` 等で別経路から起動された可能性が高く、compose は古いパスのまま残っていた。

### 実施した移行作業

1. **`docker-compose.yml` の neo4j ボリューム4行をローカルパスに書き換え**
   - `/Volumes/NeoData/enterprise/{data,logs,plugins,import}` → `/Users/yukihata/neo4j-data/enterprise/{data,logs,plugins,import}`

2. **コンテナを compose 経由で再作成**
   - `docker stop neo4j-enterprise && docker rm neo4j-enterprise`
   - `docker compose up -d neo4j`
   - healthcheck で healthy 到達を確認
   - マウント先がローカルになっていることを `docker inspect` で再確認

3. **データ整合性確認**
   - `SHOW DATABASES` で5DB（creator / note / quants / research / neo4j + system）すべて online を確認

### SSD 旧データの扱い

ユーザー判断により、`/Volumes/NeoData/enterprise/`（1.5G）および隣接する `neo4j-research/`, `neo4j-creator/`, `note-finance-data/` などの旧データは**今回は操作しない**こととする（退避は将来検討）。

## 決定事項

1. `docker-compose.yml` の Neo4j ボリュームをローカル `/Users/yukihata/neo4j-data/enterprise/` に変更し、起動経路を `docker compose` に統一する（実施済）。
2. SSD `/Volumes/NeoData/enterprise/` 配下の旧データは今回は退避せず、現状のまま保持する。

## アクションアイテム

- [ ] SSD 旧データ（`/Volumes/NeoData/enterprise/`）の退避要否を判断（優先度: 低）
- [ ] SSD `/Volumes/NeoData/{neo4j-research, neo4j-creator, note-finance-data}` の退避要否を判断（優先度: 低）

## 次回の議論トピック

- SSD 旧データの最終的な処遇（`backups/` への移動 or 削除）
- 数日〜数週間ローカル運用後に問題ないか観測してからの判断

## 参考情報

- 旧 docker-compose 設定: `git show HEAD -- docker-compose.yml` で確認可能
- 関連メモリ: `project_neo4j_enterprise.md`（Community 4コンテナ→Enterprise 1コンテナ統合）
- ローカルディスク空き: 35Gi / 228Gi（DB 2.2G に対し十分）
