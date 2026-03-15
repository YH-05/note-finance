# AGENTS.md

このファイルはAIコーディングエージェント向けのプロジェクト指示書です。
プラットフォーム非依存の共通ドキュメントとして、すべてのAIエージェントが参照します。

> **プラットフォーム固有の設定**:
> - Claude Code: `CLAUDE.md` (自動読み込み) + `.claude/` (agents, commands, skills, rules)
> - Gemini CLI / Antigravity: `.gemini/settings.json` (`contextFileName`) + `.agents/` (workflows, skills)

## Project Overview

note.com での金融コンテンツ発信を支援するツールキット。RSSニュース自動収集・AI要約・GitHub Issue投稿、週次レポート生成、記事執筆支援を提供。

- **GitHub**: `YH-05/finance`
- **Python 3.12+** / uv / Ruff / pyright / pytest

## Purpose & Vision

### 目的

AIツール（Claude Code, Gemini CLI, Google Antigravity）のみを活用し、note.com + Xでの金融コンテンツ発信で**月5万円の安定収益**を目指す副業プロジェクト。Claude Code subscription費用をまかないつつ収益化の幅を広げる。

### 制約

- 副業に割ける時間: **1時間/日**
- 1日の作業フロー: テーマ選定・AI生成指示(10分) → 記事確認(5分) → note投稿+X投稿(5分) → 残りはストック生成
- リーンスタートアップ的アプローチ（Phase 1: テスト期間 → Phase 2: 絞り込み）

### ターゲット読者

20-30代の新NISA世代。DIYで資産管理したいが不安な層。NISA改革で初心者が大量流入中。

### コンテンツ戦略

**テーマ優先順位**（2026-03-09 深掘り調査結果）:

| 順位 | テーマ | 評価 | 差別化切り口 |
|------|--------|------|-------------|
| 1 | 投資の心理学 | A | 相場×心理日記型（リアルタイム連載） |
| 2 | ポイント経済圏 | B+ | 乗り換えガイド + 改悪ウォッチ |
| 3 | 制度活用（NISA/iDeCo/ふるさと納税） | B+ | 3制度横断×年収別シミュレーション |
| 4 | 投資本レビュー | B+ | 2冊比較型 |
| 5 | クレカ比較 | B- | ライフスタイル別診断型 |

**ハイブリッド戦略**: 投資（信頼構築）× ビジネス（ストック）× 恋愛（集客）のジャンル横断。

**AI臭さ対策**（最重要）:
- 自分の実体験・数字を入れる（1記事2-3行、5分）
- 意見・立場を明確にする
- マリーさんトーン（`mary-tone-writer`スキル）の活用
- ストーリー型タイトル、X投稿との連動で人格を作る

### トラフィック戦略

SNS（特にX）→ メールリスト → YouTube/Pinterest → コンテンツ再利用。SEO依存は致命的（HCU事例）。noteへの適用: X投稿で認知 → note記事で信頼構築。

### 収益モデル

| 手段 | 単価 | 月5万に必要な規模 |
|------|------|-------------------|
| 有料記事（単品） | 300-500円 | 月100-170人購入 |
| 定期購読マガジン | 500-1,000円/月 | 50-100人の定期読者 |
| メンバーシップ | 500-1,000円/月 | 50-100人 |

## Design Philosophy

### 核心: KnowledgeGraph（Neo4j）

本プロジェクトの最大の差別化要素であり技術的な肝。個人ブロガーが到達できない「構造化された知識基盤」をAIエージェントに提供し、以下を実現する:

1. **投資仮説の自動構築**: 複数のソース横断で矛盾・裏付け・新しい因果関係を発見
2. **記事品質の根本的な向上**: 主張（Claim）にソース（Source）が紐づくため、エビデンスベースの記事を自動生成
3. **時系列での知識蓄積**: 記事を書くほどグラフが豊かになり、過去の分析との比較・トレンド検出が可能に
4. **他のnoteクリエイターとの決定的な差**: 手作業では不可能な規模の情報統合

```
[1次ソース]                    [KnowledgeGraph]              [コンテンツ出力]
SEC filings ─┐                ┌─ Entity(企業/人物)      ┌─ 週次レポート
IRレポート ──┤  PDF Pipeline  ├─ Claim(主張/評価)  ───→ ├─ 投資分析記事
セルサイド ──┤ ─────────────→ ├─ Fact(財務データ)       ├─ テーマ記事
中央銀行 ───┤                ├─ Source(出典トレース)    └─ 投資仮説
ブログ ─────┘                └─ FiscalPeriod(時間軸)
```

