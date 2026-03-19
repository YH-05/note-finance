---
name: topic-discovery
description: |
  記事トピック発掘のオーケストレーター。research-neo4jからの知識ギャップ発掘、Web検索ベースのトレンドリサーチ、既存記事ギャップ分析、topic-suggesterによるスコアリングでデータ駆動のトピック提案を生成。
  検索結果はresearch-neo4jに永続化する。
  Use PROACTIVELY when suggesting article topics, discovering content gaps, or planning new finance articles.
allowed-tools: Read, Bash, Glob, Grep, Task
---

# topic-discovery スキル

記事トピック発掘のオーケストレータースキル。research-neo4j の知識ギャップとWeb検索トレンドを組み合わせ、データ駆動のトピック提案を生成する。
Web検索ツールの選択は `.claude/skills/web-search/SKILL.md` に従う。

## パラメータ

| パラメータ | 必須 | デフォルト | 説明 |
|-----------|------|-----------|------|
| --category | - | 全カテゴリ | 特定カテゴリに限定（market_report, stock_analysis, macro_economy, asset_management, side_business, quant_analysis, investment_education） |
| --count | - | 5 | 提案数 |
| --no-search | - | false | Web検索を使用せずLLM知識のみでトピック生成（従来動作互換） |
| --skip-kg | - | false | KG照会をスキップする（Neo4j未起動時に使用） |

## 処理フロー概要

```
Phase 0: KGトピック発掘（research-neo4j 照会）
Phase 1: トレンドリサーチ（Web検索 8-12回）
Phase 2: ギャップ分析（既存記事確認）
Phase 3: トピック生成・評価（KG補正付きスコアリング）
Phase 4: 構造化レポート出力
Phase 5: 結果の保存（ファイル + research-neo4j）
```

### Phase 0: KGトピック発掘

参照: `references/kg-topic-mining.md`（Cypherクエリテンプレート・候補生成ロジック）

research-neo4j（bolt://localhost:7688）から既存データをマイニングし、KG由来のトピック候補を生成する。
`mcp__neo4j-research__research-read_neo4j_cypher` を ToolSearch でロードして使用する。

**Neo4j未起動時**: 警告を出力して Phase 0 をスキップし、Phase 1 に進む。

#### Phase 0-A: KGデータマイニング（8クエリ）

1. **未回答Question** (Q1): status: open の Question → 知識ギャップから記事テーマ候補
2. **Insight (gap)** (Q2): AI検出済みの情報ギャップ → 記事テーマ候補
3. **Entity カバレッジ密度** (Q3): Fact/Claim が少ないが関連が多い Entity → 深掘り記事
4. **ソース急増Entity** (Q4): 直近30日でソースが急増 → トレンドテーマ
5. **過去の未決定提案** (Q5): 前回 `selected: null` の提案 → 再評価
6. **Entity 間リレーション** (Q6): COMPETES_WITH/CAUSES 等 → クロスカッティング切り口
7. **センチメント対立** (Q7): bullish/bearish 拮抗 → 論争テーマ
8. **KG 全体統計** (Q8): 照会のコンテキスト把握

#### Phase 0-B: KG由来トピック候補の生成

マイニング結果から4種のトピック候補を生成:

| 候補種別 | ソース | kg_gap_score 目安 |
|---------|--------|-----------------|
| Knowledge Gap | Q1 (Question) + Q2 (Insight gap) | 6-10 |
| Underexplored Entity | Q3 (薄カバレッジ Entity) | 4-8 |
| Trending Entity | Q4 (ソース急増) | 3-6 |
| Controversy | Q7 (センチメント対立) | 5-9 |

各候補に `kg_gap_score`（0-10）を付与し、Phase 3 のスコアリング補正に使用する。

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

1. `articles/` フォルダをスキャンし、既存記事の `meta.yaml` を読み込む
2. カテゴリ分布を集計
3. Phase 0 の KG 由来候補 + Phase 1 の検索結果と既存記事を比較し、カバーされていないトピックを特定

### Phase 3: トピック生成・評価（KG補正付き）

参照: `references/scoring-rubric.md`（5軸評価ルーブリック + KGデータ補正ルール）
参照: `references/reader-profile.md`（note.com 読者特性）

1. Phase 0-2 の結果を入力として topic-suggester エージェントを呼び出す
   - **KG由来候補も候補リストに含める**（Web検索候補とマージ）
2. 5軸評価（timeliness, information_availability, reader_interest, feasibility, uniqueness）
3. **KGデータ補正を適用**:
   - Information Availability: KG に Fact/Claim が豊富 → 加算
   - Uniqueness: KG 由来/Controversy トピック → 加算、過去提案済み → 減算
   - KG Gap Score ボーナス: kg_gap_score 8-10 → +3点、5-7 → +2点、3-4 → +1点
4. 補正後スコア順にソート

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

#### 5.3 research-neo4j への保存（パイプライン経由）

参照: `.claude/rules/neo4j-write-rules.md`（直書き禁止ルール）
参照: `.claude/skills/emit-research-queue/SKILL.md`

提案結果を research-neo4j に保存する。
**重要**: Cypher 直書きは禁止。標準パイプライン（`emit_graph_queue.py → /save-to-graph`）経由で投入する。

