# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

note.com での金融コンテンツ発信を支援するツールキット。RSSニュース自動収集・AI要約・GitHub Issue投稿、週次レポート生成、記事執筆支援を提供。

- **GitHub**: `YH-05/finance`
- **Python 3.12+** / uv / Ruff / pyright / pytest

## Development Commands

```bash
# 全チェック（format → lint → typecheck → test の順に実行）
make check-all

# 個別実行
make format       # uv run ruff format src/ tests/
make lint         # uv run ruff check src/ tests/ --fix
make typecheck    # uv run pyright src/ tests/
make test         # uv run pytest tests/ -v

# 単一テスト実行
uv run pytest tests/rss/unit/test_parser.py::TestClass::test_method -v

# パッケージ別テスト
uv run pytest tests/rss/ -v
uv run pytest tests/news/ -v

# 依存関係インストール
uv sync --all-extras
```

## Architecture

### Source Packages (`src/`)

3パッケージ構成。`pyproject.toml` の `pythonpath = ["src"]` により `src/` がPythonパスに追加される。

| パッケージ | 説明 | エントリポイント |
|-----------|------|-----------------|
| `rss` | RSSフィード管理（パーサー・HTTP・差分検知・MCP Server） | `rss-mcp`, `rss-cli` |
| `news` | ニュース処理パイプライン（収集→抽出→要約→グルーピング→GitHub投稿） | `python -m news.scripts.finance_news_workflow` |
| `automation` | Claude Agent SDK による自動収集 | `collect-finance-news` |

### News Pipeline

`news.orchestrator.NewsWorkflowOrchestrator` が中心。

```
Collect (RSS) → Extract (trafilatura/Playwright) → Summarize (Claude API) → Group → Export (Markdown) → Publish (GitHub Issues)
```

- 設定: `data/config/news-collection-config.yaml`
- カテゴリ: `index`(株価指数), `stock`(個別銘柄), `sector`(セクター), `macro`(マクロ経済), `ai`(AI関連), `finance`(金融)
- テーマ: `data/config/finance-news-themes.json` で11テーマにフィードを割り当て
- GitHub Project #15 にIssue投稿（カテゴリ別Statusフィールド + 公開日フィールド設定、URL重複チェック付き）
- 抽出フォールバック: trafilatura → Playwright → RSS summary

### RSS Package

MCP Server (`rss.mcp.server`) で Claude Code からRSSフィード操作可能。7ツール: list/get/search/add/update/remove/fetch。

- フィードデータ: `data/raw/rss/`（JSON永続化）
- プリセット: `data/config/rss-presets.json`（34フィード、6カテゴリ）

### Claude Code Integration (`.claude/`)

| ディレクトリ | 内容 |
|-------------|------|
| `agents/` | 22サブエージェント（記事執筆、5つの批評、週次レポートチーム、リサーチ等） |
| `commands/` | 6スラッシュコマンド（`/finance-edit`, `/generate-market-report` 等） |
| `skills/` | 7スキル（ニュース収集、レポート生成、データ集約等） |
| `rules/` | コーディング規約、Git運用、テスト戦略、サブエージェントデータ受け渡し |

### Data Layout

| パス | 内容 |
|------|------|
| `data/config/` | YAML/JSON設定ファイル |
| `data/raw/rss/` | RSSフィード生データ（JSON） |
| `data/exports/news-workflow/` | パイプライン出力（Markdown/JSON） |
| `logs/` | ワークフローログ |
| `scripts/` | Python前処理スクリプト（`prepare_news_session.py`, テーマ別収集等） |
| `template/` | 記事テンプレート（参照専用、変更・削除禁止） |
| `snippets/` | 免責事項・警告文等の共通テキスト |

## Key Conventions

- **型ヒント**: Python 3.12+ スタイル（`list[str]`, `dict[str, int]`, `T | None`）。PEP 695 ジェネリクス使用
- **Docstring**: NumPy形式
- **ロギング**: `structlog` ベース。全コードに構造化ログ必須
- **テスト命名**: 日本語（`test_正常系_有効なデータで処理成功`, `test_異常系_不正入力でValueError`）
- **テスト種別**: `tests/{package}/unit/`, `property/`（Hypothesis）, `integration/`
- **コミット**: Conventional Commits形式（`feat(scope): 説明`）。PR/Issueは日本語
- **アンカーコメント**: `AIDEV-NOTE:`, `AIDEV-TODO:`, `AIDEV-QUESTION:`

## Slash Commands

| コマンド | 説明 |
|----------|------|
| `/finance-suggest-topics` | 金融記事のトピックを提案 |
| `/new-finance-article` | 新規記事フォルダを作成 |
| `/finance-edit` | 記事編集ワークフロー（初稿→批評→修正） |
| `/finance-full` | 記事作成の全工程を一括実行 |
| `/generate-market-report` | 週次マーケットレポートを自動生成 |
| `/ai-research-collect` | AI投資バリューチェーン収集 |
| `/asset-management` | 資産形成コンテンツ（note記事+X投稿）を自動生成 |
| `/reddit-finance-topics` | Reddit金融コミュニティからトピック発見・記事化 |
