# 「米国マクロ経済」週次記事 設計書

> 作成日: 2026-04-08
> ステータス: 確定

## 基本仕様

| 項目 | 値 |
|---|---|
| シリーズ名 | **米国マクロ経済** |
| カテゴリ | macro_economy |
| type | column |
| 文字数 | **6,000字**（5,500〜6,500字を許容） |
| 公開曜日 | **毎週日曜** |
| トーン | **標準トーン**（客観的・分析的・です/ます調） |
| 対象読者 | 中級者 |

## トーンガイドライン

マリーさんトーンは使用しない。他カテゴリ記事（stock_analysis, financial_education等）と同じ標準トーン。

| 項目 | 採用する標準トーン |
|---|---|
| 主語 | 省略 or 「〜と考えられる」「〜と報告されている」 |
| 表現 | 「〜の可能性がある」「〜と予想される」 |
| 修辞疑問 | 使わない |
| 比喩 | 最小限 |
| 結論 | 事実整理 + シナリオ提示 |
| 構成 | テンプレート駆動 |

## 文字数配分

```
セクション                        文字数      固定/変動
──────────────────────────────────────────────────────
1. フック（タイトル+リード）        400-500字    変動
2. 今週のダッシュボード             500-600字    固定構造
3. メインテーマ深掘り            2,500-3,000字   変動
4. クレジット & 流動性              700-900字    固定構造
5. 来週の注目イベント               400-500字    変動
6. 今後の見通しと投資家への示唆      600-800字    変動
──────────────────────────────────────────────────────
合計                           5,100-6,300字
```

## メインテーマの決定ロジック

月の各週で発表される主要指標に連動:

| 月の週 | 主要発表 | メインテーマ |
|---|---|---|
| **第1週** | NFP, 失業率, 時給, ISM製造業/サービス業 | **雇用 & 景気の体力** |
| **第2週** | CPI(総合/コア), PPI, ミシガン大(速報) | **インフレの現在地** |
| **第3週** | 小売売上, 住宅着工, 鉱工業生産 | **消費 & 実体経済** |
| **第4週** | PCE(コア), GDP(四半期月), 耐久財, CB消費者信頼感 | **PCE・GDP & 消費者心理** |
| **FOMC週** | FOMC声明, ドットプロット, 議長会見 | **金融政策（最優先で上書き）** |

---

## セクション詳細

### 1. フック（タイトル+リード）── 400-500字

**タイトル形式**:
```
米国マクロ経済 vol.XX ─ {その週のキャッチーな一言}
```

**リード文の型**:
- その週で最もインパクトのある数字を1つ提示
- その数字が意味することを端的に述べる
- 記事で解き明かす論点を設定

```markdown
# 概要

3月の非農業雇用者数は前月比+30.3万人となり、
市場予想（+20万人）を大幅に上回った
（[出典: BLS](https://www.bls.gov/...)）。

しかし内訳を見ると、フルタイム雇用は2ヶ月連続で減少しており、
雇用の「質」に構造的な変化が起きている可能性がある。

本稿では雇用統計の内訳を分解し、
景気サイクル上の現在地を検証する。
```

**データソース**: FRED（PAYEMS, UNRATE, CES0500000003）

### 2. 今週のダッシュボード ── 500-600字

毎週同じフォーマット。定点観測。

**(A) マーケット概況テーブル（`/generate-table-image` で画像化）**

| 指標 | 今週終値 | 前週比 | 4週前比 |
|---|---|---|---|
| S&P 500 | X,XXX | +X.X% | +X.X% |
| VIX | XX.X | +X.X | +X.X |
| 米10年債利回り | X.XX% | +Xbp | +Xbp |
| 米2年債利回り | X.XX% | +Xbp | +Xbp |
| 長短金利差(10Y-2Y) | X.XX% | +Xbp | +Xbp |
| HYスプレッド | XXXbp | +Xbp | +Xbp |
| ドル指数 | XXX.X | +X.X% | +X.X% |

データソース:
- S&P 500, VIX → **yfinance**（quantsライブラリ経由、逐次取得）
- DGS10, DGS2, T10Y2Y, BAMLH0A0HYM2, DTWEXBGS → **FRED**（NAS経由）

**(B) イールドカーブチャート（`/generate-chart-image` で画像化）**

「今週 vs 前週 vs 4週前」の3本を重ねた折れ線グラフ:
- X軸: 1M, 3M, 6M, 1Y, 2Y, 3Y, 5Y, 7Y, 10Y, 20Y, 30Y
- Y軸: 利回り（%）
- 凡例: 今週（実線・濃色）、前週（破線）、4週前（点線・薄色）
- データ: **FRED** DGS1MO〜DGS30（NAS経由）

