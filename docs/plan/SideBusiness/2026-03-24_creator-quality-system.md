# 議論メモ: creator-neo4j 品質チェック体制の構築と初回改善

**日付**: 2026-03-24
**参加**: ユーザー + AI

## 背景・コンテキスト

creator-neo4j (bolt://localhost:7689) には research-neo4j (kg-quality-check) や note-neo4j (note-quality-check) のような品質チェック手段がなかった。データ投入（creator-enrichment）後の品質劣化（genre欠損、ABOUT未接続、Entity孤立）が手動発見に依存しており、体系的な評価→改善サイクルが必要だった。

## 実施内容

### 1. creator-quality-check スキル・コマンド作成

- `.claude/skills/creator-quality-check/SKILL.md` — 7カテゴリ定量計測 + LLM-as-Judge
- `.claude/commands/creator-quality-check.md` — `/creator-quality-check` コマンド

7カテゴリ: Completeness(20%), Consistency(15%), Structural(15%), Orphan(15%), Content Balance(10%), Source Quality(10%), Taxonomy(15%)

### 2. 初回品質チェック結果

**Overall Score: 81.7/100 (Rating B)**

主要な発見:
- Entity 孤立率 88.8%（426/480）
- Story 不足（全ジャンル 11-14% vs 理想 25%）
- ABOUT 接続率 41.9%（1,960/3,374 Concept 未接続）
- genre=null コンテンツ 759件
- Reddit Source title=null 115件
- ジャンル横断コンテンツの分類不適合（4件/15件サンプル）

### 3. 6つの改善施策の実行

| # | 施策 | 結果 |
|---|------|------|
| 1 | MENTIONS 自動登録ロジック修正 | `emit_creator_queue_v2.py` 修正（about_entities 自動登録） |
| 2a | Story 検索テンプレート追加 | `genre-config.md` に S1-S4（英語4+日本語4） |
| 2b | Story 分類基準強化 | `entity-extraction-prompt-v2.md` に Story 優先判定ルール |
| 3 | ABOUT retroactive リンキング | **1,566件** MERGE（接続率 41.9%→54.8%） |
| 4 | genre プロパティ補完 | **759件** SET |
| 5 | ジャンル検証ステップ追加 | `entity-extraction-prompt-v2.md` にタスク6 追加 |
| 6a | Reddit Source title 補完 | **115件** SET |
| 6b | FROM_SOURCE retroactive リンキング | **13件** MERGE |

### 4. Embedding 有効化

- `entity_linker.py` の `--no-embedding` をデフォルト解除
- Entity 480件 + Concept 3,374件に `multilingual-e5-small` (384dim) embedding 付与
- Vector Index 2つ作成（entity_embedding_idx, concept_embedding_idx）
- `scripts/creator_embed_nodes.py` 新規作成（差分 embed 対応）

### 5. Embedding による新発見と修正

- **Coconala/ココナラ重複** 検出・マージ（類似度 0.959）
- **アフィリエイト系** 15→4 Concept に統合（11件削除、17 ABOUT 移行）
- **タロット系** 16→8 Concept に統合（8件削除、10 ABOUT 移行）
- **category=null** 5件に高信頼カテゴリ自動付与（≥0.95）

### 6. 評価→改善サイクルの制度化

**方法A: creator-enrichment Phase 6（自動）**
- 6-1: embedding 更新（差分）
- 6-2: 自動修復（genre補完、ABOUT リンキング、重複検出）
- 6-3: 簡易品質スコアをログに記録

**方法B: /creator-maintenance（独立コマンド）**
- embedding 更新 → /creator-quality-check → 自動修復 → 重複検出 → Before/After レポート

### 7. creator-enrichment の制約強化

- Phase 2 全5ステップ必須実行（Reddit 省略禁止）
- MUST/NEVER セクション新設

## 決定事項

1. **creator-quality-check スキル作成** — kg-quality-check ベースの7カテゴリ + LLM-as-Judge 構成 (dec-2026-03-24-creator-quality-check)
2. **Embedding デフォルト有効化** — entity_linker.py の Layer 4 を常時有効に (dec-2026-03-24-embedding-enabled)
3. **評価→改善サイクルの制度化** — Phase 6 + /creator-maintenance の2パターン (dec-2026-03-24-maintenance-cycle)

## アクションアイテム

- [ ] /creator-enrichment 実行で Phase 6 動作確認 (優先度: 高)
- [ ] Entity SERVES_AS 自動生成ロジック追加（孤立Entity改善） (優先度: 中)
- [ ] 残り分散 Concept の embedding 統合（category=null 1,437件削減） (優先度: 中)

## Before/After サマリー

| 指標 | Before | After |
|------|--------|-------|
| genre=null | 759 | 0 |
| ABOUT リレーション | 2,685 | 4,251 (+58%) |
| ABOUT 接続率 | 41.9% | 54.8% (+12.9pt) |
| FROM_SOURCE | 1,242 | 1,255 |
| Reddit Source title=null | 115 | 0 |
| リレーション総数 | 10,009 | 11,588 (+15.8%) |
| Concept 総数 | 3,374 | 3,355 (-19 統合) |
| Entity 総数 | 480 | 479 (-1 重複マージ) |
| Vector Index | 0 | 2 (entity + concept) |
| Embedding 付与 | 0 | 3,854 ノード |
