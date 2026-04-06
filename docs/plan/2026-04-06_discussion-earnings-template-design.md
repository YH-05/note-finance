# 議論メモ: 決算プレビュー記事テンプレート詳細設計

**日付**: 2026-04-06
**参加**: ユーザー + AI
**Discussion ID**: `disc-2026-04-06-earnings-template-design`
**前回議論**: `disc-2026-04-05-earnings-category-creation`

## 背景・コンテキスト

前回（2026-04-05）で earningsカテゴリ新設・コマンド更新・暫定スキャフォールド作成まで完了。今回はテンプレート詳細設計（act-2026-04-05-001）とデータ取得設計（act-2026-04-05-002）を進める。

## データソース調査結果（最新）

### quants SQLite DB（NAS蓄積）

| DB | テーブル | 行数 / 銘柄数 | 記事での用途 |
|---|---|---|---|
| nasdaq_calendar.db | nc_earnings_calendar | 410行（3/30〜4/20） | 発表スケジュール・EPS予想 |
| sec_edgar.db | se_financial_statements | 525行 / 267銘柄 | 財務5指標（直近1-2期のみ） |
| yfinance.db | yf_daily_prices | 73,131行 / 299銘柄 / 1年 | **記事では使わない（都度取得に変更）** |
| alphavantage.db | av_earnings | 1,761行 / 28銘柄 | EPSサプライズ履歴 |
| alphavantage.db | av_company_overview | 20銘柄 / 46カラム | 企業概要・バリュエーション |

### AV earnings / overview の食い違い

- av_earnings 28銘柄、av_overview 20銘柄
- 原因: AV無料枠 25 calls/day をearningsとoverviewが食い合い、片方だけfailedになる
- 両方取得済み: **15銘柄**（うち未発表は7銘柄、全て4/14発表）
- 結論: AV由来データは「あればラッキー」の補足情報として扱う

### BLK（BlackRock）を試作候補に選定

- 4/14発表、BMO、EPS予想$12.16
- av_earnings 106レコード + av_overview 取得済み = データ最豊富
- 直近20四半期: ビート18回 / ミス2回（ビート率90%）

## 決定事項

### 1. yfinance は DB を使わず都度 API 取得（dec-2026-04-06-yfinance-realtime）

- `yfinance.Ticker(symbol).history(period='6y')` で6年分を都度取得
- 1M, 3M, 6M, 1Y, 3Y, 5Y リターンを算出可能（検証済み）
- DBの1年分データでは3Y/5Yが計算不可能なため

### 2. 記事セクション構成を6セクションに確定（dec-2026-04-06-section-structure）

1. **銘柄概要** — Pencil表で基本情報・バリュエーション・リターンを一覧化
2. **今回の決算ポイント** — カタリスト + 着目ポイントを統合
3. **過去の決算実績** — EPSサプライズ履歴 + 乖離パターン解説
4. **株価パフォーマンス** — チャート + 決算前後の株価反応パターン
5. **リスク要因** — ダウンサイドシナリオ（中立性維持）
6. **まとめ** — 中立的総括 + 免責

### 3. 過去の決算実績セクションの設計（dec-2026-04-06-earnings-history-design）

- 対象: **直近8四半期**
- 表の列: サプライズ方向・率、決算期間リターン（前日→翌日 / 前5日→後5日）、要因
- 各四半期のサプライズ方向と株価反応の乖離を**文章でも解説**
- 要因分析にはSEC EDGAR 8-K（EX-99.1プレスリリース）を使用
  - GAAP/Adjusted EPS の乖離要因
  - AUM・Net Inflows
  - CEOコメント（Larry Fink）
  - 主要イベント（M&A等）
- 8-Kで不足する背景情報はWeb検索で補完

### 4. SEC EDGAR 8-K は REST API 直接アクセス（dec-2026-04-06-sec-edgar-rest-api）

MCPツール（`analyze_8k`）は使わず、ヘルパースクリプトでREST API直接アクセスする。

**選定理由**:
- MCPツールはPythonスクリプトから呼べない
- REST APIは認証不要（User-Agentヘッダーのみ）
- HTMLをHTMLParserで構造的にパース可能（ASCIIアート除去不要）
- `days` パラメータ上限がなく、全四半期アクセス可能
- ヘルパースクリプトとして独立実行可能

