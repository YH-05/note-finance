# 議論メモ: PR #238 KG v3.0 FIBO準拠オントロジー再設計マージ

**日付**: 2026-03-23
**参加**: ユーザー + AI

## 背景・コンテキスト

research-neo4j のナレッジグラフスキーマを KG v2.2 から KG v3.0（FIBO準拠）に再設計するPR #238 をマージした。
PR は feature/kg-v3-ontology-redesign ブランチで開発され、22ファイル変更（+10,599/-971行）の大規模変更。

## 議論のサマリー

### CI失敗と修正

マージ試行時にCI失敗が2種類発生:

1. **Bandit B324 (Lint)**: `src/creator/image_hosting.py` の `hashlib.md5()` に `usedforsecurity=False` が未設定
2. **Unit Tests 13件失敗**: KG v3.0 のスキーマ変更に伴うテスト更新漏れ
   - `schema_version`: `"2.2"` → `"3.0"` (6テストファイル)
   - リレーションキーセット: 21種 → 41種 (3テストファイル、v3.0分類リレーション20種追加)

### 修正と再CI

- サブエージェントで全修正を実施（510テストパス確認）
- 修正コミット push 後、CI全チェック（Lint, Type Check, KG Quality, Unit Tests, All Checks Passed）がパス
- スカッシュマージ + ブランチ削除を実行

## 決定事項

1. **KG v3.0 スキーマがアクティブ化**: SCHEMA_VERSION=3.0、41種のリレーションキー、33ノード・59リレーション設計
2. **FIBO準拠の薄いハブノード設計**: 分類リレーション20種が新規追加（is_source_type, from_domain, rated_as, in_language, ingested_via, is_type, has_identifier, in_industry, is_fact_type, is_claim_type, in_unit, is_datapoint_type, is_category, is_author_type, affiliated_with, alias_of, parent_class, in_parent_sector, issued_by, is_instrument_class）

## アクションアイテム

- [ ] KG v3.0 移行実行: neo4j-lifecycle --instance research --phase C（Migration） (優先度: 高)
- [ ] KG v3.0 品質検証: 移行後に /kg-quality-check を実行 (優先度: 中)

## 次回の議論トピック

- v3.0 移行の実行タイミングと手順確認
- 移行後のデータ整合性検証結果レビュー
- save-to-graph スキルの v3.0 対応状況確認
