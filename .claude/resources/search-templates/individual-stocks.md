# 個別銘柄 検索クエリテンプレート

## 決算関連

四半期決算の結果、ガイダンス、コンセンサス比較を調査する。

| クエリ | ユースケース |
|--------|-------------|
| `"{TICKER} earnings Q{Q} {YYYY} results"` | 四半期決算の結果 |
| `"{TICKER} revenue guidance outlook {PERIOD}"` | 売上高ガイダンス・見通し |
| `"{TICKER} EPS beat miss consensus {PERIOD}"` | EPSのコンセンサス比較 |
| `"{TICKER} earnings call transcript Q{Q} {YYYY}"` | 決算説明会のトランスクリプト |
| `"{TICKER} earnings surprise reaction"` | 決算サプライズと株価反応 |
| `"{TICKER} quarterly results breakdown segment"` | セグメント別決算内訳 |
| `"{TICKER} full year {YYYY} guidance forecast"` | 通期ガイダンス |

## カタリスト

株価を動かすイベントや材料を調査する。

| クエリ | ユースケース |
|--------|-------------|
| `"{TICKER} news catalyst {PERIOD}"` | 直近のカタリスト |
| `"{TICKER} analyst upgrade downgrade {PERIOD}"` | アナリスト評価の変更 |
| `"{TICKER} product launch announcement {PERIOD}"` | 新製品発表 |
| `"{TICKER} partnership deal acquisition {PERIOD}"` | 提携・買収 |
| `"{TICKER} FDA approval trial results"` | FDA承認・治験結果（バイオ） |
| `"{TICKER} contract win government"` | 大型契約の獲得 |
| `"{TICKER} management CEO change"` | 経営陣の交代 |
| `"{TICKER} stock split buyback dividend"` | 株式分割・自社株買い・配当 |

## バリュエーション

銘柄の割安・割高判断に使う指標を調査する。

| クエリ | ユースケース |
|--------|-------------|
| `"{TICKER} valuation PE ratio forward {YYYY}"` | フォワードPER |
| `"{TICKER} price target consensus analyst"` | コンセンサス目標株価 |
| `"{TICKER} DCF intrinsic value analysis"` | DCF・本質的価値分析 |
| `"{TICKER} PEG ratio growth valuation"` | PEGレシオ |
| `"{TICKER} EV EBITDA multiple comparison"` | EV/EBITDA倍率 |
| `"{TICKER} free cash flow yield"` | フリーキャッシュフロー利回り |
| `"{TICKER} overvalued undervalued analysis"` | 割高・割安判断 |

## 競合比較

同業他社との比較を行う。

| クエリ | ユースケース |
|--------|-------------|
| `"{TICKER} vs {TICKER2} comparison {YYYY}"` | 2銘柄の直接比較 |
| `"{TICKER} market share industry {PERIOD}"` | 市場シェア・業界内ポジション |
| `"{TICKER} competitive advantage moat"` | 競争優位性・経済的堀 |
| `"{TICKER} peers relative performance {PERIOD}"` | ピアグループとの相対パフォーマンス |
| `"{TICKER} industry ranking position"` | 業界内ランキング |

## テクニカル分析

チャートパターンやテクニカル指標を確認する。

| クエリ | ユースケース |
|--------|-------------|
| `"{TICKER} technical analysis chart {PERIOD}"` | テクニカル分析 |
| `"{TICKER} support resistance level"` | サポート・レジスタンス水準 |
| `"{TICKER} moving average golden cross death cross"` | ゴールデンクロス・デッドクロス |
| `"{TICKER} short interest days to cover"` | 空売り残高 |
| `"{TICKER} options unusual activity volume"` | オプション異常取引量 |

## 日本語クエリ

日本語での銘柄情報を確認する。

| クエリ | ユースケース |
|--------|-------------|
| `"{TICKER} 決算 {PERIOD}"` | 決算情報（日本語） |
| `"{TICKER} 株価 分析 {PERIOD}"` | 株価分析（日本語） |
| `"{TICKER} 投資判断 レーティング"` | 投資判断（日本語） |
| `"{TICKER} 業績 見通し {YYYY}"` | 業績見通し（日本語） |
| `"{TICKER} 株主還元 配当 自社株買い"` | 株主還元策（日本語） |
