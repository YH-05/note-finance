# 検索クエリテンプレート集

週次マーケットレポート、記事リサーチ、仮説検証などで使用する検索クエリのテンプレート集。

## プレースホルダ構文

| プレースホルダ | 説明 | 例 |
|--------------|------|-----|
| `{TICKER}` | 銘柄ティッカー | NVDA, AAPL, 7203.T |
| `{TICKER2}` | 比較対象ティッカー | AMD, MSFT |
| `{YYYY}` | 年 | 2026 |
| `{Q}` | 四半期番号 | 1, 2, 3, 4 |
| `{PERIOD}` | 期間表現 | "January 2026", "Q1 2026", "this week" |
| `{KEYWORD_JA}` | 日本語キーワード | 米国株, 半導体 |
| `{SECTOR}` | セクター名 | technology, energy, healthcare |
| `{INDICATOR}` | 経済指標名 | CPI, PMI, GDP |

## 言語戦略

| 言語 | 用途 | 理由 |
|------|------|------|
| 英語（デフォルト） | グローバル市場情報、米国株、マクロ経済 | 情報量が圧倒的に多い |
| 日本語 | 国内市場、個人投資家動向、日本固有テーマ | 国内メディア・note.com調査 |

各テンプレートファイルでは英語クエリをデフォルトとし、日本語クエリは明示的に「日本語クエリ」セクションに配置。

## サイト指定（`site:` 演算子）

よく使うサイト指定:

| サイト | 演算子 | 用途 |
|--------|--------|------|
| Bloomberg | `site:bloomberg.com` | 市場ニュース、企業分析 |
| Reuters | `site:reuters.com` | 速報、マクロ経済 |
| CNBC | `site:cnbc.com` | 市場コメンタリー |
| 日経 | `site:nikkei.com` | 日本市場、企業ニュース |
| note.com | `site:note.com` | 競合コンテンツ調査 |
| Seeking Alpha | `site:seekingalpha.com` | 個別銘柄分析 |
| Yahoo Finance | `site:finance.yahoo.com` | 市場データ、ニュース |

## フォールバック戦略

検索結果が不十分な場合の段階的アプローチ:

1. **具体 → 一般**: `"{TICKER} Q{Q} {YYYY} earnings revenue"` → `"{TICKER} earnings {YYYY}"` → `"{TICKER} financial results"`
2. **英語 → 日本語**: `"{TICKER} earnings analysis"` → `"{TICKER} 決算 分析"`
3. **サイト指定 → 全体検索**: `"site:bloomberg.com {query}"` → `"{query}"`
4. **期間限定 → 期間拡大**: `"{query} {PERIOD}"` → `"{query} {YYYY}"`

## テンプレートファイル一覧

| ファイル | 内容 | 主な用途 |
|---------|------|---------|
| `index-market.md` | 株価指数・市場全体 | 週次レポート、市場概況 |
| `individual-stocks.md` | 個別銘柄 | 銘柄分析、決算レビュー |
| `macro-economy.md` | マクロ経済 | FOMC、経済指標、為替 |
| `sectors.md` | セクター別 | セクターローテーション分析 |
| `ai-tech.md` | AI・テクノロジー | AI投資テーマ、半導体 |
| `japan-market.md` | 日本市場特化 | 国内市場、NISA、個人投資家 |
| `competitor-content.md` | 競合コンテンツ調査 | note.com記事企画、ギャップ発見 |

## 使用例

```
# 仮説検証: NVIDIAの急騰要因を調査
クエリ: "NVIDIA AI GPU demand datacenter January 2026"
フォールバック: "NVDA news catalyst this week"

# 週次レポート: 市場全体の動向
クエリ: "S&P 500 weekly performance January 2026"
補助: "stock market rally selloff January 2026"

# 記事企画: 競合調査
クエリ: "site:note.com 米国株 2026"
```
