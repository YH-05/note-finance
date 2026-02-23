# 金融ニュース収集ワークフロー再構築計画

## Context

金融ニュース収集パイプライン（`src/news/`）は、GitHub Project #15 への Issue 投稿を前提に構築されている。Issue投稿を廃止し、**ローカルJSON/Markdown出力のみ**に簡素化する。これにより GitHub API 依存による信頼性問題を解消し、コードの保守性を大幅に改善する。

**現状のパイプライン（6ステージ）:**
```
RSS収集 → 本文抽出 → AI要約 → グルーピング → Markdown出力 → GitHub Issue投稿
```

**再構築後（4ステージ）:**
```
RSS収集 → 本文抽出 → AI要約 → ローカル出力（JSON + Markdown）
```

---

## Phase 1: モデル・設定レイヤーの更新

### 1-1. `src/news/models.py` — GitHub関連モデルの削除

**削除するモデル:**
- `PublicationStatus` (L297-332)
- `PublishedArticle` (L672-759)
- `CategoryPublishResult` (L547-619)

**修正するモデル:**

`WorkflowResult` (L918-1045):
- 削除: `total_published`, `total_duplicates`, `publication_failures`, `published_articles`, `category_results`
- 追加: `total_exported: int`, `total_deduplicated: int`, `export_dir: str | None`, `exported_files: list[str]`

`__all__` (L1047-1065): 削除したモデル名を除去

### 1-2. `src/news/config/models.py` — GitHub関連設定の削除

**削除するクラス:**
- `GitHubConfig` (L781-845)
- `GitHubSinkConfig` (L339-361)
- `PublishingConfig` (L976-1011)

**追加するクラス:**
```python
class ExportConfig(BaseModel):
    base_dir: str = Field(default="data/exports/news-workflow")
    format_json: bool = Field(default=True)
    format_markdown: bool = Field(default=True)
    duplicate_check_days: int = Field(default=7, ge=0)
```

**修正するクラス:**

`NewsWorkflowConfig` (L1096-1205):
- 削除: `github: GitHubConfig`, `github_status_ids: dict[str, str]`, `publishing: PublishingConfig`
- `status_mapping` → `category_mapping` にリネーム（カテゴリ正規化マッピングとして維持）
- 追加: `export: ExportConfig`

### 1-3. `data/config/news-collection-config.yaml` — 設定ファイル簡素化

**削除するセクション:** `github_status_ids`, `github`, `publishing`

**追加するセクション:**
```yaml
export:
  base_dir: "data/exports/news-workflow"
  format_json: true
  format_markdown: true
  duplicate_check_days: 7
```

`status_mapping` → `category_mapping` にリネーム

---

## Phase 2: ローカル重複チェック・JSONエクスポーターの作成

### 2-1. `src/news/dedup.py` — 新規作成

ローカルファイルベースの重複チェッカー。過去N日分の `index.json` からURL集合を構築。

```python
class LocalDuplicateChecker:
    def __init__(self, export_base_dir: Path, lookback_days: int = 7) -> None: ...
    def get_existing_urls(self) -> set[str]: ...
    def is_duplicate(self, url: str, existing_urls: set[str]) -> bool: ...
```

既存の `tests/news/unit/core/test_dedup.py` を拡張。

### 2-2. `src/news/exporters/json_exporter.py` — 新規作成

要約済み記事をJSON形式でエクスポート。

```python
class JsonExporter:
    def export(self, articles: list[SummarizedArticle], ...) -> Path: ...
```

**出力 `index.json` のスキーマ:**
```json
{
  "version": "2.0",
  "generated_at": "ISO8601",
  "period": { "max_age_hours": 168, "earliest_article": "...", "latest_article": "..." },
  "statistics": { "total_collected": 50, "total_extracted": 45, "total_summarized": 42, "by_category": {} },
  "articles": [
    {
      "url": "...", "title": "...", "published": "...",
      "source_name": "...", "category": "index", "category_label": "株価指数",
      "raw_summary": "...",
      "extraction_status": "success", "extraction_method": "trafilatura",
      "body_text": "...",
      "summary": { "overview": "...", "key_points": [], "market_impact": "...", "related_info": null }
    }
  ],
  "failures": { "extraction": [], "summarization": [] },
  "feed_errors": [],
  "domain_extraction_rates": []
}
```

