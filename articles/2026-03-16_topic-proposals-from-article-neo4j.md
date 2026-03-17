# 記事テーマ提案（article-neo4j データベース調査）

- 調査日: 2026-03-16
- データソース: article-neo4j (bolt://localhost:7689)
- DB規模: Source 432件（blog 431 + original 1）、Chunk 431件、Entity 27件、Topic 10件

## DB内の主要ソース

| ソース                      | 特徴                             | 記事数（概算） |
| --------------------------- | -------------------------------- | -------------- |
| A Wealth of Common Sense    | マーケット解説・行動ファイナンス | 30+            |
| Early Retirement Now        | FIRE・4%ルール・債券分析         | 30+            |
| Afford Anything             | ライフスタイル設計・お金の心理   | 20+            |
| Monevator                   | UK投資・住宅市場・配当戦略       | 20+            |
| Young and the Invested      | ETF比較・ファンドレビュー        | 20+            |
| Get Rich Slowly             | 個人資産形成・節約               | 10+            |
| Marginal Revolution         | マクロ経済・学術                 | 10+            |
| I Will Teach You To Be Rich | 夫婦のお金問題（Episode群）      | 30+            |

## DB内の Entity（27件）

| タイプ    | 名称                                                                                      |
| --------- | ----------------------------------------------------------------------------------------- |
| company   | NVIDIA, TSMC, Broadcom, AMD, Intel, Marvell Technology                                    |
| index     | S&P 500, 日経平均, TOPIX, VIX, QQQ, VT, VTI, Russell 1000 Growth/Value, 米10年債利回り 他 |
| commodity | SPDR Gold Shares                                                                          |
| currency  | USD/JPY, EUR/JPY                                                                          |

## DB内の Topic（10件）

| カテゴリ         | トピック                                                                                                       |
| ---------------- | -------------------------------------------------------------------------------------------------------------- |
| wealth           | FIRE & Wealth Building, Dividend Income, Personal Finance, Data-Driven Investing, Academic Finance & Economics |
| content_planning | 個別株分析, マクロ経済, クオンツ分析, マーケットレポート, 投資教育                                             |

---

## テーマ提案

### 1. 資産形成（asset_management）

#### 1-1. 4%ルールは本当に安全か？ — Early Retirement Now の検証を日本版で再考

- **DB根拠**: ERN「The 4% Rule is not as good as we hoped」Part 1-3、FIRE関連記事多数
- **既存記事との差別化**: 既存はインデックス投資・iDeCo中心。出口戦略（取り崩し）の記事がゼロ
- **主要ソース**:
    - https://earlyretirementnow.com/ （4% Rule シリーズ）
    - 「Pros and cons of different withdrawal rate rules」
    - 「Top 10 reasons for targeting more than 25 times annual spending」

#### 1-2. ロボアドバイザー vs 自分で組むインデックスポートフォリオ — 本当にコストに見合うか

- **DB根拠**: Wealthfront Review, Robo-Advisor記事9本+, ERN「Why we don't use Robo-advisers」
- **既存記事との差別化**: 既存はファンド選びが主。「委託 vs DIY」の比較視点がない
- **主要ソース**:
    - 「9 Best Robo-Advisors for Investing Money Automatically」
    - 「Wealthfront Review」
    - 「Be Your Own DIY Zero-Cost Robo-Adviser!」
    - 「The pros and cons of Empower (Personal Capital)」

#### 1-3. 高配当ETF vs 成長ETF — インカムとキャピタルゲインの最適バランス

- **DB根拠**: Best High-Yield ETFs, Best Dividend Aristocrats, Tech Dividend Stocks 等10本超
- **既存記事との差別化**: 既存の「高配当転換」記事(VZ)はあるが、ETFポートフォリオ設計の比較記事なし
- **主要ソース**:
    - 「7 Best High-Yield ETFs for Dividend-Hungry Investors」
    - 「10 Best-Rated Dividend Aristocrats Right Now」
    - 「5 Best Tech Dividend Stocks to Buy」
    - 「Slowly Get Rich with Dividends: Living on Dividends Alone?」

---

### 2. マクロ経済（macro_economy）

#### 2-1. 住宅バブルの構造 — UK/US事例から日本の不動産市場を読む

- **DB根拠**: Monevator の UK住宅価格記事8本超、AWOCS「How to Fix the Housing Market」「Housing Price Inflation」
- **既存記事との差別化**: 既存は原油ショック・金利がテーマ。不動産マクロの記事がゼロ
- **主要ソース**:
    - 「Housing Price Inflation - A Wealth of Common Sense」
    - 「Halifax's UK house price index plunges 2.5%」
    - 「Are UK house prices finally set for big falls?」
    - 「How to Fix the Housing Market」

#### 2-2. 金（ゴールド）vs ペーパーマネー — インフレヘッジ資産の再評価

- **DB根拠**: ERN「Gold vs. Paper Money」、Best Gold ETFs、Entity に SPDR Gold Shares
- **既存記事との差別化**: 既存はクレジット・日銀・原油がテーマ。コモディティ分析がゼロ
- **主要ソース**:
    - 「Gold vs. Paper Money: a rant - Early Retirement Now」
    - 「The 7 Best Gold ETFs You Can Buy」
    - 「Animal Spirits: Gold's 1987 Moment」
    - 「Animal Spirits: Hi-Yo Silver!」

#### 2-3. 「債券のほうが株より危険」になる局面 — 金利リスクの本質

- **DB根拠**: ERN「When bonds are riskier than stocks」「Lower risk through leverage」、Entity に米10年債利回り・VIX
- **既存記事との差別化**: 既存の日銀利上げ記事と補完的だが、債券リスクに焦点を当てた記事がない
- **主要ソース**:
    - 「When bonds are riskier than stocks - Early Retirement Now」
    - 「Lower risk through leverage - Early Retirement Now」
    - 「Is Diversification Finally Working Again?」

---

### 3. 投資教育（investment_education）

#### 3-1. 「お金の心理学」入門 — 行動バイアスが投資判断を狂わせるメカニズム

- **DB根拠**: Afford Anything Episode群（夫婦のお金問題130-157）、「Invisible Scripts」、AWOCS「Some Things I've Been Wrong About」
- **既存記事との差別化**: 既存の行動バイアス記事は資産形成寄り。心理学の基礎教育切り口がない
- **主要ソース**:
    - 「Are You Letting Invisible Scripts Rule Your Life?」
    - 「Some Things I've Been Wrong About - A Wealth of Common Sense」
    - Episode 130-157（お金と感情の実例集）

#### 3-2. 20代から始める資産形成ロードマップ — 401k/iDeCo/NISAの使い分け

- **DB根拠**: 「How to Invest in Your 20s」「How to Start Investing in College」「Financial advice for 18 year olds」
- **既存記事との差別化**: 既存のFOMC記事は中級者向け。初心者ロードマップ型の記事がない
- **主要ソース**:
    - 「How to Invest in Your 20s [Best Ways to Invest Money]」
    - 「How to Start Investing in College」
    - 「Best Long-Term Investments for Young Adults to Make」
    - 「The New Graduate's Guide to Financial Freedom」

#### 3-3. ドルコスト平均法 vs 一括投資 — データで見る最適解

- **DB根拠**: 「Why Dollar Cost Averaging Stinks」「Investing a Lump Sum of Cash in This Market」
- **既存記事との差別化**: 投資初心者が最も迷うテーマ。既存記事にこの切り口がない
- **主要ソース**:
    - 「Why Dollar Cost Averaging Stinks (and the Smart Alternative)」
    - 「Investing a Lump Sum of Cash in This Market - A Wealth of Common Sense」
    - 「Saving rate vs investment return: Which matters more?」

---

### 4. 個別株分析（stock_analysis）

#### 4-1. 半導体バリューチェーン分析 — NVIDIA/TSMC/Broadcom/AMD の競争構造

- **DB根拠**: Entity に NVIDIA, TSMC, Broadcom, AMD, Intel, Marvell の6社が登録済み
- **既存記事との差別化**: 既存はBlackRock・VZのみ。半導体セクターの本格分析がない
- **Entity一覧**: NVIDIA, TSMC, Broadcom, AMD, Intel, Marvell Technology

#### 4-2. 集中投資 vs 分散投資 — 「勝者総取り」市場での銘柄選択

- **DB根拠**: AWOCS「Investing in a Concentrated Stock Market」「Is Diversification Finally Working Again?」
- **既存記事との差別化**: 既存記事は個別企業分析。投資哲学レベルの銘柄選択論がない
- **主要ソース**:
    - 「Talk Your Book: Investing in a Concentrated Stock Market」
    - 「Is Diversification Finally Working Again?」

#### 4-3. バリュー株復活の条件 — グロース優位がいつ終わるか

- **DB根拠**: 「Best Value Stocks for 2026」、Entity に Russell 1000 Growth/Value
- **既存記事との差別化**: 既存のVZ記事は「高配当転換」文脈。バリュー vs グロースの構造分析がない
- **主要ソース**:
    - 「7 Best Value Stocks for 2026」
    - 「Animal Spirits: Small Caps Are Back」
    - Entity: iShares Russell 1000 Growth, iShares Russell 1000 Value

---

### 5. 副業・サイドビジネス（side_business）

#### 5-1. FIRE達成者のリアル — 早期リタイア後に何が起きるか

- **DB根拠**: ERN全記事群、「Once you can afford to retire, you can't afford not to」、Afford Anything「Why I Quit My Job」
- **既存記事との差別化**: 既存は副業ハウツー中心。FIRE後の生活設計・収入源の記事がない
- **主要ソース**:
    - 「Once you can afford to retire, you can't afford not to - ERN」
    - 「Should You Stop Working When You Become Financially Independent?」
    - 「Why I Quit My Job - and Why I Almost Didn't」
    - 「What happened to Early Retirement Extreme?」

#### 5-2. 場所に縛られない働き方 — デジタルノマド×投資の最適解

- **DB根拠**: 「Escape Your Office Job!」「How to Travel the World While Running a Business」「Retire abroad on $500 a month」
- **既存記事との差別化**: 既存の動画編集・AI副業と異なるライフスタイル設計の切り口
- **主要ソース**:
    - 「Escape Your Office Job! Be Location Independent」
    - 「How to Travel the World While Running a Business from Your Laptop」
    - 「Living richly in retirement: Retire abroad on $500 a month」

#### 5-3. 賃貸不動産オーナーは副業として成立するか？ — 現実的なP/L分析

- **DB根拠**: 「Is owning rental property worth it?」「Should You Buy a Vacation Rental?」「Real Estate: Buy or Rent?」
- **既存記事との差別化**: 既存は労働集約型副業。不動産投資を副業視点で分析する記事がない
- **主要ソース**:
    - 「Is owning rental property and being a landlord worth it?」
    - 「Should You Buy a Vacation Rental?」
    - 「Real Estate: Buy or Rent? - Early Retirement Now」
    - 「REITs pros and cons - Early Retirement Now」

---

## 推奨優先度

| 優先度 | テーマ                      | 理由                                                    |
| ------ | --------------------------- | ------------------------------------------------------- |
| A      | 資産形成 1-1（4%ルール）    | ERNの検証シリーズ3本が丸ごとDB内にあり素材が最も豊富    |
| A      | マクロ経済 2-2（ゴールド）  | Entity + 専門記事あり。2026年の金価格高騰と時事性も高い |
| A      | 個別株 4-1（半導体）        | Entity 6社登録済み。AI投資テーマとの接点が強い          |
| B      | 投資教育 3-3（DCA vs 一括） | 初心者向け鉄板テーマ。DB内に賛否両論の素材あり          |
| B      | 副業 5-1（FIRE後のリアル）  | ERN + Afford Anything の実体験記事が豊富                |
| C      | その他                      | DB素材はあるが追加リサーチが必要                        |