- **入力**: SEC filings、IRレポート、セルサイドレポート、中央銀行レポート、ブログ
- **処理**: PDF → Markdown → チャンキング → 知識抽出 → Entity名寄せ → Neo4j投入
- **インフラ**: Docker上のNeo4j + APOC、3つのNeo4j MCP Server（cypher / data-modeling / memory）
- **スキーマ**: 5層構造（ソース・レキシカル・ナレッジ・マスター・時間イベント）
- **冪等性**: SHA-256ハッシュベースのID生成 + MERGEベース投入で重複なし
- **設計ドキュメント**: `docs/plan/KnowledgeGraph/`

### コンテンツ自動化パイプライン

KnowledgeGraphの知識を活用し、1時間/日の制約下で品質と量を両立するための60エージェント構成。

```
収集（RSS/Reddit/Web） → 選定（トピック提案） → 執筆（記事生成）
→ 批評（4-5観点並列） → 修正 → 投稿（note.com/X）
```

- **収集層**: RSS MCP、Reddit MCP、Web検索でソースを自動収集 → KnowledgeGraphに蓄積
- **執筆層**: テーマ別writer（金融、体験談、資産形成）+ マリーさんトーン。KnowledgeGraphからエビデンスを引用
- **批評層**: データ正確性・構成・可読性・コンプライアンス等を並列評価
- **配信層**: note.com下書き投稿、X投稿の自動生成

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

6パッケージ構成。`pyproject.toml` の `pythonpath = ["src"]` により `src/` がPythonパスに追加される。

| パッケージ   | 説明                                                               | エントリポイント                              |
| ------------ | ------------------------------------------------------------------ | --------------------------------------------- |
| `rss`        | RSSフィード管理（パーサー・HTTP・差分検知・MCP Server）            | `rss-mcp`, `rss-cli`                          |
| `news`       | ニュース処理パイプライン（収集→抽出→要約→グルーピング→GitHub投稿） | `python -m news.scripts.finance_news_workflow` |
| `automation` | Agent SDK による自動収集                                           | `collect-finance-news`                        |
| `news_scraper` | ニューススクレイピング                                           | -                                             |
| `report_scraper` | レポートスクレイピング                                         | -                                             |
| `pdf_pipeline` | PDF→ナレッジグラフ パイプライン                                  | -                                             |

### News Pipeline

`news.orchestrator.NewsWorkflowOrchestrator` が中心。

```
Collect (RSS) → Extract (trafilatura/Playwright) → Summarize (LLM API) → Group → Export (Markdown) → Publish (GitHub Issues)
```

- 設定: `data/config/news-collection-config.yaml`
- カテゴリ: `index`(株価指数), `stock`(個別銘柄), `sector`(セクター), `macro`(マクロ経済), `ai`(AI関連), `finance`(金融)
- テーマ: `data/config/finance-news-themes.json` で11テーマにフィードを割り当て
- GitHub Project #15 にIssue投稿（カテゴリ別Statusフィールド + 公開日フィールド設定、URL重複チェック付き）
- 抽出フォールバック: trafilatura → Playwright → RSS summary

### RSS Package

MCP Server (`rss.mcp.server`) でRSSフィード操作可能。7ツール: list/get/search/add/update/remove/fetch。

- フィードデータ: `data/raw/rss/`（JSON永続化）
- プリセット: `data/config/rss-presets.json`（34フィード、6カテゴリ）

### AI Agent Integration

| プラットフォーム       | 設定ディレクトリ        | 内容                                           |
| ---------------------- | ----------------------- | ---------------------------------------------- |
| Claude Code            | `.claude/`              | 60エージェント、21コマンド、44スキル、8ルール |
| Gemini CLI/Antigravity | `.gemini/` + `.agents/` | 16コマンド、10ワークフロー、38スキル          |

### MCP Servers

以下のMCPサーバーが利用可能（`.gemini/settings.json` / `.claude/settings.local.json`）:

