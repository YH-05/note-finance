---
name: macro-economic-research
description: |
  グローバルマクロ経済の分析フレームワーク。バイサイドアナリストがマクロ環境を体系的に
  調査し、個別銘柄分析（equity-stock-research）のマクロコンテキストを提供するための
  8フェーズ調査視点を提供するナレッジベース。
  マクロリサーチの開始時、週次レポート作成時、アセットアロケーション検討時、
  中央銀行政策分析時、経済指標の解釈時にプロアクティブに使用する。
  「マクロ分析」「マクロリサーチ」「金融政策」「中央銀行」「利上げ」「利下げ」
  「イールドカーブ」「GDP」「CPI」「雇用統計」「PMI」「為替分析」「FX」
  「コモディティ」「地政学リスク」「景気サイクル」「アセットアロケーション」
  「クロスアセット」と言われたら必ずこのスキルを参照すること。
---

# Macro Economic Research Framework

グローバルマクロ経済を体系的に調査するためのフレームワーク。
景気サイクルの位置を起点に、金融政策・経済指標・金利・為替・コモディティ・地政学を
横断的に分析し、投資判断のマクロコンテキストを提供する。

## equity-stock-research との関係

このスキルは equity-stock-research の **マクロ補完レイヤー** として機能する。

| equity-stock-research | macro-economic-research |
|----------------------|------------------------|
| Phase 2: Industry & Competition のマクロ要素 | Phase 3: 経済指標、Phase 7: 地政学で深掘り |
| Phase 6: Catalysts & Risks の金利・為替リスク | Phase 2: 金融政策、Phase 4-5: 金利・為替で定量化 |
| 個別銘柄のバリュエーション前提 | Phase 1: レジーム判定でディスカウントレート環境を提供 |

**使い分け**: 個別銘柄調査中にマクロ環境の確認が必要になったら、このスキルの該当Phaseを参照する。
マクロ調査から個別銘柄へ落とし込む場合は、Phase 8 の統合分析を起点にする。

## 基本思想

equity-stock-research と同様、**「何を問うべきか」** を定義する。情報の取得手段は別スキル/ツールに委譲する。

### 情報ソースと利用可能性

マクロ分析では、情報ソースごとにカバー範囲が異なる。全ソースが常に利用可能とは限らないため、
**利用可能なソースから最大限の情報を引き出す** 設計とする。

| 情報ソース | 対応ツール | カバー範囲 | 利用可能性 |
|-----------|-----------|-----------|-----------|
| マクロ戦略レポート（PDF） | `/convert-pdf`, NotebookLM | 総合的なマクロビュー | ソース依存 |
| Web上のニュース・データ | `/gemini-search`, Web検索 | リアルタイム情報 | 常時 |
| RSS金融ニュース | `rss` MCP | ニュースフロー | 常時 |
| SEC Edgar（米国企業） | `sec-edgar-mcp` | 米国企業の開示情報 | 常時 |
| Wikipedia（背景情報） | `wikipedia` MCP | 制度・歴史的背景 | 常時 |
| Reddit（市場センチメント） | `/reddit-finance-topics` | 個人投資家の見方 | 常時 |
| 中央銀行サイト | Web検索/Fetch | 政策声明・議事要旨 | 常時 |

### グレースフルデグラデーション

各Phaseは以下の3層で設計されている。上位層のソースがなくても、下位層だけで基本的な分析は可能。

1. **Core（必須）**: Web検索と公開データだけで回答可能な基本質問
2. **Enhanced（推奨）**: セルサイドレポートやNotebookLMがあれば深掘りできる質問
3. **Advanced（任意）**: 複数ソースの横断比較が必要な高度な質問

## 8フェーズ概観

Phase 1でレジームを判定し、Phase 2-7でテーマ別に深掘りし、Phase 8で統合する。

| Phase | テーマ | 出力ファイル名 | 目的 |
|-------|--------|--------------|------|
| 1 | Macro Regime & Cycle | `regime_cycle.md` | 景気サイクルの位置と方向性の判定 |
| 2 | Monetary Policy & Central Banks | `monetary_policy.md` | 主要中銀の政策スタンスと金利パス |
| 3 | Economic Data & Indicators | `economic_data.md` | 成長・雇用・インフレの定量把握 |
| 4 | Rates & Fixed Income | `rates_fixed_income.md` | イールドカーブ・クレジットの分析 |
| 5 | FX & Currency | `fx_currency.md` | 為替動向とドライバー分析 |
| 6 | Commodities & Real Assets | `commodities.md` | エネルギー・貴金属・農産物の需給 |
| 7 | Geopolitical & Fiscal Policy | `geopolitical_fiscal.md` | 地政学リスクと財政政策の影響 |
| 8 | Cross-Asset Synthesis | `cross_asset_synthesis.md` | レジームベースの統合分析と投資示唆 |

### 効率的な進め方