**(C) サマリーコメント（2-3行）**

カーブの形状変化、リスクオン/オフの状況を客観的に記述。

### 3. メインテーマ深掘り ── 2,500-3,000字

```
### {テーマ見出し}
    例: 「3月CPI ─ コアが再加速、利下げシナリオへの影響」
    例: 「雇用統計の内訳 ─ フルタイム雇用の減少が示すもの」
```

**3-a. ファクトの整理（What）── 600-800字**

- 発表された数字を正確に記述（**ソースURL必須**）
- 市場予想（コンセンサス）との比較
- 前月比・前年比のトレンド

**3-b. なぜこうなったか（Why）── 700-900字**

- 内訳の分解
  - CPI → 住居費 / エネルギー / 食品 / スーパーコア
  - NFP → セクター別（政府 / ヘルスケア / レジャー / 製造業）
  - GDP → 個人消費 / 設備投資 / 住宅 / 政府支出 / 純輸出の寄与度
- 構造的要因 vs 一時的要因の切り分け
- 過去3-6ヶ月のトレンドとの整合性

**3-c. 分析と考察（Analysis）── 800-1,000字**

- 他メディアが見落としている角度を客観的に提示
- 過去の類似局面との比較（定量的に）
- 複数の指標の整合性/矛盾の指摘

**3-d. チャート（`/generate-chart-image` で画像化、1-2枚）**

**デフォルト: 過去5年分（60ヶ月）をプロット**

| メインテーマ | チャート仕様 | 期間 |
|---|---|---|
| 雇用 | NFP月次推移（棒）+ 失業率（折れ線重ね） | 5年 |
| インフレ | CPI総合 / コア / スーパーコアの前年比推移 | 5年 |
| 消費・実体 | 小売売上 前月比（棒）+ 実質平均時給 前年比（折れ線） | 5年 |
| PCE/GDP | PCEコア vs CPIコアの乖離推移 / GDP寄与度分解 | 5年 |
| FOMC | FF金利実績 + yfinance先物からの織込みパス | 5年 + 先物分 |

**テーマ別データソース**:

| テーマ | データソース | 取得方法 |
|---|---|---|
| 雇用 | UNRATE, PAYEMS, CES0500000003, ICSA, JTSJOL, ADPMNUSNERSA | **FRED**（NAS経由） |
| インフレ | CPIAUCSL, PCEPILFE, T5YIE, T10YIE | **FRED**（NAS経由） |
| 消費・実体 | RSAFS, UMCSENT, MORTGAGE30US, HOUST | **FRED**（NAS経由） |
| PCE/GDP | PCEC, PCEPILFE, GDPC1, A191RL1Q225SBEA, GDPNOW | **FRED**（NAS経由） |
| FOMC | DFF, DGS2, DGS10, T10Y2Y | **FRED**（NAS経由） |
| FOMC織込み | Fed Funds先物（ZQ=F系列） | **yfinance**（逐次取得） |
| ISM PMI | — | **RSS** → 不足時のみ**Tavily** |
| COTデータ | CFTC Socrata SODA API | **SODA API**（逐次取得） |

### 4. クレジット & 流動性スナップショット ── 700-900字

毎週固定。全データ **FRED Weekly**（NAS経由）。

**4-a. 信用スプレッド ── 250-300字**

- IG（BAMLC0A0CM）/ HY（BAMLH0A0HYM2）スプレッドの週次変化と水準
- BBBスプレッド（BAMLC0A4CBBB）と BBスプレッド（BAMLH0A1HYBB）の差 → Fallen Angelリスクの温度計
- 変化が大きい週はCCC（BAMLH0A3HYC）にも言及

**4-b. 銀行貸出 & 流動性 ── 250-300字**

- 商工業貸出（TOTCI）→ 企業の資金需要
- 消費者ローン（CONSUMER）→ 個人消費の持続性
- 預貸率（TOTCI+REALLN+CONSUMER / DPSACBW027SBOG）→ 銀行の貸出意欲

**4-c. マネーサプライ & ストレス ── 200-250字**

- M2（M2SL）前年比伸び率 → 名目GDP成長率との比較で過剰/不足流動性を判定
- 金融ストレス指数（STLFSI4）→ 0超はストレス状態、0未満は平穏

### 5. 来週の注目イベント ── 400-500字

**テーブルではなく通常の文章**で記述。

各イベントについて:
- 発表日時（米国時間 + 日本時間を併記）
- なぜ注目か
- 上振れ/下振れ時の市場反応シナリオ

