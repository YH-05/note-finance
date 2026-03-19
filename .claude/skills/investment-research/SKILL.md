---
name: investment-research
description: |
  特定の投資テーマについてマルチソースで深掘りリサーチし、記事素材を集めるスキル。
  research-neo4jから既存データを照会し、情報ギャップを特定した上で、
  Web検索・RSS・Reddit・SEC Edgarを組み合わせたファクト収集と論点抽出を行う。
  検索結果はresearch-neo4jに永続化する。
  Use PROACTIVELY when 投資テーマのリサーチ、銘柄分析、マクロ経済調査が必要な場合。
allowed-tools: Read, Write, Bash, Glob, Grep, ToolSearch
---

# investment-research スキル

特定の投資テーマについてマルチソースで深掘りリサーチし、記事素材を集めるスキル。

## パラメータ

| パラメータ | 必須 | デフォルト | 説明 |
|-----------|------|-----------|------|
| --theme | 必須 | - | リサーチテーマ（例: "NVIDIA AI需要", "日銀利上げ影響", "新NISA投資動向"） |
| --depth | - | standard | 調査深度。quick: 5-8検索, standard: 12-18検索, deep: 20-30検索 |
| --language | - | both | 検索言語。en: 英語のみ, ja: 日本語のみ, both: 両方 |
| --skip-kg | - | false | KG照会・永続化をスキップする（Neo4j未起動時に使用） |

## 処理フロー概要

```
Phase 0: KG既存データ照会 + ギャップ分析
Phase 1: マルチソース検索（ギャップ優先）
Phase 2: ファクト整理
Phase 3: 論点抽出
Phase 4: リサーチノート出力
Phase 5: KG永続化（検索結果をresearch-neo4jに保存）
```

### Phase 0: KG既存データ照会 + ギャップ分析

参照: `references/kg-gap-analysis.md`（Cypherクエリテンプレート・ギャップ判定ロジック）

research-neo4j（bolt://localhost:7688）から既存データを照会し、情報ギャップを特定する。
`mcp__neo4j-research__research-read_neo4j_cypher` を ToolSearch でロードして使用する。

#### Phase 0-A: 既存データ照会

テーマからキーワードを抽出し、以下を照会する:

1. **関連Entity**: テーマに関連する企業・指標・セクター等（Q1）
2. **関連Topic**: テーマに紐づくTopicノード（Q2）
3. **ソース鮮度**: 最新ソースの公開日（Q3）
4. **既存Fact**: 関連エンティティの時系列ファクト（Q4）
5. **Claimセンチメント分布**: bullish/bearish/neutralの偏り（Q5）
6. **未回答Question**: 過去に特定された未解決ギャップ（Q6）

キーワード抽出の例:
- "日銀利上げ影響" → `["日銀", "BOJ", "利上げ", "金利"]`
- "NVIDIA AI需要" → `["NVIDIA", "AI", "GPU", "データセンター"]`
- "新NISA投資動向" → `["NISA", "投資信託", "積立"]`

#### Phase 0-B: ギャップ分析

照会結果から5つの観点でギャップを判定する:

| ギャップ種別 | 判定条件 | 優先度 |
|------------|---------|--------|
| stale_data | 最新ソース published_at < today - 30d | HIGH |
| missing_bear_case | bullish > 0 AND bearish == 0 | MEDIUM |
| missing_bull_case | bearish > 0 AND bullish == 0 | MEDIUM |
| no_coverage | 記事に必要なエンティティの fact/claim が0件 | HIGH |
| open_questions | 未回答 Question ノードが存在 | HIGH/MEDIUM |
| missing_financials | company/etf/index の FinancialDataPoint が0件 | MEDIUM |

#### Phase 0-C: ギャップレポート出力

分析結果を `01_research/kg_gap_report.md` に出力する。
このレポートには既存データサマリー、特定されたギャップ一覧、推奨検索クエリが含まれる。

### Phase 1: マルチソース検索（ギャップ優先）

参照: `references/search-strategy.md`（テーマ種別ごとのソース優先順位）
参照: `.claude/skills/web-search/SKILL.md`（Web検索ツール選択基準）

Phase 0 で特定されたギャップに基づき、検索クエリの優先順位を調整する。

#### 検索予算の配分

```
深度別 総検索回数:
  quick:    5-8回   → ギャップ解消: 3-5回, 通常リサーチ: 2-3回
  standard: 12-18回 → ギャップ解消: 6-10回, 通常リサーチ: 6-8回
  deep:     20-30回 → ギャップ解消: 10-15回, 通常リサーチ: 10-15回
```

#### ギャップ解消検索の優先順位

1. **stale_data** → 最新ニュース・レポートを重点検索
2. **no_coverage** → 該当エンティティ名で集中検索
3. **open_questions** → Question.content をクエリとして使用
4. **missing_bear_case / missing_bull_case** → 反対意見の検索クエリ追加
5. **missing_financials** → SEC Edgar / 決算データ検索

#### ソース

1. **Web検索**: 最新ニュース・分析記事を検索（ツール選択は web-search スキル参照）
   - 日本語テーマ → Gemini Search 推奨
   - 英語テーマ → Tavily MCP 推奨
   - `.claude/resources/search-templates/` のテンプレートを活用