1. **Phase 1** でレジーム判定 → 全体のフレームを決める
2. **Phase 2-3** で金融政策と経済データを押さえる → マクロの骨格
3. **Phase 4-6** で資産クラス別に深掘り → 必要なPhaseのみ選択可
4. **Phase 7** で地政学・財政を確認 → テールリスクの棚卸し
5. **Phase 8** で統合 → 投資判断への示唆を形成

**部分的な利用**: 全8Phaseを順に消化する必要はない。週次レポート用ならPhase 1+8を中心に、
特定テーマ（例：FRB利下げの影響）ならPhase 2+4+5を重点的に、といった使い方が効果的。

## Phase 1: Macro Regime & Business Cycle

景気サイクルの現在位置と方向性を判定する。全分析の起点。

### 1-1. サイクル判定
- 主要国（米国・欧州・日本・中国）の景気サイクル位置（拡大/ピーク/後退/回復）
- 先行指標（LEI、PMI、イールドカーブ形状）が示す方向性
- 各国のサイクル同期度 — 同時進行か乖離しているか

### 1-2. レジーム分類
- 現在のマクロレジーム: Goldilocks / Reflation / Stagflation / Deflation
- インフレと成長の組み合わせマトリクス上の位置
- レジーム転換のトリガーになりうるイベント

### 1-3. クロスカントリー比較
- 先進国 vs 新興国の成長格差とトレンド
- 金融政策の乖離度（利上げ国 vs 利下げ国のマッピング）
- 資本フローの方向性（リスクオン/リスクオフ）

> 詳細な質問リスト: `references/phase1-regime.md`

## Phase 2: Monetary Policy & Central Banks

最も市場インパクトの大きいマクロ変数。主要5中銀を中心に分析する。

### 2-1. 政策スタンスの把握
- 各中銀（FRB/ECB/BOJ/BOE/PBOC）の現在の政策金利と直近の決定
- フォワードガイダンスの要点 — 何を条件に次のアクションが決まるか
- 市場の織り込み（OIS/FF金利先物）vs 中銀のドットプロット/見通し

### 2-2. バランスシート政策
- QE/QTの現状と今後の見通し
- バランスシートの規模推移と縮小ペース
- 流動性への影響（準備預金残高、RRP残高等）

### 2-3. 中銀ウォッチのポイント
- 直近の声明文・議事要旨でのトーン変化
- 中銀メンバーのハト派/タカ派バランスの変化
- サプライズの可能性 — 市場予想と乖離しうるシナリオ

> 詳細な質問リスト: `references/phase2-monetary-policy.md`

## Phase 3: Economic Data & Indicators

ハードデータとソフトデータを組み合わせ、経済の実態を把握する。

### 3-1. 成長指標
- GDP成長率（実質/名目）の推移と構成要素（個人消費、投資、政府支出、純輸出）
- PMI（製造業/サービス業）の水準と方向性
- 鉱工業生産、小売売上高、貿易収支

### 3-2. 労働市場
- 雇用者数変化、失業率、労働参加率
- 賃金上昇率（平均時給、ECI等）
- 求人倍率、失業保険申請件数

### 3-3. インフレ指標
- CPI/PCE（総合/コア）の水準とトレンド
- PPI（生産者物価）— コスト転嫁の先行指標
- インフレ期待（BEI、ミシガン大学調査、NY Fed調査）

### 3-4. その他の先行・一致指標
- 消費者信頼感（Conference Board、ミシガン大学）
- ISM/PMIのサブコンポーネント（新規受注、在庫等）
- 住宅着工件数、建設許可件数

> 詳細な質問リスト: `references/phase3-economic-data.md`
> 地域別指標カタログ: `references/region-indicators.md`

## Phase 4: Rates & Fixed Income

金利の水準と構造を分析し、金融環境の引き締め/緩和度合いを評価する。

### 4-1. イールドカーブ分析
- 主要年限（2Y/5Y/10Y/30Y）の水準と直近の変動
- カーブ形状（スティープ/フラット/逆イールド）の意味
- ターム・プレミアムの推定値と変動要因

### 4-2. クレジット市場
- IG/HYスプレッドの水準と推移 — リスク選好度の指標
- 社債発行市場の動向（発行量、需要、スプレッド）
- デフォルト率の推移と見通し

### 4-3. 金融環境指数
- Financial Conditions Index（GS FCI、Chicago Fed NFCI等）
- 実質金利（名目金利 - BEI）の水準
- 銀行の貸出態度調査（Senior Loan Officer Survey等）

> 詳細な質問リスト: `references/phase4-rates-credit.md`

## Phase 5: FX & Currency

為替動向とそのドライバーを分析する。

### 5-1. 主要通貨の動向
- DXY（ドルインデックス）の水準とトレンド
- 主要ペア（EUR/USD、USD/JPY、GBP/USD、USD/CNY）の動向
- 実質実効為替レート（REER）— 長期的な割高/割安の判断

### 5-2. ドライバー分析
- 金利差（2年金利差が短期的な為替の主要ドライバー）
- 経常収支・資本収支のフロー
- リスクセンチメント（VIX、キャリートレードの巻き戻し等）