**処理フロー**:
```
Step 1: submissions API で accession_number を特定
  GET https://data.sec.gov/submissions/CIK{cik}.json
  → form_type='8-K' でフィルタ

Step 2: filing ディレクトリから EX-99.1 URL を特定
  GET https://www.sec.gov/Archives/edgar/data/{cik}/{accession}/
  → "ex99_1.htm" を正規表現で抽出

Step 3: EX-99.1 プレスリリース HTML を取得
  GET https://www.sec.gov/.../blk-ex99_1.htm
  → HTML 5.6MB

Step 4: HTML → プレーンテキスト変換
  HTMLParser でタグ除去 → 134KB クリーンテキスト

Step 5: ハイライト抽出 → 構造化 JSON 出力
  先頭 5KB にキー情報集約（EPS, AUM, Inflows, CEO Quote）
```

**検証結果（BLK Q3 2025）**:
- 8-Kディレクトリ: `blk-ex99_1.htm` を正常発見
- HTML→テキスト変換: 5.6MB → 134KB
- ハイライト先頭5KBにGAAP/Adjusted EPS, Net Inflows $205B, CEO引用すべて含有

**BLK Q3 2025 乖離パターンの実例**:
- GAAP EPS $8.43（予想$10.73を-21.4%ミス）→ 株価は翌日+4.1%上昇
- 原因: GIP/HPS買収の非現金費用でGAAP歪み。Adjusted EPS $11.55は実質ビート
- 実態: $205B純流入（iShares過去最高）、オーガニック手数料成長率10%

### 5. 銘柄概要テーブルの掲載項目（dec-2026-04-06-overview-table）

Pencilで表を作成。以下のフィールドを含む:

- 企業名、ティッカー、企業概要
- 時価総額、セクター、インダストリー
- 株価（最新終値）
- 配当（1株配当、配当利回り）
- リターン: 1M, 3M, 6M, 1Y, 3Y, 5Y
- EPS予想（今期コンセンサス）
- 発表日時、BMO/AMC

データソース:
- yfinance API（都度取得）: 株価、リターン、配当
- nc_earnings_calendar: 発表日、EPS予想、BMO/AMC
- av_company_overview: 時価総額、セクター、インダストリー、PER等（取得済み銘柄のみ）
- Web検索: av_overviewが未取得の銘柄の基本情報補完

## アクションアイテム

| # | Action ID | 内容 | 優先度 |
|---|---|---|---|
| 1 | act-2026-04-06-001 | references/earnings.md を本設計版に更新（6セクション構成、データソース、8-K活用フロー反映） | 高 |
| 2 | act-2026-04-06-002 | SEC EDGAR 8-K プレスリリース取得ヘルパースクリプト作成（REST API → HTML → テキスト → JSON） | 高 |
| 3 | act-2026-04-06-003 | 決算前後株価反応分析ヘルパースクリプト作成（yfinance都度取得 + av_earnings突合） | 高 |
| 4 | act-2026-04-06-004 | BLK（4/14発表）で `/article-full --category earnings` 初回試作 | 中 |
| 5 | act-2026-04-06-005 | Pencil で銘柄概要テーブルテンプレート作成 | 中 |

## 次回の議論トピック

1. **references/earnings.md 本設計版のレビュー**
   - 6セクション構成の文字数配分
   - 各セクションのライティングガイドライン
   - 中立性ルールの具体例

2. **ヘルパースクリプトの詳細設計**
   - 出力JSONスキーマの確定
   - article-research からの呼び出しインターフェース
   - エラーハンドリング（8-K未提出、EX-99.1形式違い等）

3. **銘柄選定ロジック**
   - 3-5日前銘柄のうち、どの基準で記事化対象を絞るか
   - 1日あたりの投稿本数

## 参考情報

- SEC EDGAR REST API: `https://data.sec.gov/submissions/CIK{cik}.json`
- BLK CIK: `2012383`（新持株会社）/ `1364742`（旧）
- EX-99.1 URL例: `https://www.sec.gov/Archives/edgar/data/2012383/000119312525237960/blk-ex99_1.htm`

## 保存先

| リソース | パス |
|---|---|
| note-neo4j Discussion | `disc-2026-04-06-earnings-template-design` |
| note-neo4j Decision | `dec-2026-04-06-yfinance-realtime`, `dec-2026-04-06-section-structure`, `dec-2026-04-06-earnings-history-design`, `dec-2026-04-06-sec-edgar-rest-api`, `dec-2026-04-06-overview-table` |
| note-neo4j ActionItem | `act-2026-04-06-001` 〜 `act-2026-04-06-005` |
| ドキュメント | `docs/plan/2026-04-06_discussion-earnings-template-design.md`（このファイル） |
