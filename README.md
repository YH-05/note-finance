# note-finance

[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)
[![uv](https://img.shields.io/badge/uv-latest-green.svg)](https://github.com/astral-sh/uv)
[![Ruff](https://img.shields.io/badge/code%20style-ruff-000000.svg)](https://github.com/astral-sh/ruff)
[![CI](https://github.com/YH-05/finance/actions/workflows/ci.yml/badge.svg)](https://github.com/YH-05/finance/actions/workflows/ci.yml)

[note.com](https://note.com/) での金融コンテンツ発信を支援する Python ツールキット。RSSフィードからの金融ニュース自動収集、AI要約によるGitHub Issue投稿、週次マーケットレポート生成、記事執筆支援までを一貫して提供します。

## 主要機能

- **金融ニュース自動収集** — 34のRSSフィードから記事を収集し、本文抽出・AI要約・GitHub Project投稿を自動化
- **週次マーケットレポート** — 市場データとニュースを集約し、テンプレートベースのレポートを自動生成
- **記事執筆ワークフロー** — トピック提案・初稿生成・批評（事実/構成/読みやすさ/コンプライアンス）・修正の全工程を支援
- **RSS MCP Server** — Claude Code からRSSフィードを直接操作できるMCPサーバー

## セットアップ

```bash
# 依存関係のインストール
uv sync --all-extras

# Python バージョンの固定
uv python pin 3.12

# 環境変数の設定
cp .env.example .env
# .env を編集し ANTHROPIC_API_KEY を設定

# MCP サーバーの設定（任意）
cp .mcp.json.template .mcp.json
# .mcp.json を編集し API キーを設定
```

## 金融ニュース収集

RSSフィードから金融ニュースを収集し、GitHub Project #15 にIssueとして投稿するパイプライン。

### パイプライン概要

```
RSS収集 → 本文抽出 (trafilatura) → AI要約 (Claude) → カテゴリ別グルーピング → GitHub Issue投稿
```

6カテゴリに分類: 株価指数 / 個別銘柄 / セクター / マクロ経済 / AI関連 / 金融

### CLI

```bash
# 全カテゴリを収集・投稿
uv run python -m news.scripts.finance_news_workflow

# ドライラン（GitHub投稿をスキップ）
uv run python -m news.scripts.finance_news_workflow --dry-run

# 特定カテゴリのみ
uv run python -m news.scripts.finance_news_workflow --status index,macro

# 記事数を制限
uv run python -m news.scripts.finance_news_workflow --max-articles 10

# 詳細ログ
uv run python -m news.scripts.finance_news_workflow --verbose
```

| オプション | 説明 | デフォルト |
|-----------|------|-----------|
| `--config` | 設定ファイルパス | `data/config/news-collection-config.yaml` |
| `--dry-run` | Issue作成をスキップ | `False` |
| `--status` | カテゴリフィルタ（カンマ区切り） | 全カテゴリ |
| `--max-articles` | 最大記事数 | 無制限 |
| `--verbose`, `-v` | DEBUGログ出力 | `False` |

### 出力

- **コンソール**: 収集・抽出・要約・投稿件数のサマリー
- **ログ**: `logs/news-workflow-{日付}.log`
- **GitHub**: Project #15 にIssue投稿（カテゴリ別Statusフィールド付き）
- **Markdown**: `data/exports/news-workflow/` にエクスポート

## Claude Code ワークフロー

`.claude/` 配下にスラッシュコマンド・スキル・サブエージェントを定義し、コンテンツ制作を自動化します。

### コマンド一覧

| コマンド | 説明 |
|----------|------|
| `/finance-suggest-topics` | 金融記事のトピックを提案・スコアリング |
| `/new-finance-article` | 新規記事フォルダを作成（テンプレートから） |
| `/finance-edit` | 記事編集ワークフロー（初稿 → 批評 → 修正） |
| `/finance-full` | 記事作成の全工程を一括実行 |
| `/generate-market-report` | 週次マーケットレポートを自動生成 |
| `/ai-research-collect` | AI投資バリューチェーン（77社・10カテゴリ）の収集 |

### 記事編集の流れ

1. `/finance-suggest-topics` — トピック候補をスコアリング
2. `/new-finance-article` — フォルダ・テンプレート生成
3. `/finance-edit` — 初稿生成 → 5つの批評エージェント（事実/構成/データ/読みやすさ/コンプライアンス）→ 修正

### 週次レポートの流れ

`/generate-market-report` が以下をチーム制御:
1. ニュース集約（GitHub Projectから）
2. データ集約（指数・MAG7・セクター）
3. コメント生成（テンプレート + LLM）
4. テンプレート埋め込み
5. 品質検証 → Issue投稿

## パッケージ構成

```
src/
├── rss/           # RSSフィード管理
│   ├── core/      #   パーサー、HTTPクライアント、差分検知
│   ├── services/  #   フィード管理、記事抽出、バッチスケジューラ
│   ├── mcp/       #   MCP Server（7ツール）
│   ├── storage/   #   JSON永続化
│   └── cli/       #   CLIインターフェース
├── news/          # ニュース処理パイプライン
│   ├── orchestrator.py  # ワークフローオーケストレータ
│   ├── collectors/      # RSS収集
│   ├── extractors/      # 本文抽出（trafilatura / Playwright）
│   ├── summarizer.py    # AI要約（Anthropic Claude）
│   ├── grouper.py       # カテゴリ別グルーピング
│   ├── publisher.py     # GitHub Issue投稿
│   └── config/          # YAML設定ローダー
└── automation/    # Claude Agent SDK による自動実行
```

## 設定ファイル

| ファイル | 説明 |
|---------|------|
| `data/config/news-collection-config.yaml` | ニュース収集パイプラインの主設定（カテゴリマッピング、抽出、要約、GitHub） |
| `data/config/rss-presets.json` | RSSフィード一覧（34フィード、6カテゴリ） |
| `data/config/finance-news-themes.json` | テーマ別フィード割り当て（11テーマ） |
| `data/config/finance-news-filter.json` | ドメインフィルタリング・キーワード設定 |

## 開発

```bash
# 全チェック（format → lint → typecheck → test）
make check-all

# 個別実行
make format       # Ruff フォーマット
make lint         # Ruff リント（自動修正付き）
make typecheck    # pyright 型チェック
make test         # pytest テスト

# 単一テスト
uv run pytest tests/rss/unit/test_parser.py::TestClass::test_method -v

# パッケージ別テスト
uv run pytest tests/rss/ -v
uv run pytest tests/news/ -v
```

### CI/CD

GitHub Actions (`ci.yml`) が以下を実行:
- **Lint**: Ruff + pre-commit + Bandit + pip-audit
- **Type Check**: pyright (Python 3.12)
- **Unit Tests**: pytest（`-m "not integration"`）
- **Integration Tests**: mainブランチpush時のみ（Anthropic APIキー必要）

## 技術スタック

| カテゴリ | ツール |
|---------|--------|
| 言語 | Python 3.12+ |
| パッケージ管理 | uv |
| HTTP | httpx |
| RSS解析 | feedparser |
| 本文抽出 | trafilatura, Playwright（フォールバック） |
| AI要約 | Anthropic Claude API |
| 構造化ログ | structlog |
| バリデーション | Pydantic |
| テスト | pytest, Hypothesis, pytest-asyncio |
| リンター | Ruff |
| 型チェック | pyright |
| MCP | FastMCP |
