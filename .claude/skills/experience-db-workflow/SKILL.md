---
name: experience-db-workflow
description: 体験談DB記事の全工程ワークフロー。ソース収集→合成→執筆→批評→修正→Neo4j保存の6Phaseを制御する。
allowed-tools: Read, Write, Edit, Bash, Glob, Grep, Agent, ToolSearch
---

# Experience DB Workflow Skill

体験談DB（合成パターン法）の記事作成フルパイプライン。
6 Phase で体験談ソース収集から記事公開準備までを一貫実行する。

## いつ使用するか

- `/experience-db-full` コマンド実行時
- 体験談DB記事の作成を依頼された時

## 処理フロー

```
Phase 1: ソース収集
├── Reddit MCP（テーマ別サブレディット）
├── RSS MCP（Google News体験談フィード）
├── Web検索（Tavily / Gemini）
└── note.com Chrome巡回（オプション）
↓
[HF1] ソース確認・選定
↓
Phase 2: 合成パターン生成
├── experience-synthesizer エージェント
├── 共通パターン抽出
├── 匿名化・帯域化
└── 埋め込みリソース候補
↓
Phase 3: 記事執筆
├── experience-writer エージェント
├── テンプレートv2準拠（6,000-8,000字）
└── 埋め込みリンク配置
↓
Phase 4: 4エージェント並列批評
├── experience-db-critique スキル
├── リアリティ(30%) + 共感度(30%) + 埋め込み(15%) + バランス(25%)
└── 統合スコア算出
↓
[HF2] 批評結果確認
↓
Phase 5: 批評反映・修正
├── experience-reviser エージェント
├── critical/high 問題を優先修正
└── revised_draft.md 生成
↓
Phase 6: Neo4j保存 + 完了
├── ExperiencePattern ノード MERGE
├── EmbeddableResource ノード MERGE
├── リレーション設定
└── meta.yaml ステータス更新
```

## Phase 1: ソース収集

### 1.1 記事フォルダ作成

`template/experience_db/` をコピーして記事フォルダを作成:

```
articles/{category}/{YYYY-MM-DD}_{english-slug}/
├── meta.yaml
├── 01_research/
├── 02_draft/
└── 03_published/
```

カテゴリ対応: konkatsu -> `marriage/`, sidehustle -> `side_business/`, shisan -> `asset_management/`

meta.yaml の `theme`, `created_at` を設定。

### 1.2 Reddit 収集

テーマ別サブレディットから体験談を収集。

| テーマ | サブレディット（優先順） |
|--------|----------------------|
| konkatsu | r/hingeapp, r/OnlineDating, r/dating_advice, r/Bumble, r/Tinder |
| sidehustle | r/sidehustle, r/freelance, r/WorkOnline, r/Entrepreneur, r/beermoney |
| shisan | r/Bogleheads, r/personalfinance, r/financialindependence, r/investing, r/stocks |

各サブレディットに対して `mcp__reddit__get_subreddit_new_posts` を実行。
体験談フィルタリング: タイトルに experience/story/journey/update/finally/success/failed を含むもの。
結果を `01_sources/reddit.json` に保存。

### 1.3 RSS 収集

`mcp__rss__rss_search_items` で `experience-db-{theme}` カテゴリのフィードを検索。
結果を `01_sources/rss.json` に保存。

### 1.4 Web検索

`mcp__tavily__tavily_search` または `gemini --prompt "WebSearch: ..."` で体験談を検索。

検索クエリ例:
- konkatsu: 「婚活 体験談 成功」「マッチングアプリ 成婚 ブログ」
- sidehustle: 「副業 体験談 月収」「Webライター 未経験 体験」
- shisan: 「つみたてNISA 運用報告」「投資 暴落 体験」

結果を `01_sources/web_search.json` に保存。

### 1.5 note.com 巡回（オプション）

Chrome自動化でハッシュタグページを巡回。
`mcp__claude-in-chrome__navigate` → `mcp__claude-in-chrome__get_page_text`。
結果を `01_sources/note_com.json` に保存。

### 1.6 [HF1] ソース確認

収集結果のサマリーを表示し、ユーザーに確認:

```
## ソース収集結果

| ソース | 取得件数 | フィルタ通過 |
|--------|---------|------------|
| Reddit | XX件 | XX件 |
| RSS | XX件 | XX件 |
| Web検索 | XX件 | XX件 |
| note.com | XX件 | XX件 |
| **合計** | **XX件** | **XX件** |

合成に使用するソースを選定してよいですか？
```

