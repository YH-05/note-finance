---
name: equity-stock-research
description: |
  個別銘柄のエクイティリサーチにおける分析フレームワーク。バイサイドアナリストがInitial Reportを
  執筆するための7フェーズ調査視点を提供するナレッジベース。
  銘柄調査の開始時、NotebookLMへの質問設計時、セルサイドレポート分析時、
  SEC Edgar/EDINET調査時、企業の財務分析時にプロアクティブに使用する。
  「銘柄調査」「個別株リサーチ」「Initial Report」「企業分析」「ARPU」「EV/EBITDA」
  「セルサイドレポート」「ファンダメンタルズ」「バリュエーション」と言われたら必ずこのスキルを参照すること。
---

# Equity Stock Research Framework

バイサイドアナリストがFM向けInitial Reportを執筆するための、構造化された個別銘柄調査フレームワーク。
セクター横断で使える汎用的な分析視点を7フェーズに整理し、調査の網羅性と深度を担保する。

## 基本思想

このスキルは **「何を問うべきか」** を定義する。**「どう情報を取るか」** は別のスキル/ツールに委譲する。

| 情報ソース | 対応スキル/ツール |
|-----------|----------------|
| 会社資料・セルサイドレポート（PDF） | `/convert-pdf`, `nlm` CLI (`nlm chat ask`, `nlm source add-file`) |
| Web上のニュース・業界データ | `/gemini-search`, Web検索ツール |
| SEC Edgar（米国上場） | `sec-edgar-mcp` |
| Wikipedia（企業・業界背景） | `wikipedia` MCP |
| Reddit（個人投資家センチメント） | `/reddit-finance-topics` |
| 既存リサーチメモ | `equity_research/{TICKER}_{EXCHANGE}/` |

## 7フェーズ概観

調査は以下の順序で進める。Phase 1-3で定性理解を固め、Phase 4で数字を検証し、Phase 5-7で投資判断の材料を揃える。

| Phase | テーマ | 出力ファイル名 | 目的 |
|-------|--------|--------------|------|
| 1 | Company Overview | `company_overview.md` | 事業構造・ガバナンス・経営陣の理解 |
| 2 | Industry & Competition | `industry_competition.md` | 市場環境・競合ポジション・規制の把握 |
| 3 | Business Model & KPIs | `business_kpis.md` | 収益モデルと主要KPIの深掘り |
| 3+ | Sector Deep Dive | `sector_deep_dive.md` | **業種固有KPIの動的深掘り**（後述） |
| 4 | Financial Analysis | `financial_analysis.md` | P/L・B/S・C/F・ガイダンスの定量分析 |
| 5 | Valuation & Consensus | `valuation_consensus.md` | セルサイド見解・マルチプル・コンセンサスの整理 |
| 6 | Catalysts & Risks | `catalysts_risks.md` | カタリスト・リスク要因・ESGの棚卸し |
| 7 | Investment Synthesis | `investment_synthesis.md` | Bull/Bear case統合・独自論点の抽出 |

### 効率的な進め方

1. **Phase 1-3** を先に消化 → 定性的な理解を固める
2. **Phase 3+** でセクター固有KPIを深掘り → 業種特有の論点を特定
3. **Phase 4** で数字を固める → スプレッドシートに転記
4. **Phase 5** でバリュエーション前提を確認
5. **Phase 6-7** で判断の最終材料を集める

## Phase 1: Company Overview & Structure

企業の全体像を掴む。事業セグメント、株主構成、経営陣の質を理解する。

### 1-1. 事業概要
- 事業セグメント別の売上構成比と各セグメントの概要・直近トレンド
- 過去の重要な合併・買収・分離の経緯と、具体的なシナジー/ディスシナジー実績
- 事業モデルの一言要約 — 収益の源泉は何か

### 1-2. 株主・ガバナンス
- 大株主の持分比率と経営への関与度
- 取締役会の構成と独立取締役比率
- 大株主間の利害対立リスク — 過去の事例はあるか

### 1-3. 経営陣
- CEO・CFOの経歴・実績・在任期間
- 中期経営計画・戦略ビジョンの要点
- 報酬体系とインセンティブ構造 — 株主利益との整合性

> 詳細な質問リスト: `references/phase1-company.md`

## Phase 2: Industry & Competition

対象企業が置かれた市場環境と競争構造を理解する。

