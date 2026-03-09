# 金融記事管理ダッシュボード

> **プラットフォーム**: note.com
> **最終同期**: 2026-03-09

---

## コンテンツカテゴリ

### 運用中ワークフロー

| ワークフロー | コマンド | 説明 |
|-------------|---------|------|
| 週次マーケットレポート | `/generate-market-report` | 指数・セクター・MAG7のデータ収集→レポート生成 |
| 金融ニュース収集 | `/collect-finance-news` | RSS→テーマ分類→GitHub Issue作成 |
| 資産形成コンテンツ | `/asset-management` | JP RSSソース→note記事+X投稿 |
| AI投資リサーチ | `/ai-research-collect` | 77社・10カテゴリのAI投資バリューチェーン |

### 記事執筆ワークフロー

| ステップ | コマンド |
|---------|---------|
| 1. トピック提案 | `/finance-suggest-topics` |
| 2. フォルダ作成 | `/new-finance-article` |
| 3. 編集（初稿→批評→修正） | `/finance-edit` |
| 4. 全工程一括 | `/finance-full` |
| 5. note.com投稿 | `/publish-to-note` |

## Neo4j 記事関連データ

| ノード種別 | 件数 | 説明 |
|-----------|------|------|
| Source | 693 | RSS/記事ソース |
| Claim | 686 | 主張・事実 |
| Entity | 72 | 企業・人物・概念 |
| Topic | 16 | トピック分類 |
| FinancialProduct | 7 | 金融商品 |
| Article | 1 | 公開記事 |

## GitHub Project

- **Project #15**: 金融ニュース管理
- **Project #44**: AI投資バリューチェーン

## 関連リンク

- [[news/_weekly-digest|週次ニュースダイジェスト]]
- [[../_dashboard|全体ダッシュボード]]
