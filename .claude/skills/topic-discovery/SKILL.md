---
name: topic-discovery
description: |
  記事トピック発掘のオーケストレーター。Web検索ベースのトレンドリサーチ、既存記事ギャップ分析、finance-topic-suggesterによるスコアリングでデータ駆動のトピック提案を生成。
  Use PROACTIVELY when suggesting article topics, discovering content gaps, or planning new finance articles.
allowed-tools: Read, Bash, Glob, Grep, Task
---

# topic-discovery スキル

記事トピック発掘のオーケストレータースキル。Web検索ベースのトレンドリサーチで、データ駆動のトピック提案を生成する。
Web検索ツールの選択は `.claude/skills/web-search/SKILL.md` に従う。

## パラメータ

| パラメータ | 必須 | デフォルト | 説明 |
|-----------|------|-----------|------|
| --category | - | 全カテゴリ | 特定カテゴリに限定（market_report, stock_analysis, economic_indicators, investment_education, quant_analysis, asset_management） |
| --count | - | 5 | 提案数 |
| --no-search | - | false | Web検索を使用せずLLM知識のみでトピック生成（従来動作互換） |

## 処理フロー

### Phase 1: トレンドリサーチ（`--no-search` 時はスキップ）

Web検索を 8-12回実行し、現在のトレンド情報を収集する。
ツール選択は `.claude/skills/web-search/SKILL.md` 参照（日本市場クエリは Gemini Search 推奨）。

参照: `references/search-strategy.md`（検索クエリ配分・戦略）
参照: `.claude/resources/search-templates/`（クエリテンプレート集）

1. 市場トレンド検索（3回）: index-market.md, macro-economy.md テンプレート使用
2. セクター動向検索（2回）: sectors.md テンプレート使用
3. AI・テクノロジー検索（2回）: ai-tech.md テンプレート使用
4. 日本市場検索（2回）: japan-market.md テンプレート使用
5. コンテンツギャップ検索（1-3回）: competitor-content.md テンプレート使用

### Phase 2: ギャップ分析

1. `articles/` フォルダをスキャンし、既存記事の `article-meta.json` を読み込む
2. カテゴリ分布を集計
3. Phase 1 の検索結果と既存記事を比較し、カバーされていないトピックを特定

### Phase 3: トピック生成・評価

参照: `references/scoring-rubric.md`（5軸評価ルーブリック）
参照: `references/reader-profile.md`（note.com 読者特性）

1. Phase 1-2 の結果を入力として finance-topic-suggester エージェントを呼び出す
2. 5軸評価（timeliness, information_availability, reader_interest, feasibility, uniqueness）
3. スコア順にソート

### Phase 4: 構造化レポート出力

JSON形式でトピック提案を出力（finance-topic-suggester の出力スキーマに準拠）。

## 出力

finance-topic-suggester エージェントの出力スキーマ（JSON）に準拠。
追加フィールド:
- `search_insights`: Phase 1 で収集したトレンド情報のサマリー（`--no-search` 時は null）
- `content_gaps`: Phase 2 で特定されたギャップ情報

## `--no-search` モード

Web検索を使用せず、LLM の知識のみでトピックを生成する。
Phase 1 をスキップし、Phase 2（既存記事確認）→ Phase 3（LLM生成）→ Phase 4 の流れで実行。
従来の finance-topic-suggester と同等の動作を維持。