### 2-1. 市場環境
- 市場規模（TAM/SAM）と過去3-5年のCAGR
- 主要な普及率指標の推移（業種による）
- 人口動態・マクロ環境が当該市場に与える影響

### 2-2. 競合分析
- 主要競合との定量比較（シェア、売上、利益率、主要KPI）
- 各社の競争戦略の違い（価格・品質・ニッチ等）
- 対象企業の競争上のポジショニングとシェア推移

### 2-3. 規制環境
- 主要な規制当局の方針と最近の動き
- 業種固有の許認可・ライセンスの状況
- 規制変更リスクの特定

> 詳細な質問リスト: `references/phase2-industry.md`

## Phase 3: Business Model & KPIs

収益モデルの仕組みと、それを測る主要KPIを深掘りする。

### 汎用KPIフレームワーク

どのセクターでも確認すべき基本KPI:

| カテゴリ | KPI例 |
|---------|-------|
| トップライン | 売上成長率、オーガニック成長率、地域別/製品別売上 |
| 顧客指標 | 顧客数/加入者数、チャーン率、LTV、CAC |
| 単価指標 | ARPU、ASP、単位あたり収益 |
| 効率指標 | 稼働率、歩留まり、生産性指標 |
| デジタル/新規事業 | 新規事業の売上比率、成長率、マージンプロファイル |

### セクター固有KPI — 動的深掘りメカニズム

Phase 1-2の調査結果から対象企業のセクターを特定した後、以下のプロセスで業種固有KPIを深掘りする。

**ステップ 1: セクター特定とKPIカタログ参照**

`references/sector-kpis.md` に主要セクター別のKPIカタログがある。該当セクターのKPIリストを参照し、調査すべき指標を特定する。

**ステップ 2: 動的質問生成**

カタログにないセクターの場合、Phase 1-2で得た情報を元に以下の観点で追加KPIを推論する:

1. **収益ドライバー分解**: 売上 = [量] x [単価] の構造を分解し、それぞれの変動要因を特定
2. **業界固有の制約**: 規制、ライセンス、季節性、技術サイクルなど
3. **競合との差別化指標**: 品質、速度、コスト、ネットワーク効果など
4. **経営陣が強調するKPI**: IR資料で頻出する指標は経営の関心を反映している

**ステップ 3: 深掘り質問の実行**

特定したKPIについて:
- 四半期推移（最低2年分）
- 変動要因の分析
- 業界平均との比較
- 経営陣のコメント・ガイダンス

結果は `sector_deep_dive.md` に保存する。

> 詳細な質問リスト: `references/phase3-business.md`
> セクター別KPIカタログ: `references/sector-kpis.md`

## Phase 4: Financial Analysis

定量的な財務分析。P/L・B/S・C/Fの3表を精査し、ガイダンスの達成度を検証する。

### 4-1. P/L（損益計算書）
- 過去5年間のRevenue、EBITDA、EBITDA Margin、Net Incomeの推移
- 売上成長のドライバー分解（サービス別、地域別）
- コスト構造の内訳と各項目の対売上比率の推移
- M&A実施企業はシナジー実績を数値で確認

### 4-2. B/S（貸借対照表）
- 有利子負債、ネットデット、Net Debt/EBITDAの推移
- 負債の通貨構成と為替リスクヘッジの状況
- 満期構成（Debt maturity profile）
- ROEとROICの推移 — 資本効率の改善トレンド

### 4-3. C/F（キャッシュフロー計算書）
- Operating CF、Capex、FCFの推移
- Capex/Revenue比率のトレンドと今後のガイダンス
- 配当方針（Payout ratio target）と配当実績
- 大型投資プログラムのCapexへの影響

### 4-4. ガイダンスと達成度
- 直近のガイダンス（Revenue、EBITDA、Capex等）
- 中期的な財務目標（Margin target、Leverage target）
- **ガイダンスのトラックレコード** — 過去のガイダンス vs 実績の乖離パターン

> 詳細な質問リスト: `references/phase4-financials.md`

## Phase 5: Valuation & Consensus

市場の評価水準とセルサイドの見方を整理する。

### 5-1. セルサイド見解
- 各社のRating、ターゲットプライス、算出手法、主要前提の一覧表
- セルサイド間で**最も見解が分かれているポイント**の特定
- TP算出手法（DCF/マルチプル/PER等）と前提の比較

### 5-2. バリュエーション水準
- 主要マルチプル（EV/EBITDA、PER等）の過去推移とレンジ
- 同業他社・地域peer比でのプレミアム/ディスカウントとその理由
- 現在のマルチプルが歴史的レンジのどこに位置するか

