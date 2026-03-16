# note記事執筆ワークフロー統一化リファクタリング

## Context

articles/配下のフォルダ構成が5パターン混在し、コマンド体系も分断されている。
全カテゴリを統一フォルダ構成・統一コマンド体系・統一メタデータ（meta.yaml）に再設計し、
既存12本の記事をマイグレーションする。

**課題**:
- フォルダ構成が `{category}_{seq}_{theme}/`, `asset_management/{slug}/`, `exp-{theme}-{seq}/`, `weekly_report/{date}/` の4+パターン混在
- `/new-finance-article`, `/finance-edit`, `/finance-full`, `/asset-management`, `/experience-db-full` が個別に存在し統一されていない
- article-meta.json のスキーマがカテゴリごとに異なる
- template/ のサブフォルダ構成もカテゴリごとに不統一

---

## 1. 新フォルダ構成

### 1.1 ディレクトリ階層

```
articles/
  {category}/
    {YYYY-MM-DD}_{topic-slug}/
      meta.yaml
      01_research/
      02_draft/
      03_published/
```

### 1.2 カテゴリ一覧

| 新カテゴリ | 旧カテゴリ | 説明 |
|-----------|-----------|------|
| `asset_formation` | `asset_management` + `investment_education` | 資産形成・NISA・初心者向け |
| `side_business` | `experience_db` | 副業・体験談・事例分析 |
| `macro_economy` | `economic_indicators` | マクロ経済・経済指標 |
| `stock_analysis` | `stock_analysis` | 個別銘柄分析 |
| `weekly_report` | `market_report` + `weekly_report` | 週次レポート |
| `quant_analysis` | `quant_analysis` | クオンツ分析 |

### 1.3 統一サブフォルダ

全カテゴリ共通（旧 `02_edit/` → `02_draft/` にリネーム）:

```
{YYYY-MM-DD}_{topic-slug}/
  meta.yaml                # メタデータ（article-meta.json を置換）
  01_research/             # リサーチ素材（カテゴリ固有ファイルあり）
  02_draft/                # ドラフト
    first_draft.md
    critic.json
    critic.md
    revised_draft.md
  03_published/            # 公開版
    article.md
```

### 1.4 カテゴリ固有の 01_research/ ファイル

**stock_analysis / macro_economy / quant_analysis:**
```
01_research/
  queries.json, raw-data.json, sources.json, claims.json,
  analysis.json, decisions.json, fact-checks.json, market_data/data.json
```

**asset_formation:**
```
01_research/
  sources.json, session.json, x_post.md
```

**side_business:**
```
01_research/
  sources.json              # 全ソース統合（旧 reddit.json, rss.json 等）
  synthesis.json            # 合成パターン（旧 02_synthesis/）
  embed_resources.json
```

**weekly_report:**
```
01_research/
  sources.json, market/{indices,mag7,sectors}.json, metadata.json
```

---

## 2. meta.yaml スキーマ

```yaml
# === Core (必須) ===
title: "記事タイトル"
category: asset_formation      # 6カテゴリから選択
type: column                   # column | case_study | experience | weekly_report | data_analysis
status: draft                  # draft | review | published

# === Timestamps ===
created_at: "2026-03-08"
updated_at: "2026-03-08"

# === Content ===
tags: [NISA, 投資初心者]
target_audience: beginner      # beginner | intermediate | advanced
target_wordcount: 4000

# === Category-Specific (該当カテゴリのみ) ===
symbols: []                    # stock_analysis / quant_analysis
date_range: {start: "", end: ""}
fred_series: []                # macro_economy
theme: ""                      # asset_formation / side_business
experience:                    # side_business (experience type)
  spec_card: {age_range: "", gender: "", occupation: "", income_range: "", duration: "", outcome: ""}

# === Tracking ===
critic_score: null
revision_count: 0
note_url: null
x_post_url: null
research_sources: 0

# === Workflow ===
workflow:
  research: pending            # pending | in_progress | done | skipped
  draft: pending
  critique: pending
  revision: pending
  publish: pending

# === Neo4j (side_business only) ===
neo4j:
  pattern_node_id: null
  source_node_ids: []
  embed_resource_ids: []

# === Legacy ===
legacy:
  old_path: null
  old_article_id: null
  migrated_at: null
```

---

## 3. 新コマンド体系

### 3.1 5フェーズコマンド

| Phase | コマンド | 説明 | 置換対象 |
|-------|---------|------|---------|
| 1 | `/article-init [topic]` | フォルダ作成 + meta.yaml | `/new-finance-article` |
| 2 | `/article-research @dir` | リサーチ実行 | `/finance-full` Phase 2 部分 |
| 3 | `/article-draft @dir` | ドラフト作成 | `/finance-edit` Step 1 |
| 4 | `/article-critique @dir [--mode quick\|full]` | 批評・修正 | `/finance-edit` Steps 2-3 |
| 5 | `/article-publish @dir [--dry-run]` | note投稿 | `/publish-to-note` |

