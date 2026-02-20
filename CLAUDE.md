# note-finance - note.com 金融記事作成・ニュース収集パイプライン

**Python 3.12+** | uv | Ruff | pyright | pytest

note.com での金融コンテンツ発信を効率化するパッケージ。

## パッケージ構成

| パッケージ | 説明 |
|------------|------|
| `rss` | RSSフィード管理（フィード監視・記事抽出・MCP統合） |
| `news` | ニュース処理パイプライン（収集・フィルタリング・GitHub投稿） |
| `automation` | 自動収集スクリプト |

## 主要コマンド

| コマンド | 説明 |
|----------|------|
| `/finance-suggest-topics` | 金融記事のトピックを提案 |
| `/new-finance-article` | 新規記事フォルダを作成 |
| `/finance-edit` | 記事編集ワークフロー（初稿→批評→修正） |
| `/finance-full` | 記事作成の全工程を一括実行 |
| `/generate-market-report` | 週次マーケットレポートを自動生成 |
| `/ai-research-collect` | AI投資バリューチェーン収集 |

## 開発コマンド

```bash
make check-all    # 全チェック（format, lint, typecheck, test）
make format       # フォーマット
make lint         # リント
make typecheck    # 型チェック
make test         # テスト
```
