---
name: competitor-analysis
description: |
  note.com金融カテゴリの競合分析とコンテンツギャップ発見。
  競合記事収集、差別化スコアリング、機会レポート生成を行う。
  Use PROACTIVELY when planning new articles, discovering content opportunities, or analyzing competitor trends.
allowed-tools: Bash, Read, Write, Glob, Grep
---

# competitor-analysis スキル

note.com 金融カテゴリの競合状況を分析し、コンテンツ機会を発見するスキル。

## パラメータ

| パラメータ | 必須 | デフォルト | 説明 |
|-----------|------|-----------|------|
| --category | - | 全カテゴリ | 分析対象カテゴリ（market_report, stock_analysis, economic_indicators, investment_education, quant_analysis, asset_management） |
| --depth | - | quick | 分析深度。quick: 5-8検索、full: 10-15検索 |
| --days | - | 30 | 分析対象期間（日数） |

## 処理フロー

### Phase 1: 競合記事収集

参照: `.agents/skills/web-search/SKILL.md`（ツール選択基準）

Web検索で note.com 金融カテゴリの記事を収集する。
日本語コンテンツが対象のため、Gemini Search が推奨。

参照: `references/search-strategy.md`（検索戦略）
参照: `.agents/resources/search-templates/competitor-content.md`（クエリテンプレート）

1. note.com カテゴリスキャン: `site:note.com` クエリで金融記事を検索
2. トレンド交差照合: 現在のトレンドキーワードと note.com 記事を交差検索
3. エンゲージメント信号: 人気記事・話題の記事を検索

depth=quick: 5-8回検索
depth=full: 10-15回検索

### Phase 2: コンテンツギャップ分析

1. 収集した競合記事のトピック・カテゴリを整理
2. 自分の `articles/` フォルダの既存記事と比較
3. 競合がカバーしているが自分がカバーしていないトピックを特定
4. 逆に、自分の強みがあるカテゴリを特定

### Phase 3: 差別化スコアリング

参照: `references/gap-analysis-framework.md`（ギャップ分析フレームワーク）

各ギャップに対して5軸×1-5点でスコアリング:
1. トピックギャップ（そのトピックが未カバーか）
2. 深さギャップ（既存記事より深い分析が可能か）
3. 鮮度ギャップ（より新しい情報で書けるか）
4. 読者レベルギャップ（異なるターゲット層向けに書けるか）
5. フォーマットギャップ（異なる形式で価値を提供できるか）

### Phase 4: 機会レポート出力

`.tmp/competitor-analysis/{timestamp}.md` に分析レポートを出力。

## 出力

### レポート構成
1. エグゼクティブサマリー
2. 競合状況概要（収集記事数、主要クリエイター）
3. コンテンツギャップ一覧（スコア順）
4. 差別化機会トップ5
5. 推奨アクション
6. データソース一覧

### 出力先
`.tmp/competitor-analysis/{YYYYMMDD-HHMM}.md`