**出力ディレクトリ構造:**
```
data/exports/news-workflow/
  2026-02-23/
    index.json            # 全記事データ（週次レポート・記事執筆の入力）
    index.md              # セッション概要
    categories/
      index.md            # 株価指数
      stock.md            # 個別銘柄
      ...
```

テスト: `tests/news/unit/exporters/test_json_exporter.py`

---

## Phase 3: オーケストレーター改修

### 3-1. `src/news/orchestrator.py` (1116行)

**削除:**
- `from news.publisher import Publisher`
- `Publisher` 関連の import (`PublishedArticle`, `CategoryPublishResult`, `PublicationStatus`)
- `_publisher` 属性と初期化
- メソッド群: `_run_publishing`, `_run_per_category_publishing`, `_run_per_article_publishing`, `_publish_batch_with_progress`, `_log_publish_result_category`, `_log_publish_result_article`

**変更:**
- `run()` シグネチャ: `dry_run`, `export_only` パラメータ削除、`output_dir: Path | None` 追加
- 重複チェック: `Publisher.get_existing_urls()` → `LocalDuplicateChecker.get_existing_urls()`
- ステージ 4-6（Group → Export → Publish）→ ステージ 4（Group → JSON Export → Markdown Export）に統合
- `_build_result()`: publication関連フィールド → export関連フィールドに置換
- `_log_final_summary()`: publication統計 → export統計に変更

### 3-2. `src/news/progress.py`

publication関連の進捗出力を削除、export進捗に置換

### 3-3. 既存テスト更新

- `tests/news/unit/test_orchestrator.py` — Publisherモック削除、Export検証追加
- `tests/news/unit/test_orchestrator_integration.py` — 同上
- `tests/news/unit/test_orchestrator_metrics.py` — publishingメトリクス削除
- `tests/news/unit/test_models.py` — 削除モデルのテスト除去
- `tests/news/unit/test_models_category.py` — `CategoryPublishResult` テスト除去
- `tests/news/unit/test_result.py` — `WorkflowResult` テスト更新

---

## Phase 4: CLI・publisher削除・テスト整理

### 4-1. `src/news/scripts/finance_news_workflow.py` (454行)

**削除するオプション:** `--format`, `--dry-run`, `--export-only`
**リネーム:** `--status` → `--category`
**追加するオプション:** `--output-dir`, `--no-dedup`, `--json-only`

### 4-2. ファイル削除

- `src/news/publisher.py` — 全削除
- `tests/news/unit/publishers/test_publisher.py` — 全削除
- `tests/news/unit/test_publisher_category.py` — 全削除
- `tests/news/unit/sinks/test_github.py` — 全削除（GitHub sink テスト）

### 4-3. テスト更新

- `tests/news/unit/scripts/test_finance_news_workflow.py` — CLI引数テスト更新
- `tests/news/unit/config/test_workflow.py` — `GitHubConfig` テスト削除、`ExportConfig` テスト追加

---

## Phase 5: Claude Code連携の更新

### 5-1. `.claude/skills/finance-news-workflow/SKILL.md`

現在の3フェーズ（Python前処理 → article-fetcher並列 → 結果集約）を簡素化:
- Python CLI直接実行（`python -m news.scripts.finance_news_workflow`）に一本化
- article-fetcherエージェント呼び出しを削除

### 5-2. `.claude/agents/news-article-fetcher.md`

GitHub Issue作成専用エージェント → 廃止。`.claude/agents/` から削除（または `_archived/` に移動）

### 5-3. `scripts/prepare_news_session.py` (980行)