FOMC週の場合は声明文の発表時刻・会見の有無・ドットプロットの有無を明記。

**データソース**: **FRED releases/dates API**（経済指標カレンダー）+ **Fed RSS**（FOMC日程）

### 6. 今後の見通しと投資家への示唆 ── 600-800字

1. **現在地の整理（150-200字）**
   - 今週のデータが示す景気サイクル上のポジション
   - 拡大中期 / 拡大後期 / 減速初期 / 後退期 のどこにいるか

2. **シナリオ分岐（250-350字）**
   - 楽観シナリオ: 前提条件と想定される展開
   - 悲観シナリオ: 前提条件と想定される展開
   - 各シナリオの条件を定量的に明示

3. **投資家への示唆（200-250字）**
   - 環境認識に基づく考え方の方向性
   - 具体的な売買推奨は行わない
   - 「〜が有効と考えられる」「〜に注意が必要である」の表現

免責: 記事末尾にdisclaimer挿入

---

## meta.yaml テンプレート

```yaml
article_id: "2026-XX-XX_us-macro-weekly-volXX"
topic: "米国マクロ経済 vol.XX ─ {サブタイトル}"
category: macro_economy
type: column
series: us_macro_weekly
series_volume: XX
target_audience: intermediate
target_wordcount: 6000
fred_series:
  # ダッシュボード（毎週固定 7系列）
  - DGS10
  - DGS2
  - T10Y2Y
  - BAMLH0A0HYM2
  - VIXCLS
  - DTWEXBGS
  - SP500
  # イールドカーブ（毎週固定 11系列）
  - DGS1MO
  - DGS3MO
  - DGS6MO
  - DGS1
  - DGS3
  - DGS5
  - DGS7
  - DGS20
  - DGS30
  # クレジット&流動性（毎週固定 10系列）
  - BAMLC0A0CM
  - BAMLC0A4CBBB
  - BAMLH0A1HYBB
  - BAMLH0A3HYC
  - TOTCI
  - CONSUMER
  - DPSACBW027SBOG
  - M2SL
  - STLFSI4
  - DFF
  # メインテーマ（週により変動、以下から選択）
  # 雇用:    UNRATE, PAYEMS, CES0500000003, ICSA, JTSJOL, ADPMNUSNERSA
  # インフレ: CPIAUCSL, PCEPILFE, T5YIE, T10YIE
  # 消費:    RSAFS, UMCSENT, MORTGAGE30US, HOUST
  # GDP:     GDPC1, A191RL1Q225SBEA, GDPNOW
status: draft
```

## 画像一覧（毎号で生成）

| # | 種類 | ファイル名 | 固定/変動 |
|---|---|---|---|
| 1 | テーブル | `table_dashboard.png` | 固定構造 |
| 2 | チャート | `chart_yield_curve.png`（今週/前週/4週前） | 固定構造 |
| 3 | チャート | `chart_main_theme.png`（過去5年） | 変動 |
| 4 | チャート | `chart_main_theme_2.png`（過去5年、任意） | 変動 |

---

## データソースアーキテクチャ

```
Mac mini (launchd)                          NAS (/Volumes/personal_folder)
┌──────────────────────┐                   ┌──────────────────────┐
│ com.quants.fred-sync │──── 毎日06:00 ───→│ data/raw/fred/       │
│ (65+9系列を自動取得)  │                   │  indicators/         │
│                      │                   │   DGS10.json         │
│ com.finance.news-*   │──── 定期実行 ────→│   GDPNOW.json        │
│ (RSS収集+neo4j投入)  │                   │   RSAFS.json         │
│                      │                   │   ...                │
└──────────────────────┘                   └──────────┬───────────┘
                                                      │ NAS mount
                                                      ↓
                                           このPC (記事執筆環境)
                                           ┌──────────────────────┐
                                           │ note-finance         │
                                           │  HistoricalCache()   │
                                           │   → NAS上のJSONを読む │
                                           │                      │
                                           │ yfinance (逐次取得)  │
                                           │   → S&P500, VIX      │
                                           │   → Fed Funds先物    │
                                           │                      │
                                           │ CFTC SODA API(逐次)  │
                                           │   → COTデータ        │
                                           │                      │
                                           │ FRED releases/dates  │
                                           │   → 経済指標カレンダー │
                                           │                      │
                                           │ 記事生成 → note.com  │
                                           └──────────────────────┘
```

### データソース全体像

