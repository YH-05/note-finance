# 発表後の株価反応 — JPMorgan Q1 2026

---

## 日次推移（2026年4月）

| 日付 | 終値（USD） | 前日比 | イベント |
|---|---|---|---|
| 2026-04-11（金） | 309.87* | — | プレビュー記事発行時点 |
| 2026-04-13（月） | 313.39 | +1.14% | — |
| 2026-04-14（火） | **311.03** | -0.75% | **決算発表（BMO）** |
| 2026-04-15（水） | 約 313-314（推定・週次データ）| 小幅上昇 | BAC決算、他行比較 |
| 2026-04-16（木、本日朝） | 305.93**（analyze_earnings_reaction.pyより）| -2.3%程度 | — |

*プレビュー記事本文より
**`scripts/analyze_earnings_reaction.py` 2026-04-16 実行時の `current_price`。ただし同スクリプトは Q1 2026決算反応をまだ反映しておらず、Q4 2025データを返している点に注意

出典: [Yahoo Finance JPM Historical Prices](https://finance.yahoo.com/quote/JPM/history)

---

## 発表当日（4/14）のイントラデー動向

- **プレマーケット初動**: 決算ヘッドライン出た瞬間に +1%（$5.94 vs $5.45 のEPS大幅ビートを反映、[CNBC Premarket](https://www.cnbc.com/2026/04/14/stocks-making-the-biggest-moves-premarket-nvo-jpm-ual.html)）
- **その後プレマーケットで反落**: NIIガイダンス引き下げ判明後に **-2.6%** まで下落（[Barron's](https://www.barrons.com/livecoverage/jpmorgan-chase-bofa-citigroup-wells-fargo-bank-earnings/card/jpmorgan-s-profit-rises-13-tops-wall-street-expectations-QmHW9TRyOqHtVJvax44y), [Seeking Alpha](https://seekingalpha.com/news/4574690-jpmorgan-chase-q1-earnings-beat-but-nii-outlook-trimmed)）
- **寄り付き後**: 損失縮小、終値 $311.03（前日比 -0.75%）で着地

## 評価のポイント

1. **市場の優先順位**: EPS/売上の大幅ビート（EPS+9%、売上+2.8%サプライズ）よりも、**「NIIガイダンス引き下げ」を重く見た**
   - Seeking Alpha見出し: 「Q1 earnings beat, but NII outlook trimmed」
2. **MarketWatchの解釈**: 「JPMorgan's markets and investment banking revenue surge, but here's why the stock is pulling back」([MarketWatch](https://www.marketwatch.com/story/jpmorgans-markets-and-investment-banking-revenue-surge-but-heres-why-the-stock-is-pulling-back-2e03575f))
3. **ただし下落は限定的**: -2.6%→終値 -0.75% と、売られすぎを買い戻す動きが発生

## YTD（2026年初来）パフォーマンス

- 4/13時点で年初来 **-3.6%**（[Barron's](https://www.barrons.com/livecoverage/jpmorgan-chase-bofa-citigroup-wells-fargo-bank-earnings/card/jpmorgan-s-profit-rises-13-tops-wall-street-expectations-QmHW9TRyOqHtVJvax44y)）
- S&P 500 は同期間 +0.4% → JPMはアンダーパフォーム
- Reuters: 「JPMorgan, Bank of America and Wells Fargo are all trading in red so far in 2026, underperforming the broader S&P 500 index」（[Reuters](https://www.reuters.com/sustainability/boards-policy-regulation/bank-america-profit-rises-trading-shines-2026-04-15/)）
- 銀行セクター全体が2026年YTDで軟調

---

## セクター比較（同週の大手銀行決算）

| 銘柄 | 発表日 | EPS実績 vs 予想 | 株価反応 |
|---|---|---|---|
| Goldman Sachs（GS） | 4/13（月） | Beat — IB/株式トレ過去最高 | +（上昇） |
| **JPMorgan（JPM）** | **4/14（火）** | **$5.94 vs $5.45（+9%Beat）** | **-0.75%** |
| Wells Fargo（WFC） | 4/14（火） | 売上・NIIミス | ラガード扱い |
| Citigroup（C） | 4/14（火） | Beat（$5B利益） | 18年ぶり高値圏 |
| Bank of America（BAC） | 4/15（水） | EPS $1.01コンセンサス、Beat報道 | +（上昇） |

出典: [CNBC Earnings Playbook](https://www.cnbc.com/2026/04/12/earnings-playbook-jpm-nflx-kick-off-the-reporting-season.html)、[Reuters BofA](https://www.reuters.com/sustainability/boards-policy-regulation/bank-america-profit-rises-trading-shines-2026-04-15/)、[NYT](https://www.nytimes.com/2026/04/14/business/jpmorgan-wells-fargo-citi-earnings.html)

---

## アナリスト反応

- **Hightower の Stephanie Link**: 「JPMorgan's Q1 was really amazing」（強気、[CNBC](https://www.cnbc.com/video/2026/04/14/jpmorgans-q1-was-really-amazing-says-hightowers-stephanie-link.html)）
- **Bespoke の Paul Hickey**: 「Economy not derailed by energy shocks so market is looking past it」（市場のエネルギーショック織り込み済み、[CNBC](https://www.cnbc.com/video/2026/04/15/economy-not-derailed-by-energy-shocks-so-market-is-looking-past-it-says-bespokes-paul-hickey.html)）
- **Fundstrat の Tom Lee**: 「The war is actually helping earnings right now」（逆説的解釈、[CNBC](https://www.cnbc.com/video/2026/04/14/jpmorgan-chase-reports-q1-2026-revenue-eps-beats-in-first-quarter-earnings.html)）

個別アナリストの目標株価変更（アップグレード/ダウングレード）については、発表当日〜2営業日の期間中に主要メディアでは一斉ダウングレード/アップグレードは観測されていない。Seeking Alphaがquick insightsで「outperformance in Q1 earnings helps mitigate concerns」としており、中立的スタンスが多数派。

---

## 注意事項（データ欠落）

- `scripts/analyze_earnings_reaction.py` はAlpha Vantage API経由のEPSデータ更新を待っており、**Q1 2026決算反応が reactions 配列に未反映**（fiscal_quarter: 2025-Q4 のみ）
- 4/15、4/16 の明示的な終値・出来高は複数検索でピンポイント取得できず。レビュー記事執筆時は「4/14の -0.75%」と「週間の銀行セクタートレンド」に焦点を絞るのが安全
- 発表後48時間でアナリストの目標株価変更集計は**まだ公開データベース化されていない**可能性が高い。Tipranks/Zacks等の集計は通常数日ラグ
