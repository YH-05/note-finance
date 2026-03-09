# 議論メモ: 体験談DBフルパイプライン実装

**日付**: 2026-03-09
**参加**: ユーザー + AI
**ステータス**: 実装完了（E2Eテスト未実施）

## 背景・コンテキスト

体験談DB（合成パターン法）の記事作成を、ソース収集から公開準備までを一貫して実行できるワークフローとして実装。
既存の finance-full コマンド（3Phase）と asset-management ワークフロー（4Phase）のパターンを参考に、体験談DB固有の合成・匿名化ステップを含む6Phase構成を設計。

## 決定事項

### 1. テンプレート構造（dec-2026-03-09-004）

`template/experience_db/` に記事フォルダテンプレートを作成:

```
template/experience_db/
├── article-meta.json          ← 6Phaseワークフロー管理 + Neo4j紐付け
├── 01_sources/                ← Phase 1: ソース収集
│   ├── reddit.json
│   ├── rss.json
│   ├── web_search.json
│   └── note_com.json
├── 02_synthesis/              ← Phase 2: 合成パターン生成
│   └── synthesis.json
├── 03_edit/                   ← Phase 3-5: 執筆→批評→修正
│   ├── first_draft.md
│   ├── critic.json
│   └── revised_draft.md
└── 04_published/              ← Phase 6: 公開
    └── YYYYMMDD_pattern-name-en.md
```

### 2. ExperienceSource ノード — B案採用（dec-2026-03-09-005）

体験談ソースを専用の `ExperienceSource` ノードとして保存。既存の `Source` ノード（金融ニュース用）とは分離。

**選定理由**: A案（既存Source拡張）は金融ニュースSourceと体験談Sourceの混在が問題。B案は専用ノードで明確に分離しクエリも書きやすい。

**スキーマ**:

```
ExperienceSource
  properties:
    source_id (exsrc-{type}-{id}), source_type (reddit|rss|web_search|note_com),
    theme, title, url, content_preview, relevance_score, selected, collected_at,
    age_range, gender, duration, outcome,
    subreddit, score, num_comments,  // reddit のみ
    feed_name,                        // rss のみ
    hashtag,                          // note_com のみ
    query                             // web_search のみ
```

**リレーション**:

```
(ExperiencePattern)-[:SYNTHESIZED_FROM {contribution}]->(ExperienceSource)
```

### 3. 6Phaseパイプライン構成（dec-2026-03-09-006）

| Phase | 内容 | 実行者 |
|-------|------|--------|
| 1 | ソース収集（Reddit + RSS + Web検索 + note.com） | collect-experience-stories |
| 2 | 合成パターン生成（5-10件→1パターン） | experience-synthesizer |
| 3 | 記事執筆（テンプレートv2, 6000-8000字） | experience-writer |
| 4 | 4エージェント並列批評 | experience-db-critique |
| 5 | 批評反映・修正 | experience-reviser |
| 6 | Neo4j保存（ExperienceSource + ExperiencePattern + EmbeddableResource） | experience-db-workflow |

HFゲート: Phase 1 後（ソース確認）、Phase 4 後（批評結果確認）の2箇所。

## 実施結果

### 完了タスク

- [x] **テンプレート作成** (act-2026-03-09-007)
  - `template/experience_db/` 配下に10ファイル作成
  - article-meta.json に6Phaseワークフロー管理 + Neo4j紐付け（source_node_ids追加）

- [x] **3エージェント作成** (act-2026-03-09-008)
  - `.claude/agents/experience-synthesizer.md` — 5-10件のソースから合成パターン生成（匿名化・帯域化）
  - `.claude/agents/experience-writer.md` — 合成パターンから初稿執筆（6,000-8,000字、テンプレートv2準拠）
  - `.claude/agents/experience-reviser.md` — 批評結果反映、4観点の修正優先順位に従う

- [x] **スキル＋コマンド作成** (act-2026-03-09-009)
  - `.claude/skills/experience-db-workflow/SKILL.md` — 6Phaseオーケストレーション
  - `.claude/commands/experience-db-full.md` — ユーザー向けエントリーポイント

### 未着手タスク

- [ ] **E2Eテスト** (act-2026-03-09-010) — 1テーマで全6Phase通し実行
- [ ] **collect-experience-stories にWeb検索追加** (act-2026-03-09-011)

## Neo4jグラフ構造（更新後）

```
(Memory:project {name: '副業プロジェクト'})
  -[:HAS_PATTERN]-> (ExperiencePattern)
    -[:BELONGS_TO]-> (CandidateTheme)
    -[:EMBEDS {section}]-> (EmbeddableResource)
    -[:SYNTHESIZED_FROM {contribution}]-> (ExperienceSource)  ← NEW

(Memory:project)
  -[:HAS_DISCUSSION]-> (Discussion: disc-2026-03-09-experience-db-pipeline)
    -[:RESULTED_IN]-> (Decision) x3
    -[:PRODUCED]-> (ActionItem) x5
```

## JSON → Neo4j 対応表

| ローカルファイル | Neo4j ノード | 保存タイミング |
|-----------------|-------------|--------------|
| 01_sources/*.json の selected stories | ExperienceSource | Phase 6 |
| 02_synthesis/synthesis.json | ExperiencePattern + SYNTHESIZED_FROM | Phase 6 |
| 02_synthesis/synthesis.json の embed_candidates | EmbeddableResource + EMBEDS | Phase 6 |
| article-meta.json | neo4j.source_node_ids 等を更新 | Phase 6 |

## 成果物一覧

| ファイル | 内容 |
|---------|------|
| `template/experience_db/` (10ファイル) | 記事フォルダテンプレート |
| `.claude/agents/experience-synthesizer.md` | 合成エージェント |
| `.claude/agents/experience-writer.md` | 執筆エージェント |
| `.claude/agents/experience-reviser.md` | 修正エージェント |
| `.claude/skills/experience-db-workflow/SKILL.md` | ワークフロースキル |
| `.claude/commands/experience-db-full.md` | フルパイプラインコマンド |

## 次回の議論トピック

- E2Eテスト結果のレビュー
- ExperienceSourceノードのインデックス設計（source_id, theme でのインデックス）
- 複数パターンで同じソースを共有する場合のリレーション設計
- noteアカウント設計（プロフィール、マガジン構成）への着手判断

## 参照

- テンプレートv2: `体験談DB統一テンプレート_v2.md`
- 批評スキル: `.claude/skills/experience-db-critique/SKILL.md`
- ソース検証: `2026-03-09_db-experience-source-verification.md`
- 試作フィードバック: `2026-03-09_prototype-feedback.md`
- Neo4jスキーマ設計: `2026-03-09_neo4j-schema-design.md`

## Neo4j保存先

- Discussion: `disc-2026-03-09-experience-db-pipeline`
- Decision: `dec-2026-03-09-004`, `dec-2026-03-09-005`, `dec-2026-03-09-006`
- ActionItem: `act-2026-03-09-007` 〜 `act-2026-03-09-011`
