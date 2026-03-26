# 議論メモ: RSSフィード整理・スクリプトバグ修正

**日付**: 2026-03-26
**参加**: ユーザー + AI

## 背景・コンテキスト

RSSフィードから直近24時間の記事を取得・表示するスクリプト (`scripts/rss_recent_articles.py`) が
`FileNotFoundError` でクラッシュしていた。また、登録フィードの中に本文取得不可のものが多数含まれており整理が必要だった。

## 議論のサマリー

### 1. rss_recent_articles.py バグ修正

**原因**: データディレクトリの不一致

| | パス |
|---|---|
| MCPサーバー（正） | `/Volumes/personal_folder/scraped/rss/` |
| スクリプト（旧・誤） | `/Volumes/NeoData/note-finance-data/raw/rss/`（存在しない） |

MCPサーバーの `_get_data_dir()` はNAS優先ロジックを持つが、スクリプトは
`DATA_ROOT` 環境変数経由のパスをそのまま使っており、NASのパスと食い違っていた。

**修正**: `_get_rss_data_dir()` を追加し、MCPサーバーと同じ優先順位に統一。
```
RSS_DATA_DIR env → /Volumes/personal_folder/scraped/rss → DATA_ROOT fallback
```

### 2. フィード別本文取得状況調査

| 区分 | フィード例 | 本文 | 要約 |
|---|---|---|---|
| RSS全文含む | Ars Technica, The Verge, ZeroHedge | ✅ | ✅ |
| 要約のみ | CNBC, TechCrunch, HN, Federal Reserve | ❌ | ✅ |
| ペイウォール | FT (403), SA (ほぼ403) | ❌ | ❌ |
| 有料レポート | Yahoo Finance (Argus) | ❌ | ❌ |
| fetch不可 | NASDAQ (robots.txt接続エラー) | ❌ | ❌ |
| bot拒否 | Google News (ClaudeBot Disallow) | ❌ | ❌ |

### 3. 削除したフィード（計24本）

- Financial Times
- Yahoo Finance
- Seeking Alpha
- NASDAQ系 10種（Original/ETFs/Markets/Options/Stocks/AI/Financial Advisors/FinTech/Innovation/Technology）
- Google News系 9種（婚活/マッチング/副業/Webライター/NISA/暴落/資産形成/結婚相談所/副業月収）
- IMF News
- Trading Economics News

### 4. ZeroHedge追加

- URL: `https://feeds.feedburner.com/zerohedge/feed`
- カテゴリ: finance
- RSSの `<description>` に全文HTMLが含まれる（Ars Technica型）
- 非Premiumコンテンツは全文アクセス可能

## 決定事項

1. **ペイウォール/取得不可フィード24本を削除** — 本文取得不可のフィードを維持するコストに見合う価値がない
2. **rss_recent_articles.py のデータディレクトリ解決ロジックをMCPサーバーと統一**
3. **ZeroHedgeをfinanceカテゴリで追加** — RSSに全文含むため高品質

## 現在の登録フィード（27本）

| カテゴリ | フィード数 |
|---|---:|
| CNBC系 | 21 |
| TechCrunch | 1 |
| Ars Technica | 1 |
| The Verge | 1 |
| Hacker News (100+ points) | 1 |
| Federal Reserve Press Releases | 1 |
| ZeroHedge | 1 |

## アクションアイテム

なし（全て完了済み）

## 次回の議論トピック

- 本文が要約のみのフィード（CNBC等）に対して trafilatura フェッチを自動適用するか検討
- CNBC Markets フィードの形式不正（Invalid feed format）を調査・修正するか検討
- RSSフィードの定期フェッチを launchd 等で自動化するか検討
