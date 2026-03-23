# 議論メモ: 情報収集ソース全量棚卸し

**日付**: 2026-03-23
**参加**: ユーザー + AI

## 背景・コンテキスト

「全てのNeo4jデータベースはプロジェクトの知識そのもの。任意のデータ収集方法で集められた情報は須くNeo4jに投入されなければならない」という根本原則に基づき、現存する全情報収集ソースを棚卸しし、Neo4j投入パイプラインの接続状況を確認した。

## 情報収集ソース一覧

### 1. RSS フィード（50フィード登録済み）

| カテゴリ | ソース | 数 | Neo4j投入 |
|---------|--------|---|-----------|
| 米国金融ニュース | CNBC | 21 | 接続済み（finance-news-workflow） |
| 米国マーケット | NASDAQ, Seeking Alpha, Investing.com | 10 | 接続済み |
| 米国マクロ | FRB, IMF, Trading Economics | 3 | 接続済み |
| テック | HN, TechCrunch, Ars Technica, The Verge | 4 | 接続済み |
| **日本 金融・マクロ** | 金融庁, 日銀, 大和総研, JPX, 財務省, 東洋経済, Japan Times | 12 | **未接続** |
| **日本 貿易** | JETRO | 2 | **未接続** |
| Wealth/資産形成ブログ | Mr. Money Mustache 等 | 18 | 接続済み（wealth-scrape） |
| **体験談DB用** | Google News (婚活/副業/資産形成) | 9 | **未接続** |

### 2. API 連携

| ソース | MCP | Neo4j投入 |
|--------|-----|-----------|
| SEC Edgar | sec-edgar-mcp | web-research経由 |
| Reddit | reddit MCP | reddit-finance-topics経由 |
| arXiv | alphaxiv MCP | academic-fetch経由 |
| **Wikipedia** | wikipedia MCP | **未接続** |

### 3. Web検索

| ツール | Neo4j投入 |
|--------|-----------|
| Tavily MCP | web-research経由 |
| Gemini Search | web-research経由 |
| WebFetch | web-research経由 |

### 4. PDF変換

| ソース | Neo4j投入 |
|--------|-----------|
| セルサイドレポート | pdf-extraction経由 |
| 決算資料 | pdf-extraction経由 |
| リサーチペーパー | pdf-extraction経由 |

### 5. 定量データ

| ソース | 設定 | Neo4j投入 |
|--------|------|-----------|
| **yfinance** | yfinance_tickers.json | **未接続**（週次レポートのみ） |
| **FRED** | fred_series.json | **未接続**（週次レポートのみ） |

### 6. 業界リサーチ

| ソース | Neo4j投入 |
|--------|-----------|
| **McKinsey, BCG, Goldman Sachs** | **未接続** |
| **Gartner, IDC, Forrester** | **未接続** |

### 7. AI投資バリューチェーン

| ソース | Neo4j投入 |
|--------|-----------|
| 77社・10カテゴリ | ai-research-collect経由 |

## 特定されたギャップ（Neo4j未接続）

| ギャップ | 影響 | 優先度 |
|---------|------|--------|
| JP RSS (14フィード) | 日本市場の知識がNeo4jに入らない | 高 |
| yfinance/FRED 定量データ | FinancialDataPointが手動PDF経由のみ | 高 |
| Wikipedia 背景情報 | Entity充填率9.6%の一因 | 中 |
| 業界リサーチ (6社) | セクター分析が限定的 | 低 |
| 体験談DB RSS (9フィード) | creator-neo4j側の課題 | 低 |

## アクションアイテム

- [ ] JP RSS → Neo4j投入パイプライン構築 (優先度: 高)
- [ ] yfinance/FRED → FinancialDataPoint投入パイプライン構築 (優先度: 高)
- [ ] Wikipedia → Entity充填パイプライン構築 (優先度: 中)
- [ ] 業界リサーチ → Neo4j投入パイプライン構築 (優先度: 低)

## 次回の議論トピック

- 各ギャップの実装順序と工数見積もり
- yfinance/FREDデータのスキーマ設計（FinancialDataPoint/FiscalPeriod/Metricとの統合）
- JP RSSをfinance-news-workflowに統合するか、別パイプラインにするか