### 5-3. 新興国通貨
- EM通貨指数の推移
- 脆弱なEM通貨の特定（経常赤字、外貨準備不足、政治リスク）
- 中央銀行の介入動向

> 詳細な質問リスト: `references/phase5-fx-currency.md`

## Phase 6: Commodities & Real Assets

コモディティの需給と価格動向を分析する。

### 6-1. エネルギー
- 原油（WTI/Brent）の価格と需給バランス
- OPEC+の生産方針と遵守状況
- 天然ガス（Henry Hub/TTF）の季節性と在庫

### 6-2. 貴金属
- 金価格のドライバー（実質金利、ドル、地政学リスク、中銀購入）
- 中央銀行の金購入トレンド
- 金ETFフローの動向

### 6-3. 産業用金属・農産物
- 銅・鉄鉱石の需給 — 中国の需要動向が鍵
- 農産物（小麦、大豆、コーン）— 天候・輸出規制リスク
- サプライチェーンのボトルネック

> 詳細な質問リスト: `references/phase6-commodities.md`

## Phase 7: Geopolitical & Fiscal Policy

地政学リスクと財政政策のインパクトを評価する。

### 7-1. 地政学リスク
- 主要な地政学ホットスポットの現状と市場への影響経路
- 貿易政策（関税、輸出規制、サプライチェーン再編）
- 経済制裁の影響と波及経路

### 7-2. 財政政策
- 主要国の財政スタンス（拡張/緊縮）と財政インパルス
- 財政赤字/GDP比と債務の持続可能性
- 重要な財政イベント（予算編成、債務上限、選挙関連の財政出動）

### 7-3. 構造的テーマ
- 脱グローバリゼーション/フレンドショアリング
- エネルギー転換・気候政策の経済的影響
- 人口動態（高齢化、移民政策）の長期的影響

> 詳細な質問リスト: `references/phase7-geopolitical-fiscal.md`

## Phase 8: Cross-Asset Synthesis

全Phaseの調査結果を統合し、投資判断への示唆を導出する。

### 統合質問 — 5つの必須問い

1. **Regime Call**: 現在のマクロレジームは何か？今後6-12ヶ月で変化する可能性は？
2. **Consensus vs Our View**: 市場コンセンサスと自分の見方が最も乖離するポイントは？
3. **Key Catalyst Timeline**: 今後3ヶ月の重要イベントカレンダーと想定インパクト
4. **Tail Risks**: 確率は低いが実現時のインパクトが大きいシナリオ（左尾/右尾）
5. **Asset Allocation Implications**: レジーム判定に基づく資産クラス別の方向性

### バイサイド固有の視点

- **ポジショニングの偏り**: 市場参加者のポジションが一方向に偏っていないか
- **ナラティブ vs データ**: 市場で支配的なストーリーとハードデータは整合しているか
- **時間軸のミスマッチ**: 短期トレードと中長期アロケーションで見方が異なるか
- **セカンドオーダーエフェクト**: 一次的な影響だけでなく、波及効果を考慮しているか

> 詳細な質問リスト: `references/phase8-cross-asset-synthesis.md`

## 出力規約

### ファイル保存先

```
equity_research/macro_research/
├── {YYYY-MM}_global/              # 月次のグローバルマクロレビュー
│   ├── regime_cycle.md
│   ├── monetary_policy.md
│   ├── economic_data.md
│   ├── rates_fixed_income.md
│   ├── fx_currency.md
│   ├── commodities.md
│   ├── geopolitical_fiscal.md
│   ├── cross_asset_synthesis.md
│   └── sources/
├── {YYYY-MM}_{THEME}/            # テーマ別の深掘り調査
│   ├── {該当Phase}.md
│   └── sources/
└── README.md
```

### テーマ別調査の例

特定テーマにフォーカスする場合は、関連Phaseのみを実施する:

| テーマ例 | 該当Phase | フォルダ名例 |
|---------|----------|-------------|
| FRB利下げサイクル分析 | 2 + 4 + 5 | `2026-03_fed_rate_cuts` |
| 中国景気減速の影響 | 1 + 3 + 6 | `2026-03_china_slowdown` |
| 地政学リスクの棚卸し | 7 + 8 | `2026-03_geopolitical_review` |

### 記録フォーマット

```markdown
# {テーマ名} — Macro Research Memo

## 調査日: {YYYY-MM-DD}
## レジーム判定: {Goldilocks / Reflation / Stagflation / Deflation}

---

## Q: [質問]
### A: [回答の要約]
- **Source**: [情報ソース]
- **データ**: [具体的な数値・日付]
- **アナリストメモ**: [考察・疑問・フォローアップ事項]
- **信頼度**: [High/Medium/Low — ソースの質と鮮度に基づく]

---
```

## 関連ファイル

| リソース | パス |
|---------|------|
| 地域別指標カタログ | `references/region-indicators.md` |
| equity-stock-research | `.claude/skills/equity-stock-research/SKILL.md` |
| 週次マーケットレポート | `.claude/skills/generate-market-report/SKILL.md` |
| macro_research ディレクトリ | `equity_research/macro_research/` |
