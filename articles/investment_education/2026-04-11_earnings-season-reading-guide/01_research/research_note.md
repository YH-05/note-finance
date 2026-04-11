# リサーチノート：決算シーズンの読み方フレームワーク

## 記事情報
- **タイトル**: 決算シーズンの読み方：EPS・売上・ガイダンス3軸スコアリングフレームワーク
- **カテゴリ**: investment_education
- **ターゲット**: 初心者投資家
- **作成日**: 2026-04-11

---

## 1. タイムリー背景：Q1 2026決算シーズン開幕

- JPMorgan Chase（JPM）が2026年4月14日（火）、市場開始前にQ1 2026決算を発表予定
- これがQ1 2026決算シーズンの事実上のスタート
- Forbes（2026-04-07）：「Big Banks, Bigger Profits: Earnings Season Kicks Off Next Week」
- S&P 500企業の決算発表は1月・4月・7月・10月の中旬が集中期
- **出典**: [JPMorgan Chase Earnings Preview](https://finance.yahoo.com/markets/stocks/articles/jpmorgan-chase-earnings-preview-expect-144841270.html)、[Forbes](https://www.forbes.com/sites/mayrarodriguezvalladares/2026/04/07/big-banks-bigger-profits-earnings-season-kicks-off-next-week/)

---

## 2. 3軸スコアリングの基本

### 軸1：EPS（1株当たり利益）

#### EPSとは
- EPS = 純利益 ÷ 発行済み株式数
- **Diluted EPS**（希薄化後EPS）が市場で最も重視される
  - ストックオプション・転換社債等の潜在株式を含む
  - Basic EPSより厳しい数字 → より正確な1株利益を反映
- **Adjusted EPS**（調整後EPS / Non-GAAP EPS）も重要
  - 一時的な損益を除外した「実力値」
  - アナリスト予想はほとんどAdjusted EPSベース
  - Apple・Amazon・Metaはこれを通常発表しない（GAAP重視）

#### Beat/Miss の判定
- **Beat**: 実際のEPS > アナリストコンセンサス → 好材料
- **Miss**: 実際のEPS < コンセンサス → 悪材料
- ポイント: **前年同期比の成長率**との組み合わせで評価

#### 具体例（KGデータから）
- AMD Q4 2025: EPS $1.53 vs コンセンサス $1.24 → Beat（+23.4%）
- Micron Q2 FY2026: EPS $12.20 vs コンセンサス $9.00 → Beat（大幅超過）
- **出典**: research-neo4jの既存ファクトデータ（AMD, Micron）

### 軸2：売上高（Revenue）

#### 見るべきポイント
1. **実績 vs コンセンサス予想**: Beatかどうか
2. **YoY成長率（前年同期比）**: 成長トレンドの確認
3. **オーガニック売上成長**: M&Aの影響を除いた内部成長
   - 米国では企業合併・事業売却が多いため重要
4. **セグメント別売上**: どの事業が牽引しているか

#### 純利益の成長率 vs 売上成長率
- 純利益成長率 > 売上成長率 → 収益性が高まっている（投資家に好材料）
- EPSはこの比較に最適な指標
- **出典**: [moomoo 米株決算で真っ先に見るべきポイント](https://www.moomoo.com/jp/learn/detail-summary-of-the-first-points-you-should-look-at-in-us-stock-financial-results-116747-230910056)

### 軸3：ガイダンス（Forward Guidance）

#### ガイダンスとは
- 次の四半期または通期の業績見通しを経営陣が発表
- アナリスト予想（コンセンサス）との比較が重要
- **最も株価を動かす軸**（将来の期待を左右するため）

#### 米国企業のガイダンス形式
- ハイテク系：次の四半期のレンジ表示（例：$9.5B～$10.0B）
- 変動が小さい企業：通期のレンジ表示
- 発表場所：①決算リリース（Outlook欄）②決算説明会資料 ③口頭のみ、と企業で異なる
- **プロフィットウォーニング**: ガイダンスと乖離が大きい場合に事前警告
  - 悪いときだけでなく、上振れ時も「ウォーニング」という
- **出典**: [SBI証券 銘柄レポート・決算リリースの基礎知識](https://go.sbisec.co.jp/media/report/fo_senryaku/fo_senryaku_260325.html)

---

## 3. Beat-and-Raise / Beat-and-Lower パターン

### 4パターンの整理

| EPS/売上 | ガイダンス | パターン名 | 株価反応の典型 |
|---------|-----------|-----------|--------------|
| Beat | 上方修正（Raise） | **Beat-and-Raise** | 急騰 ↑↑ |
| Beat | 据え置き（Maintain） | Beat-and-Hold | 小幅高か横ばい |
| Beat | 下方修正（Lower） | **Beat-and-Lower** | 下落 ↓（好決算でも売られる） |
| Miss | 下方修正（Lower） | **Miss-and-Lower** | ガラ ↓↓ |

### 「好決算なのに株価下落」の理由

#### Buy the rumor, Sell the news
- 期待先行で株価が既に上昇済み → 決算発表で出尽くし売り
- 「ウィスパーナンバー」（非公式の期待値）がコンセンサスより高い場合
  - 公式コンセンサスを超えても、非公式期待値を下回ると売られる

#### ガイダンス失望
- EPSは勝っても、次期ガイダンスがコンセンサスを下回ると急落
- Snap（2022年4-6月期）：売上13%増も次期ガイダンスなし → 翌日39%暴落
- Nvidia（2025年）：ガイダンス引き上げも株価終値-3%（AI不安が背景）

#### ペナルティの非対称性
- Forbes調査：「Miss」のペナルティ > 「Beat」の報酬（非対称）
- アルゴリズム取引：「コンセンサスをX%超えたら買い/売り」が自動実行
- **出典**: [Forbes - The Dysfunctional Earnings Game](https://www.forbes.com/sites/georgecalhoun/2025/11/30/the-case-against-quarterly-reporting--part-2-the-earnings-game/)、[Investopedia - Why Stocks Drop After Positive News](https://www.investopedia.com/ask/answers/06/stockdeclinegoodnews.asp)

---

## 4. Conference Callの注目ポイント

### 構成
1. **オープニング**: IRまたは司会者による注意事項
2. **経営陣プレゼン**: CEO/CFOの業績説明・ガイダンス提示
3. **Q&Aセッション**: アナリストからの質問 ← **最重要パート**

### Q&Aで読むべき「経営の本音」

#### 注目ポイント
- **アナリストが何を聞くか** = 市場の関心事が分かる
- **CEOの自信の度合い** ← ただし米国は文化的に強気プレゼンが標準
  - 日本人が聞くと「会社が潰れる直前まで力強く聞こえる」（Fund Garage）
- **CFOが売上やマージンをどう説明するか**
- **回避的・曖昧な回答** → レッドフラグ

#### 聴く際のポイント
- **録音/トランスクリプトが公開される** → Yahoo Finance等で後から確認可能
- 発表翌日の時間外取引の反応も確認
- **出典**: [Investopedia - How To Listen to Earnings Calls Like an Investor](https://www.investopedia.com/small-business/what-is-an-earnings-conference-call/)、[Fund Garage 米国企業の決算発表](https://fundgarage.com/stock/post-0-80/)

### 決算発表の時間帯（米国）
- **市場開始前（7:00〜9:00 ET）**: 東海岸本社企業（JPMorgan等）
- **市場終了後（16:00〜17:00 ET）**: 西海岸本社企業（GAFA等ハイテク）
- 「市場終了後」発表 → **翌日の開幕に影響**（時間外取引の反応を事前チェック）
- **出典**: [SBI証券](https://go.sbisec.co.jp/media/report/fo_senryaku/fo_senryaku_260325.html)

---

## 5. 日本株の決算短信との違い

### 比較表

| 項目 | 米国（8-K / 10-Q） | 日本（決算短信） |
|------|------------------|----------------|
| 業績予想の形式 | レンジ表示（$x〜$y） | ピンポイント単一値 |
| 会計基準 | GAAP（Non-GAAP調整あり） | 日本GAAP（特別損益除外なし） |
| 会計年度の名前 | 終了月基準（FY2026=1月期） | 開始月基準（2025年度=4月期） |
| 重視する利益指標 | Adjusted EPS / GAAP EPS | 営業利益・経常利益 |
| カンファレンスコール | 完全公開（誰でも聴ける） | 機関投資家向けが中心 |
| 発表タイミング | 四半期末後1〜2ヶ月 | 四半期末後30〜45日 |

### 会計年度の命名に注意
- NVIDIAの「FY27」= 2027年1月期（2027年1月終了）
- 日本企業「2025年度」= 2026年3月終了（開始年で命名）
- **出典**: [SBI証券](https://go.sbisec.co.jp/media/report/fo_senryaku/fo_senryaku_260325.html)

### 日本株の決算チェックポイント
- **本決算**: 着地よりも「来期予想」が重要 → 増収増益予想 → 株価↑
- **四半期決算**: 前年同期比で増収増益 + 通期進捗率が良好 → ポジティブ
- 進捗率は「季節性」を加味して判断
- 第1四半期に好決算 → その後の上昇が長続きしやすい傾向
- **出典**: [Money Plus 決算後出し作戦](https://media.moneyforward.com/articles/9075)

---

## 6. 実践：決算チェックの手順

### 情報収集ツール
- **Investing.com**: EPS・売上の実績 vs 予想を一覧確認
- **Yahoo Finance**: Earnings履歴・ガイダンス確認
- **SEC EDGAR**: 8-K（速報）、10-Q（正式四半期報告）の一次情報
- **企業IRページ**: 決算リリース・説明会資料

### スコアリングの実践フロー

```
Step 1: EPS確認
  - Diluted EPS vs コンセンサス → Beat/Miss
  - Adjusted EPS vs コンセンサス → Beat/Miss
  - YoY成長率

Step 2: 売上確認
  - Revenue vs コンセンサス → Beat/Miss
  - YoY成長率
  - セグメント別の良し悪し

Step 3: ガイダンス確認
  - 次期/通期ガイダンス vs コンセンサス → Raise/Hold/Lower
  - Beat-and-Raise? or Beat-and-Lower?

Step 4: Conference Call確認
  - Q&AでのCEO/CFOのトーン
  - アナリストの関心事
  - 口頭でのガイダンス修正・補足

Step 5: 総合スコアリング
  - 3軸スコア（EPS/Revenue/Guidance）を集計
  - 長期トレンド（時系列）で判断
```

---

## 7. 主要ソース一覧

| ソース | URL | 権威度 |
|-------|-----|--------|
| SBI証券 銘柄レポート・決算リリースを読む基礎知識（2026-03-25） | https://go.sbisec.co.jp/media/report/fo_senryaku/fo_senryaku_260325.html | analyst |
| moomoo 米株決算で真っ先に見るべきポイント | https://www.moomoo.com/jp/learn/detail-summary-of-the-first-points-you-should-look-at-in-us-stock-financial-results-116747-230910056 | media |
| HEDGE GUIDE 米国上場企業の決算の読み方 | https://hedge.guide/feature/howto-read-us-companies-financial-statement.html | media |
| Fund Garage 米国企業の決算発表、何をどう見れば良いのか | https://fundgarage.com/stock/post-0-80/ | analyst |
| note 松浦タイゾウ アメリカ株決算の調べ方 | https://note.com/ds321/n/n2cebbd31cc9a | blog |
| Investopedia What Is an Earnings Call? | https://www.investopedia.com/terms/e/earnings-call.asp | media |
| Investopedia How To Listen to Earnings Calls | https://www.investopedia.com/small-business/what-is-an-earnings-conference-call/ | media |
| Money Plus 決算後出し作戦 | https://media.moneyforward.com/articles/9075 | media |
| Forbes Big Banks Earnings Season Kicks Off（2026-04-07） | https://www.forbes.com/sites/mayrarodriguezvalladares/2026/04/07/big-banks-bigger-profits-earnings-season-kicks-off-next-week/ | media |
| Yahoo Finance JPM Q1 2026 Earnings Preview | https://finance.yahoo.com/markets/stocks/articles/jpmorgan-chase-earnings-preview-expect-144841270.html | media |
| Forbes - The Dysfunctional Earnings Game | https://www.forbes.com/sites/georgecalhoun/2025/11/30/the-case-against-quarterly-reporting--part-2-the-earnings-game/ | media |
| Investopedia - Why Stocks Drop After Positive News | https://www.investopedia.com/ask/answers/06/stockdeclinegoodnews.asp | media |

---

## 8. 記事の論点・構成案

### メインメッセージ
> 「決算は3軸スコアリングで読む。EPS・売上は"過去"、ガイダンスが"未来"。株価を動かすのは未来への期待だ。」

### 推奨構成（3500字目標）

1. **イントロ**: 2026年4月14日JPM決算でQ1シーズン開幕（タイムリー）
2. **なぜ決算が重要か**: 短期・長期両面での株価インパクト
3. **軸1: EPS**（GAAP vs Non-GAAP、Diluted、Beat/Miss判定）
4. **軸2: 売上高**（コンセンサス比、YoY成長率、オーガニック）
5. **軸3: ガイダンス**（最重要軸、Beat-and-Raise vs Beat-and-Lower）
6. **Conference Callの聴き方**（Q&Aのポイント、レッドフラグ）
7. **「好決算なのに株価下落」を理解する**（Sell the news、ウィスパーナンバー）
8. **日本株 vs 米国株の違い**（決算短信との比較）
9. **実践：3軸スコアリングの使い方**（ステップバイステップ）
10. **まとめ**: 時系列データの重要性（1回の決算より「癖」を掴む）

### ターゲット読者の課題
- 「決算発表翌日に株価が急落して損した」
- 「EPSがよかったのになぜ下がるのか分からない」
- 「コンファレンスコールって何を聴けばいいの？」
- 「日本株は分かるけど米国株の決算の見方が違う」
