# earnings（決算プレビュー）

> **注意**: このテンプレートは設計中です。最終版は今後詳細設計されます。
> 以下は初期スキャフォールドとしての暫定ルールです。

## 文字数

- **目標**: 4000-5000字
- **最低**: 3500字
- **最大**: 5500字

## 対象読者

中級者。決算発表カレンダーをウォッチし、EPS/売上サプライズに関心のある個人投資家を想定する。

## ポジショニング

**決算発表の「前」に読む記事**。発表済み決算の振り返りではなく、発表 3-5 日前の銘柄について、事前予想・過去実績トレンド・注目ポイントを整理する。

## データソース優先順位

記事内のデータは以下を優先して使用する:

1. **nasdaq_calendar.db / nc_earnings_calendar** — 発表日・発表時間（BMO/AMC）・EPS コンセンサス予想
2. **sec_edgar.db / se_financial_statements** — 過去 annual/quarterly の財務5指標（revenue, net_income, total_assets, total_liabilities, operating_cashflow）
3. **yfinance.db / yf_daily_prices** — 直近1年の日次 OHLCV（モメンタム・ボラティリティ算出用）
4. **alphavantage.db / av_earnings** — 過去 EPS サプライズ履歴（ビート/ミス傾向）
5. **alphavantage.db / av_company_overview** — 会社概要・セクター・アナリストレーティング（取得済み銘柄のみ）
6. **Web 検索** — 最新ニュース・セルサイドレポート・コンセンサス更新による補完

**重要**: 財務データは SEC EDGAR を優先使用する。Alpha Vantage の income/balance/cashflow はレート制限の都合で意図的に未収集のため、参照しない。

## セクション構成テンプレート（暫定）

```markdown
# {企業名} ({ティッカー}) 決算プレビュー — {発表予定日}

# 発表概要
[発表日時、BMO/AMC、会計四半期、EPS/売上コンセンサス予想]
→ 表は /generate-table-image で画像化

# 企業概要
[事業内容、セクター、直近の主要トピック]

# 過去実績トレンド
[直近 4-8 四半期の売上・純利益推移、YoY/QoQ、マージン]
→ 表は /generate-table-image で画像化
→ 推移グラフは /generate-chart-image で画像化

# EPS サプライズ履歴
[直近 4-8 四半期のビート/ミス履歴、サプライズ率]
→ 表は /generate-table-image で画像化

# 株価モメンタム
[決算発表前 1-3 ヶ月の株価推移、ボラティリティ、過去決算時の値動き]
→ チャートは /generate-chart-image で画像化

# 今回の注目ポイント
[事前予想のポイント、コンセンサスの分布、マクロ・セクター環境、ガイダンス観点]

# リスク要因
[ミス時の下振れ要因、セクター/マクロリスク — 両面提示]

# まとめ
[中立的な総括 — 買い/売り推奨は行わない]

---

## 参考データソース
- NASDAQ Earnings Calendar
- SEC EDGAR (10-K/10-Q)
- Yahoo Finance
- Alpha Vantage
- {その他 Web ソース}

{snippets/disclaimer.md の全文を挿入}
```

## カテゴリ固有ルール

### 中立性の維持

決算プレビューでは特に投資助言規制に注意する。

- **禁止**: 「ビートする見込み」「ミスする可能性が高い」等の予測断定
- **禁止**: 「買い」「売り」「ホールド」などのレーティング付与
- **禁止**: 目標株価の提示
- **推奨**: コンセンサス予想とトラックレコードを提示し、判断は読者に委ねる
- **推奨**: アップサイドとダウンサイドのシナリオを両面提示する

### データの鮮度

- EPS コンセンサス・発表日時は NASDAQ calendar DB の最新値を使用
- 財務データは SEC EDGAR の直近報告書を参照
- 株価データは yfinance の直近日を確認し、記事内に `as_of_date` を明記

### フロントマター

```yaml
---
title: "{企業名} ({ティッカー}) 決算プレビュー"
article_id: {article_id}
category: earnings
symbol: {ティッカー}
earnings_date: {YYYY-MM-DD}
announcement_time: {BMO|AMC}
as_of_date: {YYYY-MM-DD}
status: draft
---
```

## チェックリスト

- [ ] 発表日時（BMO/AMC）が記事冒頭で明示されている
- [ ] EPS/売上コンセンサス予想が明記されている
- [ ] 過去実績トレンド（最低4四半期）が画像化されている
- [ ] EPS サプライズ履歴が画像化されている
- [ ] 買い/売り推奨・目標株価・「ビートする/ミスする」の予測断定がない
- [ ] リスク要因セクションがある（両面提示）
- [ ] データは SEC EDGAR を優先使用している（AV income/balance/cashflow を参照していない）
- [ ] `as_of_date` がフロントマターに記載されている
