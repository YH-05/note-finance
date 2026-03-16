---
name: topic-discovery
description: |
  記事トピック発掘のオーケストレーター。Web検索ベースのトレンドリサーチ、既存記事ギャップ分析、topic-suggesterによるスコアリングでデータ駆動のトピック提案を生成。
  Use PROACTIVELY when suggesting article topics, discovering content gaps, or planning new finance articles.
allowed-tools: Read, Bash, Glob, Grep, Task
---

# topic-discovery スキル

記事トピック発掘のオーケストレータースキル。Web検索ベースのトレンドリサーチで、データ駆動のトピック提案を生成する。
Web検索ツールの選択は `.agents/skills/web-search/SKILL.md` に従う。

## パラメータ

| パラメータ | 必須 | デフォルト | 説明 |
|-----------|------|-----------|------|
| --category | - | 全カテゴリ | 特定カテゴリに限定（market_report, stock_analysis, macro_economy, asset_management, side_business, quant_analysis, investment_education） |
| --count | - | 5 | 提案数 |
| --no-search | - | false | Web検索を使用せずLLM知識のみでトピック生成（従来動作互換） |

## 処理フロー

### Phase 1: トレンドリサーチ（`--no-search` 時はスキップ）

Web検索を 8-12回実行し、現在のトレンド情報を収集する。
ツール選択は `.agents/skills/web-search/SKILL.md` 参照（日本市場クエリは Gemini Search 推奨）。

参照: `references/search-strategy.md`（検索クエリ配分・戦略）
参照: `.agents/resources/search-templates/`（クエリテンプレート集）

1. 市場トレンド検索（3回）: index-market.md, macro-economy.md テンプレート使用
2. セクター動向検索（2回）: sectors.md テンプレート使用
3. AI・テクノロジー検索（2回）: ai-tech.md テンプレート使用
4. 日本市場検索（2回）: japan-market.md テンプレート使用
5. コンテンツギャップ検索（1-3回）: competitor-content.md テンプレート使用

### Phase 2: ギャップ分析

1. `articles/` フォルダをスキャンし、既存記事の `meta.yaml` を読み込む
2. カテゴリ分布を集計
3. Phase 1 の検索結果と既存記事を比較し、カバーされていないトピックを特定

### Phase 3: トピック生成・評価

参照: `references/scoring-rubric.md`（5軸評価ルーブリック）
参照: `references/reader-profile.md`（note.com 読者特性）

1. Phase 1-2 の結果を入力として topic-suggester エージェントを呼び出す
2. 5軸評価（timeliness, information_availability, reader_interest, feasibility, uniqueness）
3. スコア順にソート

### Phase 4: 構造化レポート出力

JSON形式でトピック提案を出力（topic-suggester の出力スキーマに準拠）。

### Phase 5: 結果の保存

提案結果をファイルシステムに保存する。**この Phase は必須であり、スキップしてはならない。**

#### 5.1 セッションファイルの保存

```bash
mkdir -p .tmp/topic-suggestions
```

以下の JSON を `.tmp/topic-suggestions/{YYYY-MM-DD}_{HHMM}.json` に保存:

```json
{
  "session_id": "topic-suggestion-{YYYY-MM-DD}T{HHMM}",
  "generated_at": "ISO 8601形式",
  "parameters": {
    "category": null,
    "count": 5,
    "no_search": false
  },
  "search_insights": {
    "queries_executed": 10,
    "trends": [
      {
        "query": "検索クエリ",
        "source": "tavily | gemini | rss",
        "key_findings": ["発見事項1", "発見事項2"]
      }
    ]
  },
  "content_gaps": {
    "category_distribution": {"market_report": 3, "quant_analysis": 0},
    "underserved_categories": ["quant_analysis", "asset_management"],
    "gap_topics": ["不足しているトピック領域の説明"]
  },
  "suggestions": [
    {
      "rank": 1,
      "topic": "トピック名",
      "category": "market_report",
      "suggested_symbols": ["^GSPC"],
      "suggested_period": "2026-03-03 to 2026-03-07",
      "scores": {
        "timeliness": 9,
        "information_availability": 8,
        "reader_interest": 8,
        "feasibility": 9,
        "uniqueness": 7,
        "total": 41
      },
      "rationale": "提案理由",
      "key_points": ["ポイント1", "ポイント2"],
      "target_audience": "intermediate",
      "estimated_word_count": 4000,
      "selected": null
    }
  ],
  "category_balance": {"market_report": 3, "stock_analysis": 4},
  "recommendation": "次に書くべきカテゴリの提案"
}
```

**`selected` フィールド**: `null`（未決定）、`true`（採用→記事作成済み）、`false`（不採用）。
`/new-finance-article` 実行時に自動更新される。

#### 5.2 履歴ファイルへの追記

`data/topic-history/suggestions.jsonl` に1行のJSON（セッション要約）を追記:

```bash
# suggestions.jsonl に追記（1セッション = 1行）
echo '{"session_id":"...","generated_at":"...","count":5,"top_topic":"...","top_score":41,"categories_suggested":["market_report","stock_analysis"]}' >> data/topic-history/suggestions.jsonl
```

**JSONL 1行の形式**:

```json
{
  "session_id": "topic-suggestion-2026-03-09T1430",
  "generated_at": "2026-03-09T14:30:00+09:00",
  "parameters": {"category": null, "count": 5, "no_search": false},
  "suggestion_count": 5,
  "top_topic": "最高スコアのトピック名",
  "top_score": 41,
  "categories_suggested": ["market_report", "stock_analysis"],
  "selected_topics": [],
  "session_file": ".tmp/topic-suggestions/2026-03-09_1430.json"
}
```

`selected_topics` は `/new-finance-article` でトピック採用時に更新される。

## 出力

topic-suggester エージェントの出力スキーマ（JSON）に準拠。
追加フィールド:
- `search_insights`: Phase 1 で収集したトレンド情報のサマリー（`--no-search` 時は null）
- `content_gaps`: Phase 2 で特定されたギャップ情報

## 保存先

| 保存先 | パス | 用途 |
|--------|------|------|
| セッションファイル | `.tmp/topic-suggestions/{YYYY-MM-DD}_{HHMM}.json` | 完全な提案データ（検索結果含む） |
| 履歴ファイル | `data/topic-history/suggestions.jsonl` | セッション要約の追記ログ |

## `--no-search` モード

Web検索を使用せず、LLM の知識のみでトピックを生成する。
Phase 1 をスキップし、Phase 2（既存記事確認）→ Phase 3（LLM生成）→ Phase 4 → Phase 5 の流れで実行。
従来の topic-suggester と同等の動作を維持。
`search_insights` は `null` で保存される。
