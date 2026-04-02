# 議論メモ: Neo4j Community → Enterprise 移行

**日付**: 2026-04-02
**参加**: ユーザー + AI

## 背景・コンテキスト

Neo4j Community Edition で4つの別コンテナ（note:7687, research:7688, creator:7689, quants:7690）を運用していたが、インスタンスレベルでの一元管理を目的に Enterprise Edition（Developer License、無料）への移行を実施した。

## 議論のサマリー

1. Enterprise への切り替え可否を確認 → Developer License で無料利用可能
2. 4コンテナ → 1コンテナ（multi-database）の統合方針を決定
3. 影響範囲を棚卸し（docker-compose, MCP設定, Python src/scripts）
4. Phase 0-5 の移行計画を策定し実行

## 決定事項

1. **Enterprise 1コンテナ統合**: Community 4コンテナを Enterprise 1コンテナ（neo4j:5.26-enterprise）に統合
2. **Database命名**: note / research / creator / quants の4データベースで分離
3. **共有docker-compose**: note-finance と quants 両リポジトリに同一定義を配置
4. **接続方式**: `bolt://localhost:7687` + `database=<name>` パラメータで分離。環境変数 `NEO4J_URI` + `NEO4J_*_DB` で設定可能

## 実施結果

| Database | Nodes | Relationships | Status |
|----------|-------|---------------|--------|
| note | 214 | 279 | online |
| research | 14,675 | 482,146 | online |
| creator | 10,945 | 19,348 | online |
| quants | 3,357 | 7,860 | online |

### 変更ファイル

| カテゴリ | ファイル数 | 内容 |
|---------|----------|------|
| docker-compose.yml | 2 | Community → Enterprise |
| .mcp.json | 2 | ポート統一 + database名指定 |
| .env | 2 | NEO4J_URI + NEO4J_*_DB 追加 |
| src/ | 4 | neo4j_loader.py, pipeline.py, neo4j_writer.py, linker.py |
| scripts/ | 22 | neo4j_utils.py + 21スクリプト |

## アクションアイテム

- [x] 旧Community Docker volume/ディレクトリのクリーンアップ (優先度: 低) → `/Volumes/NeoData/trash-old-community/` に退避完了
- [x] quants側スキル/コマンドの bolt://localhost:7690 参照を更新 (優先度: 中) → 8ファイル更新完了
- ~~AuraDB バックアップスクリプトの Enterprise multi-database 対応~~ → 不要と判断、削除

## 次回の議論トピック

- Enterprise RBAC（ロールベースアクセス制御）の活用検討
- バックアップ戦略の見直し（Enterprise オンラインバックアップの活用）
- メモリ設定のチューニング（4DB統合後の最適値）