## Phase 2: 合成パターン生成

`experience-synthesizer` エージェントを起動:

```yaml
subagent_type: "experience-synthesizer"
description: "体験談合成パターン生成"
prompt: |
  以下のソースデータから合成パターンを生成してください。

  ## テーマ
  {theme}

  ## ソースデータ
  {01_sources/ の全JSONの内容}

  ## 出力先
  {article_folder}/02_synthesis/synthesis.json
```

## Phase 3: 記事執筆

**品質ルール**: 参照 `.claude/rules/article-quality-standards.md`
- マークダウン表は `/generate-table-image` で画像化
- 数値データにはソースURLリンクを埋め込み
- データ可視化が必要な場合は `/generate-chart-image` でチャート画像を生成

`experience-writer` エージェントを起動:

```yaml
subagent_type: "experience-writer"
description: "体験談DB記事執筆"
prompt: |
  合成パターンから記事の初稿を生成してください。

  ## テーマ
  {theme}

  ## 合成パターン
  {02_synthesis/synthesis.json の内容}

  ## テンプレート参照
  docs/plan/SideBusiness/体験談DB統一テンプレート_v2.md

  ## 出力先
  {article_folder}/03_edit/first_draft.md
```

## Phase 4: 4エージェント並列批評

`experience-db-critique` スキルを呼び出す:

```
/experience-db-critique {article_folder}/03_edit/first_draft.md
```

結果は `03_edit/critic.json` に保存される。

## Phase 5: 批評反映・修正

### 5.1 [HF2] 批評結果確認

```
## 批評結果

| 観点 | スコア | グレード |
|------|--------|---------|
| リアリティ | XX/100 | X |
| 共感度 | XX/100 | X |
| 埋め込みリンク | XX/100 | X |
| 文字量バランス | XX/100 | X |
| **総合** | **XX/100** | **X** |

修正版を生成しますか？
```

### 5.2 修正実行

`experience-reviser` エージェントを起動:

```yaml
subagent_type: "experience-reviser"
description: "体験談DB記事修正"
prompt: |
  批評結果を反映して記事を修正してください。

  ## 初稿
  {03_edit/first_draft.md の内容}

  ## 批評結果
  {03_edit/critic.json の内容}

  ## 合成パターン（参照用）
  {02_synthesis/synthesis.json の内容}

  ## 出力先
  {article_folder}/03_edit/revised_draft.md
```

## Phase 6: Neo4j保存 + 完了

### 6.1 ExperienceSource ノード作成

01_sources/ の各JSONから、`selected: true` のソースを `ExperienceSource` ノードとして保存。

```cypher
// ExperienceSource ノード（ソースごとに1件）
MERGE (es:ExperienceSource {source_id: $source_id})
SET es.source_type = $source_type,
    es.theme = $theme,
    es.title = $title,
    es.url = $url,
    es.content_preview = $content_preview,
    es.relevance_score = $relevance_score,
    es.selected = $selected,
    es.collected_at = datetime($collected_at),
    es.age_range = $age_range,
    es.gender = $gender,
    es.duration = $duration,
    es.outcome = $outcome
// source_type 別の追加プロパティ
SET es.subreddit = $subreddit,       // reddit のみ
    es.score = $score,               // reddit のみ
    es.num_comments = $num_comments, // reddit のみ
    es.feed_name = $feed_name,       // rss のみ
    es.hashtag = $hashtag,           // note_com のみ
    es.query = $query                // web_search のみ
```

**source_id 命名規則**:

| source_type | ID形式 | 例 |
|-------------|--------|-----|
| reddit | `exsrc-reddit-{post_id}` | `exsrc-reddit-abc123` |
| rss | `exsrc-rss-{item_id}` | `exsrc-rss-60af4cc3` |
| web_search | `exsrc-web-{url_hash[:8]}` | `exsrc-web-a1b2c3d4` |
| note_com | `exsrc-note-{url_hash[:8]}` | `exsrc-note-e5f6g7h8` |

### 6.2 ExperiencePattern ノード作成

