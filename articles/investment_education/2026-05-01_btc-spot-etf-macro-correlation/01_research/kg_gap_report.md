# KGギャップレポート

**生成日**: 2026-05-07
**対象トピック**: 暗号資産現物ETF入門：BTC ETFとマクロ資産の相関を整理
**カテゴリ**: investment_education

## 既存データサマリー（research-neo4j）

| 項目 | 件数 | 備考 |
|------|------|------|
| Instrument: Bitcoin | 1ノード | 関連Fact 8件（うち実用的データ1件、研究用TDA/LPPLS論文由来 7件） |
| BTC現物ETF（IBIT/FBTC/GBTC等）| 0ノード | **完全な空白** |
| Topic: spot ETF | 0件 | 「ETF投資入門」など一般ETF Topicのみ |
| マクロ相関データ（BTC×SPX/Gold/DXY）| 0件 | **完全な空白** |
| 関連 Source（直近30日）| 0件 | 鮮度不足 |

直近の実用的Fact:
- 「ビットコインは3月18日に約71,359ドル（-4.3%）。暗号資産市場は『クリプトウィンター』状態で防衛的なセンチメントが継続」（時期不明・URLなし）

## 特定されたギャップ

| 種別 | 内容 | 優先度 |
|------|------|--------|
| no_coverage | BTC現物ETF（IBIT, FBTC, ARKB, BITB, HODL, BRRR, EZBC, BTCO, BTCW, GBTC）の Entity/Fact が0件 | HIGH |
| no_coverage | BTC ↔ S&P500/NASDAQ/Gold/DXY/UST の相関データ Fact が0件 | HIGH |
| stale_data | Bitcoin 関連 Source が直近30日内に0件 | HIGH |
| missing_financials | BTC現物ETF（米国 11銘柄）の AUM/フローデータ FDP が0件 | MEDIUM |
| open_questions | 「機関投資家の流入経路」「マクロ環境別の相関変化」が未整理 | MEDIUM |

## ギャップ解消用推奨検索クエリ

1. `Bitcoin spot ETF AUM 2026 IBIT FBTC inflows`
2. `Bitcoin S&P 500 correlation 2026 macro`
3. `Bitcoin gold correlation digital gold thesis 2026`
4. `Bitcoin DXY dollar correlation analysis 2026`
5. `BlackRock IBIT iShares Bitcoin Trust assets under management`
6. `現物ビットコインETF 米国 一覧 手数料 2026`
7. `ビットコイン マクロ 相関 株式 金 ドル`

## 結論

BTC現物ETFとマクロ相関というテーマはKG上ほぼ全く未開拓。本記事執筆を機にKGを大きく拡充する機会と位置づけ、Web検索を最優先で実行する。
