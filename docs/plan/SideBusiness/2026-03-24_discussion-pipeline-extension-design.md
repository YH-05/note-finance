# 議論メモ: データ投入パイプライン拡張設計

**日付**: 2026-03-24
**参加**: ユーザー + AI

## 背景・コンテキスト

一気通貫パイプライン（run_pipeline）が research-neo4j 向けに完成した後、creator-neo4j との差異を分析し、両インスタンスへの統一的なパイプライン拡張方針を議論した。

## 議論のサマリー

### research-neo4j vs creator-neo4j の差異

| 項目 | research-neo4j | creator-neo4j |
|---|---|---|
| スキーマ | KG v3.0 FIBO | creator-2.0 |
| 抽出対象 | Fact/Claim/Entity/Topic | Fact/Tip/Story/Entity/Concept/ConceptCategory |
| Entity Linker | なし | 3層マッチング（完全一致→Full-Text→APOC fuzzy） |
| emit スクリプト | emit_research_queue.py | emit_creator_queue_v2.py |
| Python 投入 | neo4j_loader.py | なし（スキル経由のみ） |
| pipeline.py | run_pipeline() 対応 | 未対応 |

### 合意事項

1. **Layer 0→2 は完全に共通**（ソース選択→収集→原文保存）
2. **Layer 3 以降は target で分岐**（抽出プロンプト・スキーマが根本的に異なるため統一不可）
3. **Entity Linker はドメイン非依存**で共通化可能

## 決定事項

1. **Entity Linker 両インスタンス対応** (dec-2026-03-24-entity-linker-both-instances)
   - entity_linker.py を --instance パラメータで切り替え
   - research-neo4j に Full-Text Index + Alias ノード新設

2. **ベクトル類似度リンキング第4層** (dec-2026-03-24-vector-similarity-linking)
   - e5-small embedding、optional dependency（sentence-transformers）
   - 未インストール時は第3層で停止

3. **creator-neo4j Python 直接投入** (dec-2026-03-24-creator-neo4j-python-loader)
   - neo4j_loader.py に ingest_to_creator_neo4j() 追加
   - save-to-creator-graph スキルは対話的利用として残す

4. **run_pipeline target 分岐** (dec-2026-03-24-pipeline-target-branching)
   - `run_pipeline(target="research"|"creator")`
   - Layer 0-2 共通、Layer 3 以降分岐

## アクションアイテム

- [x] research-neo4j に Full-Text Index 3本 + Vector Index 1本作成 + link_entities=True 動作確認 (完了)
- [x] e5-small ベクトル類似度リンキング第4層 動作確認 (完了 — 3 Entity全てRESOLVED)
- [x] 日次バッチCLI `python -m data_pipeline` 実装 (完了 — collect/registry サブコマンド)
- [x] neo4j_loader.py に creator-neo4j 投入関数追加 (完了 — CreatorGraphWriterアダプター)
- [x] run_pipeline(target="creator") 実装 (完了 — dry-run テスト成功 276n/359r)
- [x] pyproject.toml embedding optional dependency 追加 (完了)
- [x] ScrapingCollector 追加 (完了 — サイトマップベース)

## 次回の議論トピック

- creator 向け LLM 抽出プロンプトの設計（Fact/Tip/Story + ConceptCategory 分類）
- ベクトル類似度の閾値設定（コサイン類似度 0.85? 0.90?）
- 日次バッチ CLI の実装（cronジョブ対応）
