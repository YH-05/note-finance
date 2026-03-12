# CLAUDE.md

> **Note**: プロジェクト共通の指示は `AGENTS.md` を参照してください。
> このファイルは Claude Code 固有の設定のみを記載しています。

## Claude Code Integration (`.claude/`)

| ディレクトリ | 内容 |
|-------------|------|
| `agents/` | 60サブエージェント（記事執筆、批評、PRレビュー、週次レポートチーム、リサーチ等） |
| `commands/` | 19スラッシュコマンド（`/finance-edit`, `/generate-market-report` 等） |
| `skills/` | 43スキル（ニュース収集、レポート生成、TDD、PRレビュー、品質管理等） |
| `rules/` | コーディング規約、Git運用、テスト戦略、サブエージェントデータ受け渡し |

## Slash Commands

| コマンド | 説明 |
|----------|------|
| `/finance-suggest-topics` | 金融記事のトピックを提案 |
| `/new-finance-article` | 新規記事フォルダを作成 |
| `/finance-edit` | 記事編集ワークフロー（初稿→批評→修正） |
| `/finance-full` | 記事作成の全工程を一括実行 |
| `/publish-to-note` | 記事をnote.comに下書き投稿 |
| `/generate-market-report` | 週次マーケットレポートを自動生成 |
| `/ai-research-collect` | AI投資バリューチェーン収集 |
| `/asset-management` | 資産形成コンテンツ（note記事+X投稿）を自動生成 |
| `/reddit-finance-topics` | Reddit金融コミュニティからトピック発見・記事化 |

## Obsidian 操作ルール

Obsidian を操作する際は `obsidian` コマンド（`/Applications/Obsidian.app/Contents/MacOS/obsidian`）のみを使用すること。ファイルの読み書きや検索等も `obsidian` CLI 経由で行う。
