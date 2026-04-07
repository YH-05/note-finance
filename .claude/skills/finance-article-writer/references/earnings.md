# earnings（決算プレビュー）

## 文字数

- **目標**: 4000-5000字
- **最低**: 3500字
- **最大**: 5500字

## 対象読者

中級者。決算発表カレンダーをウォッチし、EPS/売上サプライズに関心のある個人投資家を想定する。

## ポジショニング

**決算発表の「前」に読む記事**。発表済み決算の振り返りではなく、発表 3-5 日前の銘柄について、事前予想・過去実績トレンド・注目ポイントを整理する。

## データソース

記事執筆に使用するデータソースと取得方法。

### ヘルパースクリプト（記事執筆前に実行）

| スクリプト | 用途 | 実行例 |
|---|---|---|
| `scripts/fetch_earnings_8k.py` | SEC EDGAR 8-K（EX-99.1）プレスリリース取得 | `uv run python scripts/fetch_earnings_8k.py --symbol BLK --quarters 8` |
| `scripts/analyze_earnings_reaction.py` | 決算前後株価反応分析 + リターン算出 | `uv run python scripts/analyze_earnings_reaction.py --symbol BLK --quarters 8` |
| `scripts/generate_earnings_chart.py` | 株価 + 累積リターン 2段チャート生成 | `PYTHONPATH=scripts uv run --with yfinance python scripts/generate_earnings_chart.py --article-dir articles/earnings/{slug}` |

**`generate_earnings_chart.py` の仕様（2026-04-08 更新）**:

- **推奨実行方法**: `--article-dir` を指定するだけで完結。`01_research/*_reaction.json` を自動探索し、出力先を `images/chart_price_1y.png` に自動設定する
- **上段（株価）**: シンプルなラインチャート。決算日に赤丸マーカー + 矢印アノテーションを配置
- **下段（累積リターン）**: 銘柄（緑実線）と S&P500＝SPY（グレー破線）を重ね描き。面プロットなし。決算日アノテーションは描画しない
- **アノテーションなし**: `--no-annotations` フラグで明示的に無効化できる

### データソース優先順位

| 優先 | ソース | 取得方法 | 記事での用途 |
|---|---|---|---|
| 1 | **NASDAQ Calendar DB** | `nasdaq_calendar.db` / `nc_earnings_calendar` | 発表日・BMO/AMC・EPS予想 |
| 2 | **SEC EDGAR 8-K** | `fetch_earnings_8k.py`（REST API直接） | 過去四半期の GAAP/Adjusted EPS・AUM・フロー・CEOコメント・乖離要因 |
| 3 | **yfinance API** | `analyze_earnings_reaction.py`（都度取得・6年分） | リターン（1M〜5Y）・決算前後株価反応・モメンタムチャート |
| 4 | **AV Earnings DB** | `alphavantage.db` / `av_earnings` | 過去 EPS サプライズ履歴（ビート/ミス傾向） |
| 5 | **AV Company Overview DB** | `alphavantage.db` / `av_company_overview` | 企業概要・セクター・バリュエーション（取得済み銘柄のみ） |
| 6 | **SEC EDGAR 財務DB** | `sec_edgar.db` / `se_financial_statements` | 財務5指標（revenue/net_income/total_assets/total_liabilities/operating_cashflow） |
| 7 | **Web 検索** | Tavily / WebSearch | 最新ニュース・アナリスト反応・カタリスト・リスク情報の補完 |

**重要**:
- 財務データは SEC EDGAR を優先使用する。Alpha Vantage の income/balance/cashflow はレート制限の都合で意図的に未収集のため、参照しない
- yfinance は DB（1年分）を使わず、都度 API 取得（6年分）する
- AV earnings / overview は 28 / 20 銘柄のみ。未取得銘柄は Web 検索で補完する

## セクション構成（6セクション）

```markdown
# {企業名} ({ティッカー}) 決算プレビュー — {発表予定日}

## 1. 銘柄概要
[Pencil 表で基本情報を一覧化]

## 2. 今回の決算ポイント
[発表概要 + カタリスト + 着目KPI]

## 3. 過去の決算実績
[直近8四半期のサプライズ・株価反応・要因の一覧表]
[乖離パターンの文章解説]

## 4. 株価パフォーマンス
[1年チャート + 決算前後反応パターン]

## 5. リスク要因
[ダウンサイドシナリオ — 両面提示]

## 6. まとめ
[中立的総括 — 買い/売り推奨は行わない]

---

## 参考データソース
[使用した全データソースのリスト]

{snippets/disclaimer.md の全文を挿入}
```

### セクション別ガイドライン

#### 1. 銘柄概要（目安: 300-500字 + Pencil表）

Pencil MCP で以下の項目を含む表を作成する:

| 項目 | データソース |
|---|---|
| 企業名 / ティッカー | av_company_overview or Web |
| 企業概要（1-2行） | av_company_overview.description or Web |
| セクター / インダストリー | av_company_overview or Web |
| 時価総額 | av_company_overview or yfinance |
| 株価（最新終値） | yfinance（都度取得） |
| 配当（1株配当 / 利回り） | yfinance or av_company_overview |
| PER（実績 / 予想） | av_company_overview or Web |
| リターン（1M, 3M, 6M, 1Y, 3Y, 5Y） | `analyze_earnings_reaction.py` 出力 |
| EPS予想（今期コンセンサス） | nc_earnings_calendar |
| 発表日時 / BMO・AMC | nc_earnings_calendar |