**前提条件チェック**:

```bash
docker inspect research-neo4j --format='{{.State.Status}}' 2>/dev/null
```

- `running` → 保存処理を続行
- それ以外 → 警告出力して Phase 5.3 をスキップ（入力JSONは `.tmp/research-input/` に保持、後から投入可能）

**ステップ 5.3.1: 入力JSON構築**

セッションファイル（Phase 5.1）の内容から `emit_graph_queue.py --command topic-discovery` の入力JSONを構築する。

```json
{
  "session_id": "{session_id}",
  "research_topic": "トピック提案セッション {YYYY-MM-DD}",
  "as_of_date": "{today}",
  "sources": [
    {
      "url": "internal://topic-discovery/{session_id}",
      "title": "トピック提案セッション {YYYY-MM-DD}",
      "authority_level": "blog",
      "published_at": "{today}",
      "source_type": "original"
    }
  ],
  "entities": [
    {
      "name": "{ticker}",
      "entity_type": "{index|company}"
    }
  ],
  "topics": [
    {
      "name": "{カテゴリ日本語名}",
      "category": "content_planning"
    }
  ],
  "facts": [
    {
      "content": "{key_finding テキスト}",
      "source_url": "internal://topic-discovery/{session_id}",
      "confidence": 0.8,
      "about_entities": []
    }
  ]
}
```

**データマッピング**:

| セッションデータ | 入力JSON フィールド |
|----------------|-------------------|
| suggestions[].suggested_symbols | entities[]（`^` 始まり → index, 他 → company） |
| suggestions[].category | topics[]（カテゴリ名マッピング適用） |
| search_insights.trends[].key_findings | facts[]（`--no-search` 時は空配列） |

**ステップ 5.3.2: graph-queue JSON 生成**

```bash
uv run python scripts/emit_graph_queue.py \
  --command topic-discovery \
  --input .tmp/research-input/{session_id}.json
```

`emit_graph_queue.py` が `topic-discovery` コマンドをサポートしていない場合は `web-research` で代替する。

**ステップ 5.3.3: Neo4j 投入**

`/save-to-graph` スキルを呼び出して graph-queue JSON を Neo4j に投入する。

**エラー時**: graph-queue 生成または Neo4j 投入でエラーが発生した場合、エラー内容を警告表示するがスキルは正常終了とする（Phase 5.1-5.2 のファイル保存は完了済み）。

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
| research-neo4j | `bolt://localhost:7688` | Source/Topic/Claim/Entity/Fact ノードとリレーション |

## `--no-search` モード

Web検索を使用せず、LLM の知識のみでトピックを生成する。
Phase 1 をスキップし、Phase 2（既存記事確認）→ Phase 3（LLM生成）→ Phase 4 → Phase 5 の流れで実行。
従来の topic-suggester と同等の動作を維持。
`search_insights` は `null` で保存される。

## Observability

スキル実行のトレースを `scripts/skill_run_tracer.py` で記録する。
Neo4j 未起動時はグレースフルデグラデーションにより合成 ID を返し、スキル実行をブロックしない。

### 実行開始時（Phase 1 の前）

```bash
SKILL_RUN_ID=$(python3 scripts/skill_run_tracer.py start \
    --skill-name topic-discovery \
    --command-source "/topic-discovery" \
    --input-summary "category=${CATEGORY:-all}, count=${COUNT:-5}, no_search=${NO_SEARCH:-false}")
```

### 実行完了時（成功 — Phase 5 完了後）

```bash
python3 scripts/skill_run_tracer.py complete \
    --skill-run-id "$SKILL_RUN_ID" \
    --status success \
    --output-summary "${SUGGESTION_COUNT} topics suggested, top_score=${TOP_SCORE}, categories=${CATEGORIES_SUGGESTED}"
```

### 実行完了時（部分成功 — Phase 5.3 Neo4j 保存スキップ時）

```bash
python3 scripts/skill_run_tracer.py complete \
    --skill-run-id "$SKILL_RUN_ID" \
    --status partial \
    --output-summary "${SUGGESTION_COUNT} topics suggested (Neo4j save skipped)" \
    --error-message "Phase 5.3: research-neo4j not running" \
    --error-type "neo4j_connection"
```

### 実行完了時（エラー — 任意の Phase で失敗時）

```bash
python3 scripts/skill_run_tracer.py complete \
    --skill-run-id "$SKILL_RUN_ID" \
    --status failure \
    --error-message "Phase ${FAILED_PHASE}: ${ERROR_MSG}" \
    --error-type "${ERROR_TYPE}"
```

`error_type` の分類:

| error_type | 説明 |
|------------|------|
| web_search_failure | Web検索実行の失敗（Phase 1） |
| gap_analysis_failure | 既存記事スキャン・ギャップ分析の失敗（Phase 2） |
| topic_generation_failure | topic-suggester 呼び出し・スコアリングの失敗（Phase 3） |
| file_save_failure | セッションファイル・履歴ファイルの保存失敗（Phase 5.1-5.2） |
| neo4j_connection | research-neo4j 接続失敗（Phase 5.3） |
| cypher_execution | Cypher 実行エラー（Phase 5.3） |
