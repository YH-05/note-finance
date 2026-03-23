# 議論メモ: Neo4j APOC有効化とCypherクエリ構築ルール策定

**日付**: 2026-03-23
**参加**: ユーザー + AI

## 背景・コンテキスト

AuraDBバックアップ実行後、research-neo4jの `get_neo4j_schema`（APOC `apoc.meta.schema` 依存）がサンドボックス制限で失敗。
Claudeが Cypher クエリをアドホックに構築しており、スキーマの暗黙知依存・LIMIT不統一・リレーションパス見落としが発生していた。

## 議論のサマリー

1. **AuraDBバックアップ**: research-neo4j → AuraDB Free への移行完了（7,382ノード / 41,357リレーション）
2. **APOC制限の発見**: `NEO4J_dbms_security_procedures_unrestricted=apoc.*` が未設定だったため `apoc.meta.schema` がブロックされていた
3. **NeoData認識の訂正**: `/Volumes/NeoData` はNASではなく外付けSSD。データはbind mountでSSD上に保存されておりコンテナ再作成は安全
4. **全インスタンスAPOC有効化**: research/note/creator/quants の4インスタンス全てで `procedures_unrestricted=apoc.*` を設定してコンテナ再作成
5. **クエリ構築ルール策定**: Cypherクエリ構築前に `*-get_neo4j_schema` でスキーマ事前取得を必須とするルールを作成

## 決定事項

1. 全Neo4jインスタンスで APOC `procedures_unrestricted=apoc.*` を有効化する
2. Cypherクエリ構築前に必ず `*-get_neo4j_schema` でスキーマを事前取得すること（静的ファイル依存禁止）
3. LIMITはデータ量に応じて動的に決定する（固定値禁止）
4. `/Volumes/NeoData` は外付けSSD（NASではない）

## 実施済み

- [x] research-neo4j コンテナ再作成（APOC有効化）
- [x] note-neo4j コンテナ再作成（APOC有効化）
- [x] creator-neo4j コンテナ再作成（APOC有効化 + APOCプラグイン追加）
- [x] quants-neo4j コンテナ再作成（APOC有効化）
- [x] 全インスタンスで `get_neo4j_schema` 動作確認
- [x] `.claude/rules/neo4j-query-construction.md` 作成
- [x] `.claude/rules/README.md` にエントリ追加
- [x] メモリ `reference_neodata_ssd.md` 保存

## 成果物

| ファイル | 内容 |
|---------|------|
| `.claude/rules/neo4j-query-construction.md` | Cypherクエリ構築ルール（スキーマ事前取得必須・動的LIMIT） |
| メモリ `reference_neodata_ssd.md` | NeoDataが外付けSSDである記録 |