```
データ取得レイヤー:
┌─────────────────────────────────────────────────────┐
│  FRED (NAS経由)            ← 全指標の主軸           │
│  ・ダッシュボード 7系列 (Daily)                      │
│  ・イールドカーブ 11系列 (Daily)                     │
│  ・クレジット&流動性 10系列 (Weekly)                 │
│  ・メインテーマ 6-10系列 (Monthly/Quarterly)         │
│  ・経済指標カレンダー (releases/dates API)           │
│  取得: Mac miniのlaunchd → NAS保存 → このPCで読込   │
├─────────────────────────────────────────────────────┤
│  yfinance (quantsライブラリ経由)  ← 市場価格        │
│  ・S&P 500, VIX                                     │
│  ・Fed Funds先物 (ZQ=F) ← FedWatch代替             │
│  取得: 記事生成時に逐次取得                          │
├─────────────────────────────────────────────────────┤
│  CFTC Socrata SODA API    ← COTデータ               │
│  ・認証不要、JSON直取得、毎週金曜更新                │
│  取得: 記事生成時に逐次取得                          │
├─────────────────────────────────────────────────────┤
│  Fed RSS                  ← FOMC                    │
│  ・press_monetary.xml (声明文)                       │
│  ・speeches.xml (Fed高官発言)                        │
│  取得: Mac miniのlaunchd → research-neo4jに蓄積      │
├─────────────────────────────────────────────────────┤
│  Tavily (フォールバック)  ← 2指標のみ               │
│  ・ISM PMI (月1回)                                   │
│  ・Conference Board消費者信頼感 (月1回)              │
│  取得: 記事生成時にオンデマンド                       │
└─────────────────────────────────────────────────────┘
```

## fred_series.json 追加系列（quantsプロジェクト側）

以下の9系列を `/Users/yukihata/desktop/quants/data/config/fred_series.json` に追加:

| FRED ID | 名称 | 頻度 | カテゴリ（既存に追加） |
|---|---|---|---|
| GDPNOW | GDPNow | 随時 | Business & Economic Activity |
| RSAFS | 小売売上高 | Monthly | Business & Economic Activity |
| HOUST | 住宅着工件数 | Monthly | Business & Economic Activity |
| PERMIT | 建設許可件数 | Monthly | Business & Economic Activity |
| DGORDER | 耐久財受注 | Monthly | Business & Economic Activity |
| HSN1F | 新築住宅販売 | Monthly | Business & Economic Activity |
| PCEPILFE | PCEコアデフレーター | Monthly | Business & Economic Activity |
| A191RL1Q225SBEA | GDP成長率（前期比年率） | Quarterly | Developed Countries - Real GDP Level |
| ADPMNUSNERSA | ADP雇用統計 | Monthly | Population, Employment, & Labor Force |

## rss-presets.json 追加フィード（note-finance側）

以下の2件を `data/config/rss-presets.json` に追加（source_id: "fed-imf"）:

```json
{
    "url": "https://www.federalreserve.gov/feeds/press_monetary.xml",
    "title": "FRB Monetary Policy Statements",
    "category": "macro",
    "source_id": "fed-imf",
    "fetch_interval": "daily",
    "enabled": true
},
{
    "url": "https://www.federalreserve.gov/feeds/speeches.xml",
    "title": "FRB Speeches",
    "category": "macro",
    "source_id": "fed-imf",
    "fetch_interval": "daily",
    "enabled": true
}
```

## 新規構築（note-finance側）

| コンポーネント | 内容 | 取得タイミング |
|---|---|---|
| CFTC COTコレクター | Socrata SODA API、`requests` + `pandas` | 記事生成時に逐次取得 |
| Fed Funds先物コレクター | yfinance ZQ=F系列 | 記事生成時に逐次取得 |
| FRED releases/dates | fredapi経由で翌週の指標カレンダー取得 | 記事生成時に逐次取得 |

## 週次制作フロー

```
金曜夜   [Mac mini] FRED自動同期済み（毎日06:00）
         [Mac mini] RSS自動収集済み → research-neo4j
土曜午前  [このPC] NAS経由でFREDデータ読込
         [このPC] yfinanceでS&P500, VIX, Fed Funds先物を逐次取得
         [このPC] CFTC SODA APIでCOTデータを逐次取得
         [このPC] チャート自動生成（ダッシュボード・イールドカーブ・メインテーマ5年チャート）
         [このPC] FRED releases/dates APIで翌週の経済指標カレンダーを取得
土曜午後  [このPC] /article-draft で初稿生成（テーマ判定→メインテーマ選択）
         ISM/CB発表週のみ Tavily で速報値を補完
土曜夜   人間がセクション3-c（分析と考察）とセクション6を仕上げ
日曜     [このPC] /article-publish で note.com に投稿
```
