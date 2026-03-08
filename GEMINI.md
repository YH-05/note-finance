# GEMINI.md

> **Note**: プロジェクト共通の指示は `AGENTS.md` を参照してください。
> このファイルは Gemini CLI / Antigravity 固有の設定のみを記載しています。

## Antigravity Integration (`.agents/`)

| ディレクトリ | 内容 |
|-------------|------|
| `workflows/` | 10ワークフロー（記事編集、レポート生成、リサーチ収集、テスト等） |
| `skills/` | 36スキル（ニュース収集、レポート生成、データ集約、Git操作等） |

## Commands & Workflows

### 金融コンテンツ

| コマンド | ワークフロー | 説明 |
|----------|-------------|------|
| `/finance-suggest-topics` | ✓ | 金融記事のトピックを提案 |
| `/new-finance-article` | ✓ | 新規記事フォルダを作成 |
| `/finance-edit` | ✓ | 記事編集ワークフロー（初稿→批評→修正） |
| `/finance-full` | ✓ | 記事作成の全工程を一括実行 |
| `/publish-to-note` | ✓ | 記事をnote.comに下書き投稿 |
| `/asset-management` | ✓ | 資産形成コンテンツ（note記事+X投稿）を自動生成 |

### リサーチ・レポート

| コマンド | ワークフロー | 説明 |
|----------|-------------|------|
| `/generate-market-report` | ✓ | 週次マーケットレポートを自動生成 |
| `/ai-research-collect` | ✓ | AI投資バリューチェーン収集 |
| `/reddit-finance-topics` | ✓ | Reddit金融コミュニティからトピック発見・記事化 |

### 開発ツール

| コマンド | スキル参照 | 説明 |
|----------|-----------|------|
| `/write-tests` | ✓ | t-wada流TDDによるテスト作成 |
| `/commit-and-pr` | ✓ | 変更のコミットとPR作成を一括実行 |
| `/push` | ✓ | 変更をコミットしてリモートにプッシュ |
| `/merge-pr` | ✓ | PRのコンフリクトチェック・CI確認・マージ |
| `/gemini-search` | ✓ | Gemini CLIを使用してWeb検索 |
| `/save-to-graph` | ✓ | graph-queueのデータをNeo4jに投入 |