**削除:**
- GitHub Issue取得ロジック（`_get_existing_issues`, `_extract_urls_from_issues`）
- `issue_config` 生成
- GitHub Project関連設定

**変更:**
- 重複チェック: GitHub API → ローカルJSON参照

### 5-4. `.claude/rules/subagent-data-passing.md`

`issue_config` 関連の記述を削除

---

## Phase 6: 週次レポートとの接続

### 6-1. `.claude/agents/wr-news-aggregator.md`

**変更:** `gh project item-list`（GitHub Project #15 からの取得）→ `data/exports/news-workflow/*/index.json` のローカルファイル読み込み

**カテゴリマッピング:** `index.json` の `category` フィールドを `news_from_project.json` のカテゴリに変換
- `index` → `indices`, `stock` → `mag7`, `sector` → `sectors`, `macro` → `macro`, `ai` → `tech`, `finance` → `finance`

**出力形式:** `news_from_project.json` は現行フォーマットを維持（下流エージェントに影響なし）

---

## 対象ファイル一覧

### 新規作成
| ファイル | 説明 |
|---------|------|
| `src/news/dedup.py` | ローカルファイルベース重複チェッカー |
| `src/news/exporters/__init__.py` | エクスポーターパッケージ |
| `src/news/exporters/json_exporter.py` | JSONエクスポーター |
| `tests/news/unit/test_dedup_local.py` | 重複チェッカーテスト |
| `tests/news/unit/exporters/__init__.py` | テストパッケージ |
| `tests/news/unit/exporters/test_json_exporter.py` | JSONエクスポーターテスト |

### 主要変更
| ファイル | 変更内容 |
|---------|---------|
| `src/news/orchestrator.py` | Publisher削除、Export統合、run()シグネチャ変更 |
| `src/news/models.py` | 3モデル削除、WorkflowResult修正 |
| `src/news/config/models.py` | 3クラス削除、ExportConfig追加、NewsWorkflowConfig修正 |
| `src/news/scripts/finance_news_workflow.py` | CLI引数変更 |
| `src/news/progress.py` | publication進捗→export進捗 |
| `data/config/news-collection-config.yaml` | GitHub設定削除、export設定追加 |
| `scripts/prepare_news_session.py` | GitHub Issue取得ロジック削除 |
| `.claude/skills/finance-news-workflow/SKILL.md` | article-fetcher廃止、CLI直接実行 |
| `.claude/agents/wr-news-aggregator.md` | GitHub Project→ローカルJSON読み込み |
| `.claude/rules/subagent-data-passing.md` | issue_config記述削除 |

### 削除
| ファイル | 理由 |
|---------|------|
| `src/news/publisher.py` | GitHub Issue投稿ロジック全体 |
| `tests/news/unit/publishers/test_publisher.py` | publisher テスト |
| `tests/news/unit/test_publisher_category.py` | カテゴリpublisher テスト |
| `.claude/agents/news-article-fetcher.md` | Issue作成エージェント |

---

## 検証方法

### 各Phase完了時
```bash
make check-all   # format → lint → typecheck → test
```

### Phase 4完了後（E2E検証）
```bash
# 1. パイプライン実行（少量テスト）
uv run python -m news.scripts.finance_news_workflow --category index --max-articles 3 --verbose

# 2. 出力確認
ls data/exports/news-workflow/2026-02-23/
cat data/exports/news-workflow/2026-02-23/index.json | python -m json.tool | head -50
cat data/exports/news-workflow/2026-02-23/categories/index.md

# 3. 重複チェック検証（2回目実行で重複スキップされること）
uv run python -m news.scripts.finance_news_workflow --category index --max-articles 3 --verbose
```

### Phase 6完了後（週次レポート連携検証）
- `wr-news-aggregator` がローカルJSONから正しく `news_from_project.json` を生成できることを確認
- 下流の `wr-data-aggregator`, `wr-comment-generator` が変更なしで動作することを確認