### 3.2 オーケストレーション

| コマンド | 説明 | 置換対象 |
|---------|------|---------|
| `/article-full [topic]` | 全5フェーズ一括 | `/finance-full`, `/asset-management`, `/experience-db-full` |
| `/article-status` | 記事ステータス一覧 | `/finance-suggest-topics` Phase 1 |

### 3.3 各コマンドのカテゴリ別ディスパッチ

各コマンドは meta.yaml の `category` と `type` を読み、適切なスキル/エージェントに振り分ける:

- **research**: investment-research / asset-management-workflow Phase1 / experience-db-workflow Phase1-2 / generate-market-report Phase2-3
- **draft**: finance-article-writer / asset-management-writer / experience-writer / weekly-report-lead
- **critique**: finance-critic-* / case-study-critique / experience-db-critique / weekly-report-validation
- **publish**: publish-to-note (共通)

### 3.4 廃止計画

旧コマンドは薄いリダイレクト（deprecation notice 付き）として1リリースサイクル残す:
- `/new-finance-article` → `/article-init`
- `/finance-edit` → `/article-draft` + `/article-critique`
- `/finance-full` → `/article-full`
- `/asset-management` → `/article-full --category asset_formation`
- `/experience-db-full` → `/article-full --category side_business --type experience`
- `/publish-to-note` → `/article-publish`

---

## 4. テンプレート統一

### 4.1 新構成

```
template/
  _common/                  # 全カテゴリ共通（新規作成）
    meta.yaml
    02_draft/
      first_draft.md, critic.json, critic.md, revised_draft.md
    03_published/
      article.md
  asset_formation/          # 旧 asset_management + investment_education
    01_research/
  side_business/            # 旧 experience_db（新規作成）
    01_research/
  macro_economy/            # 旧 economic_indicators
    01_research/
  stock_analysis/
    01_research/
  weekly_report/            # 旧 market_report
    01_research/
  quant_analysis/
    01_research/
```

### 4.2 初期化ロジック

1. `template/_common/` をコピー
2. `template/{category}/` をオーバーレイ（マージ）
3. meta.yaml にカテゴリ固有デフォルトを注入

---

## 5. 既存記事マイグレーション

### 5.1 マイグレーションマッピング（12本）

| # | 旧パス | 新パス | 変換内容 |
|---|--------|--------|---------|
| 1 | `economic_indicators_001_private-credit-...` | `macro_economy/2026-03-07_private-credit-shadow-banking/` | カテゴリ変更, 02_edit→02_draft |
| 2 | `economic_indicators_002_boj-rate-hike-...` | `macro_economy/2026-03-08_boj-rate-hike-yen-scenario/` | 同上 |
| 3 | `economic_indicators_003_oil-150-shock-...` | `macro_economy/2026-03-09_oil-150-shock-stagflation/` | 同上 |
| 4 | `stock_analysis_001_tech-to-high-dividend-...` | `stock_analysis/2026-03-08_tech-to-high-dividend-vz/` | 02_edit→02_draft |
| 5 | `stock_analysis_002_blackrock-...` | `stock_analysis/2026-03-08_blackrock-private-credit/` | フラット→構造化 |
| 6 | `asset_management/fund_selection_age_based/` | `asset_formation/2026-03-08_fund-selection-age-based/` | カテゴリ変更, 01_research/03_published追加 |
| 7 | `asset_management/index-investing-...` | `asset_formation/2026-03-06_index-investing-portfolio/` | 同上 |
| 8 | `asset_management/index_vs_etf_2026/` | `asset_formation/2026-03-08_index-vs-etf-2026/` | フラット→構造化 |
| 9 | `exp-sidehustle-002-skill-freelance/` | `side_business/2026-03-09_video-editing-freelance/` | 01_sources→01_research, 02_synthesis統合, 03_edit→02_draft, 04_published→03_published |
| 10 | `exp-sidehustle-003-pending/` | `side_business/2026-03-09_sidehustle-003-pending/` | 同上 |
| 11 | `weekly_report/2026-02-23/` | `weekly_report/2026-02-23_weekly-market-report/` | data→01_research/market, 02_edit→02_draft |
| 12 | `investor_memo_conversion/` | SKIP（記事ではない） | - |

### 5.2 マイグレーションスクリプト

`scripts/migrate_articles.py` を新規作成:
- `--dry-run`: プレビューモード
- `--article <old_path>`: 単一記事のみ
- article-meta.json → meta.yaml 変換
- status マッピング: research/edit/collecting→draft, revised/ready_for_publish→review, published→published
- legacy フィールドに旧パス記録