```cypher
// ExperiencePattern ノード
MERGE (ep:ExperiencePattern {pattern_id: $pattern_id})
SET ep.theme = $theme,
    ep.title = $title,
    ep.wordcount_target = 7000,
    ep.wordcount_current = $wordcount,
    ep.status = 'revised',
    ep.created_at = datetime(),
    ep.article_folder = $article_folder

// プロジェクトとの接続
MATCH (p:Memory:project {name: '副業プロジェクト'})
MERGE (p)-[:HAS_PATTERN]->(ep)

// テーマとの接続
MATCH (ct:CandidateTheme {theme_key: $theme})
MERGE (ep)-[:BELONGS_TO]->(ct)
```

### 6.3 SYNTHESIZED_FROM リレーション

ExperiencePattern と ExperienceSource を接続:

```cypher
// 合成に使用したソースとの接続
MATCH (ep:ExperiencePattern {pattern_id: $pattern_id})
MATCH (es:ExperienceSource {source_id: $source_id})
MERGE (ep)-[:SYNTHESIZED_FROM {contribution: $contribution}]->(es)
```

`contribution` は synthesis.json の `selected_sources[].contribution` の値。

### 6.4 EmbeddableResource ノード作成

synthesis.json の `embed_candidates` から:

```cypher
MERGE (er:EmbeddableResource {resource_id: $resource_id})
SET er.resource_type = $resource_type,
    er.url = $url,
    er.title = $title,
    er.embed_section = $section,
    er.experience_context = $context

MATCH (ep:ExperiencePattern {pattern_id: $pattern_id})
MERGE (ep)-[:EMBEDS {section: $section}]->(er)
```

### 6.5 meta.yaml 更新

```json
{
  "status": "revised",
  "workflow": {
    "publishing": {
      "neo4j_saved": "done"
    }
  },
  "neo4j": {
    "pattern_node_id": "exp-{theme}-{NNN}",
    "source_node_ids": ["exsrc-reddit-abc123", "exsrc-rss-60af4cc3"],
    "embed_resource_ids": ["res-xxx-001", "res-xxx-002"]
  }
}
```

## 完了報告

```
================================================================================
              体験談DB記事作成 完了
================================================================================

## 記事情報
- パターンID: {pattern_id}
- テーマ: {theme_label}
- タイトル: {pattern_name}
- 文字数: {wordcount}字

## 批評スコア
| 観点 | スコア |
|------|--------|
| リアリティ | {score}/100 |
| 共感度 | {score}/100 |
| 埋め込みリンク | {score}/100 |
| 文字量バランス | {score}/100 |
| **総合** | **{score}/100** |

## 生成ファイル
- 01_sources/: ソースデータ（Reddit, RSS, Web検索, note.com）
- 02_synthesis/synthesis.json: 合成パターン
- 03_edit/first_draft.md: 初稿
- 03_edit/critic.json: 批評結果
- 03_edit/revised_draft.md: 改訂版

## Neo4j
- ExperienceSource: {source_count}件
- ExperiencePattern: {pattern_id}
- EmbeddableResource: {resource_ids}
- SYNTHESIZED_FROM: {source_count}件

## 次のステップ
1. revised_draft.md を最終確認
2. /publish-to-note で下書き投稿
================================================================================
```

## エラーハンドリング

| フェーズ | エラー | 対処 |
|---------|--------|------|
| Phase 1 | Reddit MCP 接続失敗 | RSS + Web検索のみで続行 |
| Phase 1 | ソース0件 | エラー終了、検索クエリ変更を推奨 |
| Phase 2 | ソース不足（3件未満） | 警告付きで続行 or 追加収集 |
| Phase 3 | 文字数不足 | 肉付け再実行 |
| Phase 4 | 批評エージェント失敗 | 成功したエージェントのみで統合 |
| Phase 5 | critical問題多すぎ | 初稿再生成を推奨 |
| Phase 6 | Neo4j 接続失敗 | 警告表示、ローカル保存のみで完了 |

## 関連リソース

| リソース | パス |
|---------|------|
| テンプレート | `template/experience_db/` |
| テンプレートv2 | `docs/plan/SideBusiness/体験談DB統一テンプレート_v2.md` |
| 批評スキル | `.claude/skills/experience-db-critique/SKILL.md` |
| 批評基準 | `.claude/resources/experience-db-criteria/` |
| ソース検証 | `docs/plan/SideBusiness/2026-03-09_db-experience-source-verification.md` |
| 匿名化戦略 | `docs/plan/SideBusiness/2026-03-09_anonymization-strategy.md` |
| ソース収集コマンド | `.claude/commands/collect-experience-stories.md` |
