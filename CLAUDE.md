# CLAUDE.md

> **Note**: プロジェクト共通の指示は `AGENTS.md` を参照してください。
> このファイルは Claude Code 固有の設定のみを記載しています。

## Claude Code Integration (`.claude/`)

| ディレクトリ | 内容 |
|-------------|------|
| `agents/` | 60サブエージェント（記事執筆、批評、PRレビュー、週次レポートチーム、リサーチ等） |
| `commands/` | 25スラッシュコマンド（`/finance-edit`, `/generate-market-report`, `/convert-pdf` 等） |
| `skills/` | 45スキル（ニュース収集、レポート生成、TDD、PRレビュー、品質管理、PDF変換等） |
| `rules/` | コーディング規約、Git運用、テスト戦略、サブエージェントデータ受け渡し |

## Slash Commands

### 記事ワークフロー（新コマンド）

| コマンド | 説明 |
|----------|------|
| `/article-init` | 新規記事フォルダを作成 |
| `/article-research` | カテゴリに応じたリサーチを実行 |
| `/article-draft` | リサーチ結果から初稿を作成 |
| `/article-critique` | 初稿の批評と修正 |
| `/article-publish` | 記事をnote.comに下書き投稿 |
| `/article-full` | 記事作成の全工程を一括実行 |
| `/article-status` | 全記事のステータス一覧 |

### タスク管理

| コマンド | 説明 |
|----------|------|
| `/todo` | 日次TODOリストの作成・更新・振り返り（`--start` / `--update` / `--end`） |

### リサーチ・レポート

| コマンド | 説明 |
|----------|------|
| `/topic-discovery` | KGデータ優先で記事トピックを提案（旧: `/finance-suggest-topics`） |
| `/kg-summary` | トピックのKGアセットをCypherで即時照会（LLM不使用） |
| `/generate-market-report` | 週次マーケットレポートを自動生成 |
| `/ai-research-collect` | AI投資バリューチェーン収集 |
| `/reddit-finance-topics` | Reddit金融コミュニティからトピック発見・記事化 |
| `/convert-pdf` | 単一PDFをMarkdownに変換（Claude Code直接Read方式） |
| `/pdf-to-knowledge` | PDF→Markdown→ナレッジグラフの一括ワークフロー |

### クリエイター運用

| コマンド | 説明 |
|----------|------|
| `/mitsuki-draft` | みつき（美月）の週次投稿ドラフト生成（タロット・星座・Tips・ENG 4本） |
| `/mitsuki-publish` | みつきのドラフトをThreads/noteに投稿 |
| `/kuroto-draft` | 玄人領域の週次投稿ドラフト生成（哲学・FW・海外メソッド・内向型・書籍 5本/日） |
| `/kuroto-publish` | 玄人領域のドラフトをThreads/noteに投稿 |

### 非推奨コマンド

| コマンド | 移行先 |
|----------|--------|
| `/new-finance-article` | `/article-init` |
| `/finance-edit` | `/article-draft` + `/article-critique` |
| `/finance-full` | `/article-full` |
| `/publish-to-note` | `/article-publish` |
| `/asset-management` | `/article-full --category asset_management` |
| `/finance-suggest-topics` | `/topic-discovery` |

## 実行環境

- Python スクリプトは必ず `uv run` 経由で実行すること（素の `python` / `python3` 直接実行は禁止）
- Python ファイルの配置先は以下に限定する（それ以外への新規作成は禁止）:
  - `src/` — パッケージソース
  - `scripts/` — ユーティリティスクリプト
  - `tests/` — テストコード
  - `.claude/skills/*/` — スキル内スクリプト
  - `.claude/hooks/` — hookスクリプト
  - `.tmp/` に一時スクリプトを置いた場合、用途が完了したら速やかに削除すること

## 制約事項

- `template/` は変更・削除禁止
- ファイル・ディレクトリを削除する際は `rm` ではなく `trash/` に移動すること
- `trash/` はユーザーが定期的に確認・削除する

## Obsidian 操作ルール

Obsidian を操作する際は `obsidian` コマンド（`/Applications/Obsidian.app/Contents/MacOS/obsidian`）のみを使用すること。ファイルの読み書きや検索等も `obsidian` CLI 経由で行う。