---

## 6. 影響範囲と変更ファイル

### 6.1 コマンド（`.claude/commands/`）

| ファイル | アクション |
|---------|----------|
| `new-finance-article.md` | → `article-init.md` にリライト |
| `finance-edit.md` | → `article-draft.md` + `article-critique.md` に分割 |
| `finance-full.md` | → `article-full.md` にリライト |
| `publish-to-note.md` | → `article-publish.md` にリライト |
| `asset-management.md` | → deprecation redirect |
| `finance-suggest-topics.md` | → パス更新 + `article-status.md` 新規作成 |

### 6.2 スキル（`.claude/skills/`）

| スキル | 変更内容 |
|--------|---------|
| `finance-topic-suggestion/` | articles/ スキャンパス更新 |
| `finance-topic-suggestion/scripts/analyze_existing_articles.py` | ネスト構造対応にリライト |
| `topic-discovery/` | パス参照更新 |
| `asset-management-workflow/` | 出力パス 02_edit→02_draft |
| `experience-db-workflow/` | フォルダ構造参照を統一構成に更新 |
| `experience-db-critique/` | 03_edit→02_draft |
| `case-study-critique/` | パス参照更新 |
| `generate-market-report/` | 出力パス更新 |
| `weekly-*-aggregation/rendering/validation/` | パス更新 |
| `publish-to-note/` | 02_edit→02_draft |
| `competitor-analysis/` | articles/ スキャン更新 |

### 6.3 エージェント（`.claude/agents/`）

- `finance-article-writer.md`, `asset-management-writer.md`, `experience-writer.md`: meta パス更新
- `finance-topic-suggester.md`: articles/ スキャン更新
- `weekly-report-lead.md`, `wr-template-renderer.md`: パス更新

### 6.4 Python スクリプト

| スクリプト | 変更内容 |
|-----------|---------|
| `scripts/publish_to_note.py` | `02_edit/` → `02_draft/` |
| `scripts/note_publisher/draft_publisher.py` | 同上 |
| `scripts/note_publisher/markdown_parser.py` | 参照更新 |
| **新規** `scripts/migrate_articles.py` | マイグレーションスクリプト |

### 6.5 テンプレート（`template/`）

- `template/_common/` 新規作成（02_draft/, 03_published/, meta.yaml）
- `template/asset_management/` → `template/asset_formation/` リネーム
- `template/economic_indicators/` → `template/macro_economy/` リネーム
- `template/market_report/` → `template/weekly_report/` リネーム
- `template/investment_education/` → `template/asset_formation/` に統合
- `template/side_business/` 新規作成

### 6.6 ドキュメント

- `CLAUDE.md`: コマンドテーブル更新
- `AGENTS.md`: コマンド参照更新

---

## 7. 実装順序

### Phase A: 基盤（非破壊的）
1. `template/_common/` と統一 meta.yaml テンプレート作成
2. テンプレートのリネーム・再構成（_common + カテゴリ別）
3. `scripts/migrate_articles.py` 作成（--dry-run テスト）

### Phase B: マイグレーション
4. マイグレーションスクリプトを dry-run で検証
5. 実行して既存12本を新構成に移行
6. 旧ディレクトリ削除

### Phase C: 新コマンド作成
7. `/article-init` コマンド作成
8. `/article-research` コマンド作成
9. `/article-draft` コマンド作成
10. `/article-critique` コマンド作成
11. `/article-publish` コマンド作成
12. `/article-full` オーケストレーター作成
13. `/article-status` 作成

### Phase D: スキル・エージェント更新
14. パス参照を一括更新（Grep で `02_edit` `article-meta.json` `articles/` を検索→置換）
15. `analyze_existing_articles.py` をネスト構造対応にリライト
16. `publish_to_note.py` のパス解決更新

### Phase E: クリーンアップ
17. 旧コマンドに deprecation redirect 追加
18. CLAUDE.md, AGENTS.md 更新
19. 旧テンプレート削除

---

## 8. 検証方法

1. **マイグレーション検証**: `scripts/migrate_articles.py --dry-run` で全12本のマッピング確認
2. **記事初期化テスト**: `/article-init` で各カテゴリの記事フォルダを作成し、meta.yaml とサブフォルダが正しく生成されることを確認
3. **パス解決テスト**: `/article-publish --dry-run` で各カテゴリの記事パスが正しく解決されることを確認
4. **E2Eテスト**: `/article-full` で asset_formation カテゴリの記事を1本通しで作成（init→research→draft→critique→publish(dry-run)）
5. **Grep監査**: `grep -r "02_edit\|article-meta\.json\|economic_indicators\|asset_management/" .claude/ scripts/` で旧パス参照が残っていないことを確認