### 5-3. コンセンサス予想とリビジョン
- FY+1、FY+2のコンセンサス予想（Revenue、EBITDA、EPS）
- **リビジョントレンド** — 上方修正/下方修正どちらが優勢か、転換点はいつか

> 詳細な質問リスト: `references/phase5-valuation.md`

## Phase 6: Catalysts & Risks

株価を動かすイベントとリスク要因を棚卸しする。

### 6-1. カタリスト（6-12ヶ月）
- 業績カタリスト: 決算、ガイダンス引き上げ、コスト削減成果
- 戦略カタリスト: M&A、資産売却、新規事業、提携
- 制度カタリスト: 規制変更、税制、業界再編

### 6-2. リスク定量化
各リスクについて、可能な限り**感応度分析**の形で把握する:
- 競争激化リスク: 単価1%低下時のEPS影響
- 為替リスク: 主要通貨の変動感応度
- 規制リスク: 最悪シナリオでの財務インパクト
- 技術リスク: 設備投資回収の不確実性

### 6-3. ESG
- ESG開示の充実度と主な取り組み
- 第三者ESGレーティング（MSCI、Sustainalytics等）
- ESG要因が投資判断に与えるマテリアルな影響

> 詳細な質問リスト: `references/phase6-catalysts.md`

## Phase 7: Investment Synthesis

全フェーズの調査結果を統合し、独自の投資判断材料を形成する。

### 統合質問 — 5つの必須問い

1. **Bull Case**: 最も強気になれる要因を3つ。各ソースからの根拠を付す
2. **Bear Case**: 最も慎重になるべき要因を3つ。定量的なダウンサイドシナリオを含む
3. **Consensus vs Reality**: セルサイドコンセンサスと会社実績データの乖離点
4. **What's Different Now**: 直近1-2年でファンダメンタルズが最も大きく変わった点
5. **Under-discussed**: 複数レポートで十分に議論されていないが投資判断に重要な論点

### バイサイド固有の視点

セルサイドレポートを読む際、以下の「裏を読む」視点を常に持つ:
- **コンセンサスの歪み**: 全員がBuyのとき、本当にそれでよいか？
- **非対称リスク**: アップサイドとダウンサイドのどちらが大きいか
- **市場に織り込まれていない変化**: 経営陣の微妙なトーン変化、競合の動き
- **時間軸のミスマッチ**: セルサイドの12ヶ月TPと自社の投資期間の違い

> 詳細な質問リスト: `references/phase7-synthesis.md`

## 出力規約

### ファイル保存先

```
equity_research/{TICKER}_{EXCHANGE}/research_memo/
├── company_overview.md
├── industry_competition.md
├── business_kpis.md
├── sector_deep_dive.md      # Phase 3+で動的に生成
├── financial_analysis.md
├── valuation_consensus.md
├── catalysts_risks.md
├── investment_synthesis.md
└── sources/                  # 元ソースPDF
```

### 各ファイルの記録フォーマット

```markdown
# {テーマ名} — {TICKER} Research Memo

## Q: [質問]
### A: [回答の要約]
- **Source**: [どの情報ソースに基づくか]
- **数値データ**: [具体的な数字]
- **アナリストメモ**: [追加の考察・疑問・フォローアップ事項]

---
(以下、質問ごとに繰り返し)
```

### 情報ソースへの質問投入のコツ

- 1質問1トピックに絞る（複数混ぜると回答が浅くなる）
- 「具体的な数字を含めて」と指示する
- 「どのソースに基づいていますか？」とソース明示を求める
- セルサイドレポート間で意見が割れている場合は「各レポートの見解を比較して」と聞く
- 回答が不十分な場合は「もう少し詳しく」「定量的に」とフォローアップ

## 関連ファイル

| リソース | パス |
|---------|------|
| セクター別KPIカタログ | `references/sector-kpis.md` |
| NotebookLM質問テンプレート（ISAT_IJ実績） | `docs/templates/initial-report/notebooklm-questions.md` |
| equity_research ディレクトリ | `equity_research/` |

## KG Output（任意）

リサーチ結果をresearch-neo4jに永続化する場合:
1. `/emit-research-queue` スキルでgraph-queue JSONを生成
2. `/save-to-graph` でNeo4jに投入

参照: `.claude/rules/neo4j-write-rules.md`（直書き禁止ルール）
