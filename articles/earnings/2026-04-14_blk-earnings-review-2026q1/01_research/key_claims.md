# BLK Q1 2026 決算レビュー 中核主張リスト

> **注意**: 作成時点で Q1 2026 実績は未発表。以下は**プレビュー確度・コンセンサス情報・前期（Q4 2025）実績**に基づく暫定主張。実績発表後に `claim_type: financial_metric` の数値を更新すること。

---

## Claim 1: コンセンサスは AUM $14.21T、Revenue $6.62B、EPS $12.09 を見込む
- **claim_type**: financial_metric
- **sentiment**: neutral
- **magnitude**: AUM YoY +22.7%、Revenue YoY +25.5%、EPS YoY +7.0%
- **根拠**: Zacks Consensus Estimate（[Globe and Mail](https://www.theglobeandmail.com/investing/markets/stocks/BLK/pressreleases/1244848/blackrock-slated-to-report-q1-earnings-whats-in-the-cards/) / [FinancialContent](https://markets.financialcontent.com/stocks/article/marketminute-2026-4-10-blackrock-eyes-1206-eps-as-capital-markets-rebound-ignites-18-monthly-surge)）
- **記事での使い方**: 冒頭サマリーの指標テーブル。実績発表後は差分を即座に更新。

## Claim 2: Q4 2025 に AUM $14.04T を達成、資産運用業界初の$14T突破
- **claim_type**: financial_metric
- **sentiment**: positive
- **magnitude**: 業界初の快挙、FY2025純流入 $698B（過去最高）
- **根拠**: [BlackRock Q4 2025 Earnings Release PDF](https://s24.q4cdn.com/856567660/files/doc_financials/2025/Q4/BLK-4Q25-Earnings-Release.pdf)
- **記事での使い方**: Q1 2026 実績を解釈する「スタートライン」として言及。

## Claim 3: 2026は GIP/HPS/Preqin 統合の通年寄与が始まる初年度
- **claim_type**: strategy
- **sentiment**: positive
- **magnitude**: Private Markets セグメントが段階的にフルラン化、One BlackRock 体制で $14T を entry run-rate 化
- **根拠**: Larry Fink CEO Q4 2025 Earnings Call コメント（[BlackRock IR](https://s24.q4cdn.com/856567660/files/doc_financials/2025/Q4/BLK-4Q25-Earnings-Release.pdf)）
- **記事での使い方**: セグメント解説とガイダンスの接続。「通年寄与初年がどう立ち上がっているか」を軸に読む。

## Claim 4: プライベートクレジット市場で未曾有の解約要請、BlackRock 含む大手が解約停止権行使
- **claim_type**: market_reaction
- **sentiment**: negative
- **magnitude**: $1.8T 市場で投資家エクソダス、Apollo/BlackRock/Ares が redemption gate 発動
- **根拠**: [Bloomberg, 2026-04-13](https://www.bloomberg.com/news/articles/2026-04-13/why-investors-are-exiting-private-credit-markets)
- **記事での使い方**: HPS 統合の追い風シナリオに対する逆風として提示。決算資料でのディスクロージャー内容を注視。

## Claim 5: アナリストの90%がブル、コンセンサス目標株価 $1,300
- **claim_type**: market_reaction
- **sentiment**: positive
- **magnitude**: BofA $1,467、Deutsche Bank $1,380、Argus bullish、Morningstar neutral
- **根拠**: [Yahoo Finance アナリスト予想](https://finance.yahoo.com/research/stock-forecast/BLK/)、[Yahoo Finance EPS コンセンサス](https://finance.yahoo.com/news/blackrock-stock-analyst-estimates-ratings-133407172.html)
- **記事での使い方**: 株価水準（2026-04-06 時点 $966.56）との乖離を示し、決算後の re-rating 余地を論じる。

## Claim 6: 決算前株価は調整局面（1M -7.7%, 3M -10.4%, 6M -15.8%）
- **claim_type**: market_reaction
- **sentiment**: negative
- **magnitude**: 2月の -4.89% 下落以降軟調、関税・地政学リスク織込み
- **根拠**: `blk_reaction.json`（quants ヘルパー出力）、2026-04-06 preview リサーチ
- **記事での使い方**: 「期待値が下がった状態での決算」という文脈設定。ビートすればサプライズ大。

## Claim 7: 過去8四半期で3回 price divergence（EPSと株価の乖離）
- **claim_type**: market_reaction
- **sentiment**: neutral
- **magnitude**: 2025 Q3（-21% miss → +4.1% up）, Q2（+11.5% beat → -2.6% down）, 2024 Q1（+4.5% beat → -2.9% down）
- **根拠**: `blk_reaction.json` 直近8四半期データ
- **記事での使い方**: 「EPSサプライズだけでは株価は決まらない」という構造提示。読者に net inflows / guidance への注目を促す。

## Claim 8: FY2026 EPS コンセンサスは $53.64（YoY +11.5%）
- **claim_type**: guidance
- **sentiment**: positive
- **magnitude**: 二桁EPS成長継続、Q1実績を踏まえガイダンス改定の可能性
- **根拠**: [Yahoo Finance](https://finance.yahoo.com/news/blackrock-stock-analyst-estimates-ratings-133407172.html)
- **記事での使い方**: Q1 結果を踏まえた通年見通しの現実感を論じる。

## Claim 9: BlackRock Investment Institute は決算前日に US/EM 株式見通しを引き上げ
- **claim_type**: strategy
- **sentiment**: positive
- **magnitude**: 「戦争は終わった、利益は上向く」ロジックで risk-on 提示、S&P 500 Q1 +12.6% 予想を引用
- **根拠**: [CNBC, 2026-04-13](https://www.cnbc.com/2026/04/13/blackrock-raises-view-on-us-stocks-on-belief-that-war-is-over-profits-are-up.html)
- **記事での使い方**: Fink CEO の決算コメントと整合性を持つか検証。マクロスタンスと自社AUMフローの連動。

## Claim 10 (発表後追記想定): Q1 2026 実績の surprise 幅と株価反応
- **claim_type**: financial_metric / market_reaction
- **sentiment**: 発表後に判定
- **magnitude**: EPS サプライズ%、AUM beat/miss、day return
- **根拠**: 決算発表後の IR press release、CNBC/WSJ/Reuters 速報、SEC EDGAR 8-K
- **記事での使い方**: 本記事の結論部（「サプライズの構造」と「株価反応の合理性評価」）。

---

## 執筆時の論点整理

1. **二軸フレーム**: (a) EPS/AUM の数値ビート/ミス vs (b) プライベートクレジット懸念・ガイダンス変更の質的ファクター
2. **乖離パターンを活かす**: 単純な EPS surprise ではなく、**net inflows の質**（iShares vs プライベート vs キャッシュ）で読み解く
3. **CEO コメントの整合性**: 決算前日のブル転換と、Q1決算でのマクロ言及のズレ有無
4. **FY2026 run-rate**: $14T AUM を entry point に、通年EPS $53.64 が現実的か