→ 表は Pencil で作成。Pencil が使えない場合は `/generate-table-image` で画像化。

#### 2. 今回の決算ポイント（目安: 800-1200字）

以下を統合して1セクションにまとめる:

- **発表スケジュール**: 発表日・BMO/AMC・会計四半期・EPS/売上コンセンサス予想
- **カタリスト**: 今期の主要イベント・ビジネスドライバー（Web検索で取得）
- **注目KPI**: この銘柄固有の注目指標（例: BLKならAUM成長率・ETFフロー・テック収益比率）
- **コンセンサスの温度感**: アナリストの見方（強気/弱気のバランス）

#### 3. 過去の決算実績（目安: 1200-1500字 + 表）

**最も差別化されるセクション**。2つの要素で構成する:

**A. 一覧表**（`/generate-table-image` で画像化）

| 決算期 | 発表日 | EPS実績 | EPS予想 | サプライズ% | 翌日リターン | 週間リターン | 要因 |
|---|---|---|---|---|---|---|---|
| 2025 Q4 | 1/15 | $13.16 | $12.19 | +8.0% | +6.5% | +3.9% | 記録的AUM $14T、純流入$342B |

- データ: `analyze_earnings_reaction.py` 出力の `earnings_reactions` + `fetch_earnings_8k.py` 出力の `highlights`
- 要因列: 8-K プレスリリースのハイライトから1行で要約

**B. 乖離パターン解説**（文章）

サプライズ方向と株価反応が不一致の四半期について、**なぜ乖離したか**を文章で解説する。

解説すべきパターン:
- **ビートなのに下落**: ガイダンス慎重化、バリュエーション過熱、マクロ悪化等
- **ミスなのに上昇**: GAAP/Adjusted乖離（一時費用）、AUM/フロー好調、ガイダンス上方修正等

要因の調査手段:
1. `fetch_earnings_8k.py` の highlights（GAAP/Adjusted EPS乖離、AUM、CEOコメント）
2. Web検索（アナリスト反応、市場環境、セクター要因）

全四半期を解説する必要はない。**乖離が大きい回（`divergence: true`）のみ深掘り**する。

#### 4. 株価パフォーマンス（目安: 500-800字 + チャート）

- **チャート生成**: `generate_earnings_chart.py --article-dir {article_dir}` で生成（推奨）
  - 上段: 5年株価推移（ラインチャート）+ 決算日の赤丸マーカー・矢印アノテーション
  - 下段: 銘柄累積リターン vs S&P500（SPY）の比較ライン
- 決算前後の株価反応パターン: 直近8四半期の翌日リターンの傾向
- ボラティリティの傾向（決算前に上がりやすい/下がりやすい等）

#### 5. リスク要因（目安: 400-600字）

中立性維持のため必須セクション。以下の観点:

- **決算ミス時のダウンサイドシナリオ**
- **セクター/マクロリスク**（金利環境、規制、競合等）
- **バリュエーションリスク**（PER水準が過熱している場合）

→ 両面提示を徹底。アップサイドの可能性にも触れる。

#### 6. まとめ（目安: 200-300字）

- 中立的な総括
- 今回の決算で最も注目すべきポイントの再確認
- 免責事項（`snippets/disclaimer.md`）

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

## 記事執筆フロー

```
1. 銘柄選定
   nc_earnings_calendar から発表3-5日前の銘柄を特定
   EPS予想がある + 時価総額が一定以上の銘柄を優先

2. データ収集（ヘルパースクリプト実行）
   uv run python scripts/analyze_earnings_reaction.py --symbol {SYMBOL} --quarters 8
   uv run python scripts/fetch_earnings_8k.py --symbol {SYMBOL} --quarters 8

3. 補完データ取得
   av_company_overview / se_financial_statements を SQLite から取得
   Web検索でカタリスト・リスク情報・アナリスト反応を補完

4. 記事執筆
   references/earnings.md（このファイル）のセクション構成に従い執筆
   表は /generate-table-image、チャートは /generate-chart-image で画像化
   Pencil が使える場合は銘柄概要テーブルを Pencil で作成

5. 品質チェック
   下記チェックリストを確認
```

## チェックリスト

- [ ] 発表日時（BMO/AMC）が記事冒頭で明示されている
- [ ] EPS/売上コンセンサス予想が明記されている
- [ ] 銘柄概要テーブルが作成されている（Pencil or 画像）
- [ ] 過去8四半期のサプライズ・リターン・要因の一覧表が画像化されている
- [ ] サプライズと株価の乖離パターンが文章で解説されている
- [ ] 1年株価チャートが画像化されている
- [ ] 買い/売り推奨・目標株価・「ビートする/ミスする」の予測断定がない
- [ ] リスク要因セクションがある（両面提示）
- [ ] データは SEC EDGAR を優先使用している（AV income/balance/cashflow を参照していない）
- [ ] `as_of_date` がフロントマターに記載されている
- [ ] 根拠データにソースURLが埋め込まれている
- [ ] マークダウン表が記事内に残っていない（全て画像化済み）
