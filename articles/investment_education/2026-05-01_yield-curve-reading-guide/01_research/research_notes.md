# リサーチノート：イールドカーブ入門
作成日: 2026-05-01
トピック: イールドカーブ入門：2/10年スプレッド・期待インフレ・タームプレミアムを絵で読む

---

## 1. イールドカーブの基本構造

### 定義
イールドカーブ（利回り曲線）とは、同一発行体（通常は国債）の残存期間（満期）と利回りの関係をグラフにしたもの。
- **縦軸**：利回り（yield）
- **横軸**：残存期間（満期まで）

### 3つの形状
| 形状 | 特徴 | 状況 |
|------|------|------|
| 順イールド（ノーマル） | 右肩上がり（長期＞短期） | 通常の景気拡大期 |
| フラット | 長短金利がほぼ同水準 | 転換期・不透明感が高い |
| 逆イールド（インバーテッド） | 右肩下がり（短期＞長期） | 景気後退の先行シグナル |

**出典**: [イールドカーブとは？形状や変化 - Siiibo証券](https://siiibo.com/articles/yield-curve)

---

## 2. 2/10年スプレッド（T10Y2Y）

### 定義
T10Y2Y = 10年国債利回り − 2年国債利回り

### 現在の数値（2026年）
- 2026年2月5日：**+73.7bp**（2022年1月以来最大に近い水準）
- 2026年4月3日：10年債 **4.31%**（前月比+0.21bp、前年比+0.32bp）
- 2025年10月に再正常化（2年債3.48%、10年債4.01%、+53bp）

### 逆イールドの歴史
- 2022年10月〜2024年中頃：**約26ヶ月の逆転**（過去最長）
- 歴史的記録（1976年以降）：7回の逆イールドのうち6回が景気後退に先行
- 逆転から景気後退までの中央値：**14ヶ月**（18〜92週の幅）
- 重要：景気後退は逆転中ではなく**再スティープ化後**に始まる傾向

**出典**: 
- [FRED T10Y2Y](https://fred.stlouisfed.org/series/T10Y2Y)
- [Yield Curve Inversion History - eco3min](https://eco3min.fr/en/yield-curve-inversion-history-2s10s-spread/)
- [NY Fed Yield Curve as Leading Indicator](https://www.newyorkfed.org/research/capital_markets/ycfaq)

---

## 3. 期待インフレ（ブレークイーブン・インフレ率 / BEI）

### 計算式
```
BEI = 名目国債利回り − TIPS（物価連動国債）利回り
期待インフレ率 ≈ BEI + α（インフレリスクプレミアム＋流動性プレミアム等）
```

通常の近似として `α = 0` とする。

### 数値例（Japan 2025年末）
- 名目10年金利：約1.763%
- 物価連動国債利回り：0.134%
- **BEI（10年）= 1.629%**

### 米国のBEI
- 長期平均：**1.7〜1.8%**（セントルイス連銀公表）
- FRBの物価目標（PCE 2%）≈ CPI 2.3%（CPI ≈ PCE + 0.2-0.3%）
- 2026年4月：1年先期待インフレ率 **4.7%**（ミシガン大学・短期要因で上振れ）

### フィッシャー方程式
```
実質金利 = 名目金利 − 期待インフレ率
```

**出典**: 
- [期待インフレ率 - Wikipedia](https://ja.wikipedia.org/wiki/%E6%9C%9F%E5%BE%85%E3%82%A4%E3%83%B3%E3%83%95%E3%83%AC%E7%8E%87)
- [期待インフレ率 - IIMA](https://www.iima.or.jp/abc/ka/25.html)
- [期待インフレ率（米国・BEI）- stock-marketdata.com](https://stock-marketdata.com/bei-us.html)

---

## 4. タームプレミアム

### 定義
長期債を保有することに対して投資家が要求する「上乗せ利回り」。
「短期債をロールするより長期債を保有することへの報酬」。

### 長期金利の分解（ACM分解）
```
名目長期金利 = 期待される将来の短期金利の平均 + タームプレミアム
（より詳細）= 実質短期金利期待 + 期待インフレ + タームプレミアム
```

### NYFed ACMモデル
- Adrian, Crump & Moench（2013）による分解モデル
- 公開データ：NY Fed Research > Capital Markets > Term Structure

### 直近の動向
- 2024年10月：タームプレミアムが**ゼロ近辺から25bp超に上昇**（Bloomberg、昨年11月以来の高水準）
- 2026年4月（IMF指摘）：米国債プレミアムが縮小、世界への影響を警告

### タームプレミアムが上昇する要因
- 財政赤字拡大（供給増加懸念）
- インフレ見通しの不確実性
- 外国投資家の米国債保有減少
- FRBのバランスシート縮小（QT）

**出典**: 
- [米国債市場に警告サイン「タームプレミアム」急上昇 - Bloomberg](https://www.bloomberg.com/jp/news/articles/2024-10-24/SLTKZXT0G1KW00)
- [Investopedia - Term Structure of Interest Rates](https://www.investopedia.com/terms/t/termstructure.asp)

---

## 5. イールドカーブの変化パターン（スティープ化/フラット化）

### 4つのパターン

| パターン | 金利方向 | 変化の特徴 | 主な要因 |
|---------|---------|-----------|--------|
| ベア・スティープ | 上昇 | 長期金利＞短期金利の上昇幅 | 財政拡大・インフレ期待・TP上昇 |
| ブル・スティープ | 下落 | 短期金利＞長期金利の下落幅 | FRB利下げ期待・景気悪化 |
| ベア・フラット | 上昇 | 短期金利＞長期金利の上昇幅 | FRBの引き締め（利上げ） |
| ブル・フラット | 下落 | 長期金利＞短期金利の下落幅 | デュレーション需要・ディスインフレ |

### 景気サイクルとの関係
```
景気拡大 → ベア・フラット（利上げ） → 逆イールド → ブル・スティープ（景気悪化・利下げ期待）
→ 景気後退本格化
```

### 2025年の局面
- 2024年9月：逆イールド解消（793日間の逆転が終了）
- 2025年：**ベア・スティープ局面**（長期金利が短期より急上昇）
  - 10-30年債の売りが顕著
  - タームプレミアム上昇が主因

**出典**: 
- [イールドカーブの形状 - OANDA](https://www.oanda.jp/lab-education/bonds_basic/bonds6/yield-curve)
- [イールドカーブとスティープ化 - Siiibo](https://siiibo.com/articles/yield-curve)
- [イールドカーブがスティープ化する局面と金 - State Street](https://www.ssga.com/jp/ja/institutional/insights/how-do-steepening-yield-curve-regimes-impact-gold)

---

## 6. 投資家が使う実践的な見方

### 「絵で読む」ポイント

**短期金利が動くとき** → FRBの政策金利（FF金利）に連動
**長期金利が動くとき** → 期待インフレ率 + タームプレミアムの変化

### 現在のスプレッド（2026年4月）をどう読むか
- T10Y2Y ≈ +73bp（2022年以来の高水準）
- FRB利下げ期待（短期金利低下方向）＋財政赤字懸念（長期金利高止まり）の複合要因
- 再スティープ化直後 → 過去の歴史では景気後退リスクが残存

### FREDでチェックすべき3系列
1. **T10Y2Y**：2年-10年スプレッド
2. **T10YIE**：10年期待インフレ率（TIPS BEI）
3. **THREEFYTP10**：NY Fed 10年タームプレミアム

---

## 7. 主要ソース一覧（ソースURL）

| ソース | URL | 権威レベル |
|--------|-----|-----------|
| FRED T10Y2Y | https://fred.stlouisfed.org/series/T10Y2Y | official |
| NY Fed Leading Indicator | https://www.newyorkfed.org/research/capital_markets/ycfaq | official |
| Fed H.15 金利データ | https://www.federalreserve.gov/releases/h15/ | official |
| 期待インフレ率 Wikipedia | https://ja.wikipedia.org/wiki/期待インフレ率 | media |
| IIMA 期待インフレ率 | https://www.iima.or.jp/abc/ka/25.html | analyst |
| stock-marketdata.com BEI | https://stock-marketdata.com/bei-us.html | analyst |
| OANDA イールドカーブ | https://www.oanda.jp/lab-education/bonds_basic/bonds6/yield-curve | analyst |
| Siiibo イールドカーブ | https://siiibo.com/articles/yield-curve | analyst |
| Bloomberg タームプレミアム | https://www.bloomberg.com/jp/news/articles/2024-10-24/SLTKZXT0G1KW00 | media |
| eco3min 逆イールド歴史 | https://eco3min.fr/en/yield-curve-inversion-history-2s10s-spread/ | analyst |
| State Street スティープ局面と金 | https://www.ssga.com/jp/ja/institutional/insights/how-do-steepening-yield-curve-regimes-impact-gold | analyst |
