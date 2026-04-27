---
name: topic-suggest
description: 金融・投資記事のトピックを提案します。研究 KG (research-neo4j) のマイニング、ローカル articles/ の被覆ギャップ分析、外部トレンド（RSS/Reddit/SEC EDGAR）を組み合わせ、5軸スコアリングで最適な執筆候補を提示します。
allowed-tools: Read, Bash, Glob, Grep, ToolSearch, Task
---

# 金融記事トピック提案スキル

研究 KG・ローカル既出記事・外部トレンドの3層から、データ駆動で記事トピックを提案します。

## パラメータ

| パラメータ | 必須 | デフォルト | 説明 |
|-----------|------|-----------|------|
| --category | - | 全カテゴリ | 特定カテゴリに限定（macro_economy, stock_analysis, asset_management, investment_education, earnings, market_report） |
| --count | - | 5 | 提案数 |
| --no-search | - | false | Web検索を使用せずKG・ローカル分析のみで生成 |
| --skip-kg | - | false | research-neo4j 照会をスキップ（Neo4j未起動時に使用） |

## 処理フロー

```
Phase 0: データマイニング（KG + ローカル articles/）
    |  research-neo4j 照会（kg-topic-mining.md の8クエリ + own_article 3クエリ）
    |  scripts/mine_local_articles.py 実行（既出記事・カテゴリ被覆・直近30日）
    |
Phase 1: 外部トレンド調査（--no-search でスキップ）
    |  Reddit / RSS / SEC EDGAR / Wikipedia
    |
Phase 2: トピック生成・スコアリング（5軸×10点 = 50点満点）
    |  KG由来候補 + Underexplored Entity + Trending Entity + Controversy + 自記事ギャップ
    |
Phase 3: 提示・保存
    |  .tmp/topic-suggest/{YYYY-MM-DD}_{HHMM}.json + data/topic-history/suggestions.jsonl
```

### Phase 0-A: ローカル articles/ マイニング（必須）

```bash
uv run python scripts/mine_local_articles.py
# → .tmp/topic-suggest/local_articles_mining.json
```

出力フィールド:
- `by_category`: カテゴリ別記事数
- `by_status`: published / draft / review 集計
- `recent`: 直近30日の記事一覧（重複回避用）
- `stale_categories`: 90日以上更新されていないカテゴリ（テコ入れ候補）
- `top_symbols`: 既出シンボル頻度（被覆ギャップ算出用）
- `draft_keywords`: 各記事から抽出したキーワード（被覆チェック用）

### Phase 0-B: research-neo4j マイニング（`--skip-kg` でスキップ）

参照: `references/kg-topic-mining.md`（8クエリ + 候補生成ロジック）

`mcp__neo4j-research__research-read_neo4j_cypher` を ToolSearch でロードして使用する。

| クエリ | 候補種別 | kg_gap_score 目安 |
|--------|---------|-----------------|
| Q1 (Question) | Knowledge Gap | 6-10 |
| Q2 (Insight gap) | Knowledge Gap | 6-9 |
| Q3 (薄カバレッジ) | Underexplored Entity | 4-8 |
| Q4 (ソース急増) | Trending Entity | 3-6 |
| Q5 (再評価) | Past proposal | 2-7 |
| Q6 (Entity 間リレーション) | Cross-cutting | 4-7 |
| Q7 (センチメント対立) | Controversy | 5-9 |
| Q8 (KG統計) | コンテキスト | - |

#### 自記事専用クエリ

参照: `references/kg-own-article-mining.md`

株投資ラボ自身の記事（`command_source='own-articles'` で識別）に絞った 5 クエリ:

| クエリ | 候補種別 | 用途 |
|--------|---------|------|
| OWN-Q1 | Underexplored Own-Mentioned | 自分が言及した未深掘り Entity |
| OWN-Q2 | Coverage Gap Category | 外部 Source 多 vs 自記事少のカテゴリ |
| OWN-Q3 | Counter-Claim | 自分 Claim と外部 Claim の対立 |
| OWN-Q4 | 自記事の鮮度一覧 | 補助（続編候補抽出） |
| OWN-Q5 | Recurring Series | 複数記事で言及の Entity → シリーズ化候補 |

**投入状況確認**:
```cypher
MATCH (s:Source {command_source: 'own-articles'}) RETURN count(s)
```
0件の場合は `uv run python scripts/emit_own_articles_queue.py` で投入する。

### Phase 1: 外部トレンド調査

`--no-search` 指定時はスキップ。それ以外では以下を組み合わせる:

- **Reddit (`reddit-finance-topics` スキル)**: 投資コミュニティの議論
- **RSS (`rss` MCP)**: 金融ニュースフィード
- **SEC EDGAR (`sec-edgar-mcp`)**: 8-K/10-Q の重要イベント
- **Wikipedia**: 背景知識補完

Web検索ツールの選択は `.claude/skills/web-search/SKILL.md` に従う。

### Phase 2: トピック生成・スコアリング

参照: `references/scoring-rubric.md`（5軸ルーブリック）

5軸（各1-10点、合計50点）:
- timeliness（時事性）
- information_availability（情報入手性）
- reader_interest（読者関心度）
- feasibility（執筆実現性）
- uniqueness（独自性）

**KG補正**: kg_gap_score (0-10) を uniqueness と feasibility に上乗せして優先度を高める。

**重複ペナルティ**: Phase 0-A の `recent` または `top_symbols` と高重複の候補は uniqueness を減点。

### Phase 3: 提示・保存

```markdown
## 既存記事の状況
- 総記事数: N件 / カテゴリ分布: [...]
- 直近30日の投稿: M件
- 停滞カテゴリ: [...]

## KG マイニング結果
- Knowledge Gap: X件 / Underexplored: Y件 / Trending: Z件 / Controversy: W件

## 提案トピック

### 1. [タイトル]
- カテゴリ / スコア XX/50 (内訳付き)
- 提案理由 / 構成骨子 / 推奨ツール
- 重複チェック: 既出記事との被り度
```

セッションファイル: `.tmp/topic-suggest/{YYYY-MM-DD}_{HHMM}.json`
履歴追記: `data/topic-history/suggestions.jsonl`

## 次のステップ

トピック決定後は `/article-init "選択トピック"` または `/article-full` で記事作成を開始する。

## 関連リソース

| リソース | パス |
|---------|------|
| ローカルマイニングスクリプト | `scripts/mine_local_articles.py` |
| KGマイニングクエリ | `references/kg-topic-mining.md` |
| own_article 専用クエリ | `references/kg-own-article-mining.md`（Phase 2 完了後） |
| スコアリングルーブリック | `references/scoring-rubric.md` |
| 旧スコア基準 | `references/scoring_criteria.md` |
| トピック提案エージェント | `.claude/agents/topic-suggester.md` |