| サーバー              | 用途                          |
| --------------------- | ----------------------------- |
| `rss`                 | プロジェクト内RSSフィード管理 |
| `git`                 | Git操作                       |
| `filesystem`          | ファイルシステム操作          |
| `sequential-thinking` | 逐次思考                      |
| `memory`              | 永続メモリ                    |
| `fetch`               | URL取得                       |
| `time`                | タイムゾーン管理（Asia/Tokyo）|
| `reddit`              | Reddit情報収集                |
| `wikipedia`           | Wikipedia検索                 |
| `sec-edgar-mcp`       | SEC EDGAR企業情報             |
| `slack`               | Slack連携                     |
| `notebooklm`          | NotebookLM連携                |
| `context7`            | ライブラリドキュメント検索    |
| `tavily`              | Web検索（Tavily API）         |
| `playwright`          | ブラウザ自動化                |
| `neo4j-cypher`        | Neo4j Cypherクエリ            |
| `neo4j-data-modeling`  | Neo4jデータモデリング        |

### Data Layout

| パス                          | 内容                                                                |
| ----------------------------- | ------------------------------------------------------------------- |
| `data/config/`                | YAML/JSON設定ファイル                                               |
| `data/raw/rss/`               | RSSフィード生データ（JSON）                                         |
| `data/exports/news-workflow/` | パイプライン出力（Markdown/JSON）                                   |
| `logs/`                       | ワークフローログ                                                    |
| `scripts/`                    | Python前処理スクリプト（`prepare_news_session.py`, テーマ別収集等） |
| `template/`                   | 記事テンプレート（参照専用、変更・削除禁止）                        |
| `snippets/`                   | 免責事項・警告文等の共通テキスト                                    |

## Key Conventions

- **型ヒント**: Python 3.12+ スタイル（`list[str]`, `dict[str, int]`, `T | None`）。PEP 695 ジェネリクス使用
- **Docstring**: NumPy形式
- **ロギング**: `structlog` ベース。全コードに構造化ログ必須
- **テスト命名**: 日本語（`test_正常系_有効なデータで処理成功`, `test_異常系_不正入力でValueError`）
- **テスト種別**: `tests/{package}/unit/`, `property/`（Hypothesis）, `integration/`
- **コミット**: Conventional Commits形式（`feat(scope): 説明`）。PR/Issueは日本語
- **アンカーコメント**: `AIDEV-NOTE:`, `AIDEV-TODO:`, `AIDEV-QUESTION:`

## Commands

以下のコマンドが全プラットフォームで利用可能。

### 金融コンテンツ

| コマンド                  | 説明                                            |
| ------------------------- | ----------------------------------------------- |
| `/finance-suggest-topics` | 金融記事のトピックを提案                        |
| `/new-finance-article`    | 新規記事フォルダを作成                          |
| `/finance-edit`           | 記事編集ワークフロー（初稿→批評→修正）          |
| `/finance-full`           | 記事作成の全工程を一括実行                      |
| `/publish-to-note`        | 記事をnote.comに下書き投稿                      |
| `/asset-management`       | 資産形成コンテンツ（note記事+X投稿）を自動生成  |

### リサーチ・レポート

| コマンド                  | 説明                                            |
| ------------------------- | ----------------------------------------------- |
| `/generate-market-report` | 週次マーケットレポートを自動生成                |
| `/ai-research-collect`    | AI投資バリューチェーン収集                      |
| `/reddit-finance-topics`  | Reddit金融コミュニティからトピック発見・記事化  |

### PDF・ナレッジグラフ

| コマンド              | 説明                                                                |
| --------------------- | ------------------------------------------------------------------- |
| `/convert-pdf`        | 単一PDFをMarkdownに変換（Claude Code直接Read方式）                  |
| `/pdf-to-knowledge`   | PDF→Markdown→ナレッジグラフの一括ワークフロー                       |
| `/save-to-graph`      | graph-queueのデータをNeo4jに投入                                    |

### 開発ツール

| コマンド         | 説明                                    |
| ---------------- | --------------------------------------- |
| `/write-tests`   | t-wada流TDDによるテスト作成             |
| `/commit-and-pr` | 変更のコミットとPR作成を一括実行        |
| `/push`          | 変更をコミットしてリモートにプッシュ     |
| `/merge-pr`      | PRのコンフリクトチェック・CI確認・マージ |
| `/gemini-search` | Gemini CLIを使用してWeb検索             |