2. **RSS MCP** (`mcp__rss__rss_search_items`): 登録済みフィードからテーマ関連記事を検索
   - ToolSearch でロード、利用不可時はスキップ
3. **Reddit MCP** (`mcp__reddit__*`): 投資家コミュニティの議論を収集
   - r/investing, r/stocks, r/wallstreetbets 等
   - ToolSearch でロード、利用不可時はスキップ
4. **SEC Edgar MCP** (`mcp__sec-edgar-mcp__*`): 個別銘柄テーマ時にSEC filingを参照
   - ToolSearch でロード、利用不可時はスキップ

### Phase 2: ファクト整理

参照: `references/source-reliability.md`（ソース信頼度）

1. 収集した情報を時系列で整理
2. 数値データ（株価、業績、経済指標等）を抽出
3. 専門家見解・アナリストコメントを分類
4. 各ファクトにソース信頼度（Tier 1-4）を付与
5. **KG既存ファクトとの重複チェック**: Phase 0で取得済みのファクトと重複する情報を除外

### Phase 3: 論点抽出

1. **ブル（強気）要因**: テーマに対するポジティブな見方・根拠
2. **ベア（弱気）要因**: テーマに対するネガティブな見方・根拠
3. **ニュートラル**: 中立的な視点・不確実性要因
4. 各論点にエビデンス（ソース付き）を紐づけ
5. **ギャップ解消の確認**: Phase 0で特定されたギャップが解消されたかを記録

### Phase 4: リサーチノート出力

参照: `references/output-format.md`（出力テンプレート）

`.tmp/investment-research/{theme_slug}_{YYYYMMDD-HHMM}.md` にリサーチノートを出力。

リサーチノートには以下のセクションを追加:

```markdown
## KGギャップ分析結果
- 特定されたギャップ: {n}件
- 解消されたギャップ: {n}件
- 残存ギャップ: {n}件（次回リサーチで対応推奨）
```

### Phase 5: KG永続化

参照: `references/kg-gap-analysis.md`（Phase 5 セクション）
参照: `.claude/rules/neo4j-write-rules.md`（直書き禁止ルール）

Phase 1-3 で収集した検索結果を research-neo4j に永続化する。

#### ステップ 5-1: 入力JSON構築

検索結果から `emit_graph_queue.py --command web-research` の入力JSONを構築する。

```json
{
  "session_id": "article-research-{slug}-{YYYYMMDD-HHMM}",
  "research_topic": "{テーマ}",
  "as_of_date": "{today}",
  "sources": [...],
  "entities": [...],
  "topics": [...],
  "facts": [...]
}
```

各フィールドのスキーマは `.claude/skills/emit-research-queue/SKILL.md` を参照。

**必須チェック項目**:
- 全ソースに `authority_level` が設定されているか
- 全ファクトの `source_url` が `sources` 内の URL と一致するか

#### ステップ 5-2: graph-queue JSON 生成

```bash
uv run python scripts/emit_graph_queue.py \
  --command web-research \
  --input .tmp/research-input/{session_id}.json
```

#### ステップ 5-3: Neo4j 投入

`/save-to-graph` スキルを呼び出して graph-queue JSON を Neo4j に投入する。

#### ステップ 5-4: 投入結果の記録

投入結果を `01_research/kg_ingestion_report.md` に記録する:

```markdown
# KG投入レポート

## セッション: {session_id}
## 投入日時: {datetime}

## 投入結果
- Source ノード: {n}件
- Entity ノード: {n}件
- Topic ノード: {n}件
- Fact ノード: {n}件
- リレーション: {n}件

## ギャップ解消状況
- 解消済み: {list}
- 残存: {list}
```

## MCP フォールバック戦略

参照: `.claude/skills/web-search/SKILL.md`（フォールバック戦略）

MCPツールは ToolSearch でロードを試みる。利用不可の場合:
- Neo4j MCP → Phase 0/5 をスキップ（`--skip-kg` と同等）、警告を出力
- RSS MCP → Web検索で代替（フィードURLを直接検索）
- Reddit MCP → Web検索で `site:reddit.com` クエリ
- SEC Edgar MCP → Web検索で `site:sec.gov` クエリ

深度別の最低検索回数:
- quick: 5回以上
- standard: 10回以上
- deep: 15回以上

## 関連ファイル

| リソース | パス |
|---------|------|
| KGギャップ分析 | `references/kg-gap-analysis.md` |
| 検索戦略 | `references/search-strategy.md` |
| ソース信頼度 | `references/source-reliability.md` |
| 調査深度基準 | `references/research-depth-criteria.md` |
| 出力フォーマット | `references/output-format.md` |
| emit-research-queue | `.claude/skills/emit-research-queue/SKILL.md` |
| save-to-graph | `.claude/skills/save-to-graph/SKILL.md` |
| Neo4j直書き禁止ルール | `.claude/rules/neo4j-write-rules.md` |
| KGスキーマ定義 | `data/config/knowledge-graph-schema.yaml` |
