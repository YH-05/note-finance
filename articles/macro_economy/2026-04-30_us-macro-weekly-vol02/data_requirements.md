# vol.2 データ要件 — PCE と CPI の乗離分析

**作成日**: 2026-04-27
**vol.2 公開予定**: 2026-04-30夜（Q1 GDP速報リリース後 = PCE 3月分も同日リリース見込み）

## ⚠️ データ可用性の事実訂正

`collect_us_macro_data.py` 実行結果から、**3月PCEは本記事作成時点（2026-04-27 月）では未公表**であることが判明。

| 指標 | 当初認識 | 実際 |
|---|---|---|
| Personal Income and Outlays（PCE含む） | 4/26公表済（誤り） | **latest=2026-04-09（2月PCE）**、次回推定 4/30 |
| Q1 GDP速報 | 4/30公表予定 | 4/30公表予定（変わらず） |

**結論**: PCE 3月分とGDP Q1速報は **2026-04-30 同時リリース予定**（BEAの慣例）。vol.2 公開予定の 4/30 夜は引き続き有効。今日（4/27）はインフラ整備とデータ系列リストアップに集中する。

## 中心論点: PCE と CPI の乗離

### 構造的に乗離する3つの理由

1. **ウエイト付け方式の違い**
   - CPI: ラスパイレス式（固定ウエイト、年1更新）
   - PCE: フィッシャー式（毎期動的更新、消費代替を反映）
2. **住居費の扱い**
   - CPI: 住居費ウエイト ≒ 33%（自家持家者にOERを適用）
   - PCE: 住居費ウエイト ≒ 16%（市場家賃を中心）
3. **医療費の扱い**
   - CPI: 消費者の自己負担分のみ
   - PCE: 雇用主負担+政府負担+保険会社負担を含む包括的計上

### 必要データ系列

#### Tier 1（記事の核 — 必須）

| FREDコード | 説明 | 頻度 | 取得期間 | 用途 |
|---|---|---|---|---|
| **PCEPI** | PCE価格指数（総合） | 月次 | 過去5年 | 主軸チャート（PCE-CPI 時系列乗離） |
| **PCEPILFE** | コアPCE価格指数 | 月次 | 過去5年 | コア乗離の中心 |
| **CPIAUCSL** | CPI（総合、季節調整済） | 月次 | 過去5年 | PCE 比較対象 |
| **CPILFESL** | コアCPI | 月次 | 過去5年 | コア乗離の中心 |

#### Tier 2（深掘り用 — 強く推奨）

| FREDコード | 説明 | 頻度 | 用途 |
|---|---|---|---|
| **CUSR0000SAH1** | CPI 住居費（Shelter） | 月次 | 住居費ウエイト差の説明 |
| **CUSR0000SEMC01** | CPI 帰属家賃（OER） | 月次 | 自家持家ウエイトの中身 |
| **CUSR0000SEMD01** | CPI 主家賃 | 月次 | 借家市場の動向 |
| **DPCERG3M086SBEA** | PCE 価格指数: Housing | 月次 | PCE側の住居費 |
| **CPIMEDSL** | CPI 医療費 | 月次 | 医療費ウエイト差の説明 |
| **DHLCRG3M086SBEA** | PCE 価格指数: Health Care | 月次 | PCE側の医療費 |

#### Tier 3（スーパーコア論点 — vol.1 から転用）

| FREDコード | 説明 | 頻度 | 用途 |
|---|---|---|---|
| **CUSR0000SASLE** | CPI Services less energy services and shelter（スーパーコア） | 月次 | スーパーコア vs Fed採用指標 |
| ※TBD | PCE版スーパーコア（FRBの "supercore" 定義） | 月次 | 4/29 までに FRED から該当系列を確定（SHELTER除外PCEサービス） |

#### Tier 4（補助 — メインテーマ全般）

| FREDコード | 説明 | 頻度 | 用途 |
|---|---|---|---|
| **GDPC1** | 実質GDP水準 | 四半期 | GDP水準の長期トレンド |
| **A191RL1Q225SBEA** | 実質GDP前期比年率 | 四半期 | Q1 速報の比較 |
| **GDPNOW** | アトランタ連銀GDPNow | リアルタイム | 速報の事前推計 |
| **UMCSENT** | ミシガン大消費者信頼感（確報） | 月次 | 4月確報を使用 |
| ※CB Consumer Confidence | CB消費者信頼感 | 月次 | 4/29発表予定の4月分を取り込み |

#### Tier 5（補助補助 — 必要に応じて）

| FREDコード | 説明 | 頻度 | 用途 |
|---|---|---|---|
| **PCE** | 名目PCE | 月次 | 価格 vs 名目 vs 実質の対比 |
| **PCEC96** | 実質PCE | 月次 | 実質消費の動向 |
| **DPCERA3M086SBEA** | 実質PCE価格指数 | 月次 | チェーン式の確認 |
| **CES0500000003** | 実質平均時給 | 月次 | スーパーコア論点での賃金推進インフレ |

## チャート要件

| # | チャート種別 | データ系列 | 期間 | 出力先 |
|---|---|---|---|---|
| 1 | 折れ線（メインチャート） | コアPCE vs コアCPI 前年同月比 | 過去5年 | images/chart_pce_cpi_yoy.png |
| 2 | 棒グラフ（寄与度分解） | コアCPI - コアPCE の構成要因（住居費・医療費・その他） | 直近12ヶ月 | images/chart_pce_cpi_decomp.png |
| 3 | 折れ線（消費者心理） | ミシガン大 vs CB Consumer Confidence | 過去5年 | images/chart_consumer_sentiment.png |
| 4 | 折れ線（スーパーコア） | コアPCE vs コアCPI vs スーパーコアCPI | 過去5年 | images/chart_supercore.png |
| 5 | 棒グラフ（GDP寄与度） | Q1 GDP の構成（PCE/設備投資/在庫/純輸出/政府支出） | Q1 2026 | images/chart_gdp_contribution.png |

## 4/27〜4/30 のタスクスケジュール

| 日付 | タスク |
|---|---|
| **4/27（今日）** | ✅ 記事フォルダ作成、collect_us_macro_data.py 実行、quants fred_series.json に9系列追加、data_requirements.md 作成 |
| 4/28-29 | スーパーコア定義の最終確定（Tier 3 のPCE版該当系列を FRED から特定）、Tier 1-2 系列の取得実装 |
| 4/29 | CB Consumer Confidence（4月）公表 → Tier 4 取り込み |
| **4/30 朝** | Q1 GDP速報・3月PCE 同時リリース → 取得・チャート生成 |
| **4/30 夜** | vol.2 初稿執筆 → 批評 → 修正 → 公開 |

## 関連リンク

- vol.2 議論メモ: `docs/plan/SideBusiness/2026-04-27_discussion-us-macro-vol02-design.md`
- 設計書本体: `docs/plan/2026-04-08_us-macro-weekly-article-design.md`
- データコレクター: `scripts/collect_us_macro_data.py`
- quants fred_series.json: `/users/yukihata/desktop/quants/data/config/fred_series.json`
