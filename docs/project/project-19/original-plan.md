# 議論メモ: グラフDB品質指標の学術調査と定量評価フレームワーク設計

**日付**: 2026-03-19
**参加**: ユーザー + AI
**Neo4j Discussion ID**: `disc-2026-03-19-kg-quality-metrics`

## 背景・コンテキスト

research-neo4j（3,282ノード / 5,310リレーション）をAIによる創発的な投資仮説生成・経済見通しの基盤として活用するため、グラフDBの品質を定量的に測定・改善するフレームワークが必要。alphaxiv MCPを用いて学術論文を調査し、適用可能な指標体系を構築した。

## 論文調査結果

### Tier 1: KG品質評価フレームワーク

| 論文 | arXiv ID | 著者 / 機関 | 年 | 要点 |
|------|----------|------------|-----|------|
| Steps to KG Quality Assessment | 2208.07779 | Huaman / Univ. Innsbruck | 2022 | KG品質評価の体系的手順。品質次元の定義と測定方法 |
| Completeness & Consistency Analysis for Evolving KBs | 1811.12721 | Rashid et al. / Politecnico di Torino | 2018 | 進化するKBの完全性・一貫性分析。Silver/Gold Standard評価 |
| KG Quality Evaluation under Incomplete Information | 2212.00994 | Li et al. / South China Univ. | 2022 | 不完全情報下でのKG品質評価手法 |
| Class Granularity | 2411.06385 | Seo et al. / Naver | 2024 | KGの表現力を「粒度」で測定 |

### Tier 2: 金融ドメイン特化KG

| 論文 | arXiv ID | 著者 / 機関 | 年 | 要点 |
|------|----------|------------|-----|------|
| FinReflectKG-EvalBench | 2510.05710 | Dimino et al. / Domyn | 2025 | 金融KG専用の多次元評価ベンチマーク |
| FinDKG | 2407.10909 | Li & Passino / Imperial College | 2024 | 動的KGで金融市場トレンド検出 |
| CompanyKG | 2306.10649 | Cao et al. / EQT | 2024 | 投資業界の企業類似性定量化 |
| QuantMind | 2509.21507 | Wang et al. / CMU + NUS | 2025 | クオンツ向けKGフレームワーク |

### Tier 3: 仮説生成・検証

| 論文 | arXiv ID | 著者 / 機関 | 年 | 要点 |
|------|----------|------------|-----|------|
| Hypothesis Virtues in KGs | 1503.09137 | Novacek / Insight | 2015 | KGから仮説を生成し評価するフレームワーク |
| KGValidator | 2404.15923 | Boylan et al. / Quantexa | 2024 | LLMによるKG自動バリデーション |

## 7カテゴリの品質指標体系

### 1. 構造的指標 (Structural Metrics)

- **エッジ密度 (Edge Density)**: エッジ数 / (ノード数 * (ノード数-1))
- **平均次数 (Average Degree)**: 全ノードの平均リレーション数
- **連結性 (Connectivity)**: 最大連結成分のサイズ / 全ノード数
- **孤立ノード率 (Orphan Rate)**: リレーションなしノード / 全ノード

### 2. 完全性指標 (Completeness Metrics)

- **スキーマ完全性 (Schema Completeness)**: 定義済みプロパティのうち値が入っている割合
- **プロパティ完全性 (Property Completeness)**: 各ノードの非nullプロパティ率
- **ポピュレーション完全性 (Population Completeness)**: 対象ドメインのカバー率
- **リレーション完全性 (Relationship Completeness)**: 期待リレーションタイプの実在割合

### 3. 一貫性指標 (Consistency Metrics)

- **型一貫性 (Type Consistency)**: プロパティ値が期待型と一致する割合
- **制約違反率 (Constraint Violation Rate)**: ビジネスルール違反数
- **重複率 (Duplication Rate)**: 同一実体を指す複数ノードの割合
- **意味的一貫性 (Semantic Consistency)**: リレーション方向性・型の意味的正確性

### 4. 正確性指標 (Accuracy Metrics)

- **事実正確性 (Factual Accuracy)**: サンプルトリプルの正誤率
- **数値精度 (Numerical Precision)**: FinancialDataPoint等の数値正確性
- **時間的正確性 (Temporal Accuracy)**: 日付・期間情報の正確性

### 5. 適時性指標 (Timeliness Metrics)

- **鮮度 (Freshness)**: 最新ソース投入日からの経過日数
- **更新頻度 (Update Frequency)**: 単位期間あたりの新規ノード/リレーション追加数
- **時間カバレッジ (Temporal Coverage)**: データの時間的範囲

### 6. 金融ドメイン特化指標 (Finance-Specific Metrics)

- **エンティティカバレッジ**: 対象セクター/地域の企業カバー率
- **メトリクスカバレッジ**: 各企業の財務指標網羅率
- **クロスリファレンス度**: エンティティ間横断リレーション数

### 7. 発見可能性指標 (Discoverability Metrics)

- **パス多様性 (Path Diversity)**: 任意2ノード間の異なるパス数
- **ブリッジノード率**: 異なるクラスターを接続するノードの割合
- **セレンディピティスコア**: 想定外接続パターンの豊富さ

## ベースライン計測結果（2026-03-19）

優先指標として「発見可能性 (Discoverability)」を選択し、3サブ指標を計測。

### 指標1: パス多様性 (Path Diversity)

| 指標 | 値 | 判定 |
|------|-----|------|
| Entity数 | 197 | - |
| 全Entityペア | 19,306 | - |
| **到達可能ペア** | **12,419 (64.3%)** | **中** |
| 平均パス長 | 4.08 hops | やや遠い（理想は2-3） |
| Entity孤立率 | 18.3%（36ノード） | 問題あり |

### 指標2: ブリッジノード率 (Bridge Node Ratio)

| 指標 | 値 | 判定 |
|------|-----|------|
| **全体ブリッジ率** | **56.2%** | **中-高** |
| Source由来 | 1,129/1,923 (58.7%) | Source偏重 |
| Entity由来 | 110/197 (55.8%) | Entity自体は中程度 |
| Topic由来 | 45/75 (60%) | Topicはハブ機能あり |

### 指標3: セレンディピティスコア

| 指標 | 値 | 判定 |
|------|-----|------|
| Cross-cluster エッジ | 5,354 (97.5%) | スキーマ構造上の特性 |
| **Intra-cluster エッジ** | **138 (2.5%)** | - |
| **Entity間直接リレーション** | **19本** | **致命的不足** |
| 内訳 | COMPETES(10), PARTNERS(4), SUBSIDIARY(2), CUSTOMER(2), INVESTED(1) | - |

### ラベル別統計

| ラベル | ノード数 | 平均次数 | 孤立率 |
|--------|---------|---------|--------|
| Source | 1,253 | 2.66 | 0% |
| Claim | 746 | 1.69 | 0% |
| Chunk | 658 | 1.0 | 0% |
| Fact | 224 | 2.22 | 0% |
| Entity | 197 | 8.32 | 18.3% |
| FinancialDataPoint | 175 | 5.0 | 0% |
| Topic | 75 | 30.63 | 0% |
| Metric | 35 | 4.34 | 0% |
| Insight | 23 | 1.52 | 0% |
| FiscalPeriod | 16 | 12.25 | 0% |
| Author | 9 | 2.0 | 0% |
| Stance | 9 | 3.0 | 0% |

### 最大ボトルネック

**Entity間直接リレーションが 197 Entity に対して 19本（1ノードあたり0.1本未満）**

→ AIが銘柄間の横断的関係（サプライチェーン、競合、セクター連動）を発見する基盤が不足。

## 決定事項

1. KG品質を7カテゴリで評価する体系を採用 (`dec-2026-03-19-001`)
2. 発見可能性を最優先指標とし、ベースライン計測完了 (`dec-2026-03-19-002`)

## アクションアイテム

- [x] 指標の優先順位付け議論 → 発見可能性を最優先に決定
- [x] 発見可能性3サブ指標のベースライン計測完了
- [x] **Phase 1実行完了**: Entity間推論リレーション自動生成 (`act-2026-03-19-001` partial)
  - CO_MENTIONED_WITH: 173本（閾値1、Claim共起ベース）
  - SHARES_TOPIC: 682本（閾値3+、Topic媒介ベース）
  - **Before/After**: 19→874本（46倍）、平均パス長 4.08→3.40 hops、Entity間接続率 50.8%
- [x] **Phase 2実行完了**: Sectorノード化 + Entity属性エンリッチメント + 重複解消 (`act-2026-03-19-002`)
  - GICS 11 Sectorノード作成（aliases, gics_code付き）
  - 102社全companyをIN_SECTORリレーションで接続（confidence: official/inferred/approximate）
  - 重複ノード7件解消（Nvidia/NVIDIA, True Corp/True Corporation, Lao Telecom x2, M1 x2, U Mobile x2, Unitel x2, MobiFone x2）
  - SAME_SECTORは非正規化のため生成せず（IN_SECTOR経由クエリで代替）
  - **Before/After**: Entity完全孤立 36→18件、リレーション 5,310→6,441
- [x] **Phase 3実行完了**: LLMベースEntity間関係タイプ推論
  - CO_MENTIONED_WITH(shared>=2)の27ペアからClaimコンテキスト+セクター情報で推論
  - 17本の高精度リレーション生成（method=llm_inferred, confidence=high/medium）
  - 新規タイプ: LED_BY(Tesla→Elon Musk), OPERATES_IN(Nvidia→China), INFLUENCES(Trump→dollar/China)
  - 強化: COMPETES_WITH +7(Anthropic↔OpenAI, Meta↔Google, Meta↔OpenAI等), INVESTED_IN +2(Microsoft→OpenAI, Nvidia→CoreWeave), CUSTOMER_OF +2(CoreWeave→Nvidia, Microsoft→Nvidia)
  - Entity間リレーションタイプ: 5種→**10種**
- [ ] **Phase 4-A**: 発見可能性指標の定期計測スクリプト化（品質ダッシュボード） (`act-2026-03-19-003`)
- [ ] **Phase 4-B**: Entity孤立ノード97件の接続強化 (`act-2026-03-19-004` 更新: 36→97件はEntity-Entity間。全体孤立36件は変化なし)

---

## 第2回調査: スキーマ設計・正規化・Entity間関係推論の学術深掘り

**日付**: 2026-03-19（同日追記）
**Neo4j Discussion ID**: `disc-2026-03-19-kg-quality-metrics-v2`

### 新規発見論文

#### Tier A: グラフスキーマ設計・正規化理論

| 論文 | arXiv ID | 著者 / 機関 | 年 | 要点 |
|------|----------|------------|-----|------|
| A Graph-Native Approach to Normalization | 2603.02995 | Schrott et al. / TU Wien | 2026 | LPG向け初の体系的正規化理論。GO-FD（Graph Object Functional Dependencies）でノード内・エッジ内・ノード間の冗長性を検出。GN-1NF/GN-2NF/GN-NF正規形を定義 |
| PG-HIVE: Hybrid Incremental Schema Discovery | 2512.01092 | Sideri et al. / FORTH | 2025 | Neo4jからのスキーマ自動発見。LSHベースクラスタリングで潜在ノード・エッジ型を検出。インクリメンタル対応 |
| Common Foundations for SHACL, ShEx, and PG-Schema | 2502.01295 | Ahmetaj et al. / 13大学共同 | 2025 | RDFとプロパティグラフの制約言語統一基盤。PG-Schema標準化の理論的基盤 |
| Repairing Property Graphs under PG-Constraints | 2602.05503 | Spinrath et al. | 2026 | PG制約違反の自動検出・修復アルゴリズム |
| Schema Validation and Evolution for Graph Databases | 1902.06427 | Bonifati et al. / Neo4j共著 | 2019 | PGのDDL標準化議論。スキーマ進化の理論 |
| Is SHACL Suitable for Data Quality Assessment? | 2507.22305 | Cortés et al. / HPI | 2025 | 15品質次元のうちSHACLがカバーする範囲を検証 |
| Schema-Based Query Optimisation for Graph Databases | 2403.01863 | Sharma et al. / CNRS | 2024 | スキーマ情報を活用したグラフクエリ最適化 |
| MV4PG: Materialized Views for Property Graphs | 2411.18847 | Xu et al. / USTC | 2024 | PGのマテリアライズドビューで重複クエリパターンを最適化 |

#### Tier B: Entity間関係推論・KG Completion

| 論文 | arXiv ID | 著者 / 機関 | 年 | 要点 |
|------|----------|------------|-----|------|
| InterCorpRel-LLM | 2510.09735 | Sun et al. / Peking Univ. | 2025 | GNN+LLMハイブリッドで企業間関係推論。Supply prediction F-score 0.8543（GPT-5: 0.2287） |
| Company Competition Graph | 2304.00323 | Zhang et al. / Wharton | 2023 | SEC 10-KからNER+リンキングで競合関係自動抽出。S&P500の83%回収 |
| JPEC: Competitor Retrieval in Financial KGs | 2411.02692 | Ding et al. / JPMorgan | 2024 | GNNで金融KGから競合企業を検索 |
| FinKario: Event-Enhanced Financial KG | 2508.00961 | Li et al. | 2025 | イベント強化型金融KG構築。エクイティリサーチレポートからの構造抽出 |
| Multi-perspective KG Completion with LLMs | 2403.01972 | Xu et al. / USTC | 2024 | LLMによる多視点KG補完 |
| GS-KGC: Generative Subgraph-based KGC | 2408.10819 | Yang et al. / Sun Yat-Sen | 2024 | サブグラフベースのKG補完フレームワーク |
| Data Considerations for Supply Chain Networks | 2107.10609 | Aziz et al. / Cambridge | 2021 | サプライチェーンネットワークのグラフ表現学習 |

#### Tier C: KG品質評価・バリデーション（追加）

| 論文 | arXiv ID | 著者 / 機関 | 年 | 要点 |
|------|----------|------------|-----|------|
| FinReflectKG: Agentic Construction and Evaluation | 2508.17906 | Dimino et al. / Domyn | 2025 | 金融KG構築パイプライン。Reflection-driven agenticワークフロー。4軸評価（CheckRules/Coverage/Diversity/LLM-as-a-Judge） |
| KGpipe: Pipeline Generation for KG Integration | 2511.18364 | 2025 | KG構築パイプラインの自動生成と評価 |
| Systematic Evaluation of KG Repair with LLMs | 2507.22419 | Lin et al. | 2025 | SHACL制約違反のLLM修復を体系的に評価 |
| KG Validation through Weighted Knowledge Sources | 2104.12622 | Huaman et al. / Innsbruck | 2021 | 重み付き知識ソースによるKGバリデーション |
| A Study of the Quality of Wikidata | 2107.00156 | Shenoy et al. / USC | 2021 | Wikidataの品質フレームワーク。大規模KGの品質次元分析 |

### 学術知見から導出された新施策候補

| ID | 施策 | 根拠論文 | 優先度 |
|----|------|---------|--------|
| NEW-001 | スキーマ冗長性のGO-FD分析 | 2603.02995 | 低-中 |
| NEW-002 | Neo4j制約の形式化（NOT NULL/型/UNIQUE） | 2502.01295, 2602.05503 | 中 |
| NEW-003 | LLMベースKGバリデーション | 2404.15923, 2508.17906 | 低 |
| NEW-004 | FinReflectKG風多次元品質ダッシュボード | 2508.17906 | 中 |

### 推奨4段階ロードマップ（暫定、dec-2026-03-19-003）

| Phase | 施策 | 状態 |
|-------|------|------|
| 1: 基盤整備 | Entity属性エンリッチメント + Neo4j制約形式化 | 未着手 |
| 2: 接続強化 | 共起ベース→Topic媒介→LLM推論でEntity間リレーション劇的強化 | 未着手 |
| 3: 品質管理 | FinReflectKG風多次元ダッシュボード | 未着手 |
| 4: 継続改善 | GO-FD正規化レビュー + 残存孤立ノード対応 | 未着手 |

---

## 第3回調査: GraphRAG・Temporal KG・Event Ripple Effect の深掘り

**日付**: 2026-03-19（同日追記）

### Tier D: GraphRAG（KG + LLM統合推論）

| 論文 | arXiv ID | 著者 / 機関 | 年 | 要点 |
|------|----------|------------|-----|------|
| **GraphRAFT** | 2504.05478 | Clemedtson & Shi / **Neo4j** | 2025 | Neo4j KGに対するRAG。Constrained DecodingでCypherクエリの正確性を保証。STaRK-primeでHit@1 63.7%（SOTA+22.8pt）。KGのスキーマ品質がGraphRAG性能に直結することを実証 |
| Graph-R1 | 2507.21892 | Luo et al. / NTU | 2025 | End-to-end RL でGraphRAGを最適化。1,902 visits, 105 likes |
| Graph RAG Survey | 2408.08921 | Peng et al. / Ant Group + Zhejiang | 2024 | GraphRAGの包括的サーベイ。8,898 visits |
| When to use Graphs in RAG | 2506.05690 | Xiang et al. / PolyU | 2025 | GraphRAGが有効な条件の体系的分析 |
| RAG vs. GraphRAG | 2502.11371 | Han et al. / MSU + Meta | 2025 | RAGとGraphRAGの系統的比較評価 |
| GDS Agent for Graph Algorithmic Reasoning | 2508.20637 | Neo4j関連 | 2025 | Neo4j GDSのエージェント活用。Claude 4への言及あり |

#### GraphRAFT の research-neo4j への示唆

- **スキーマ品質がGraphRAG性能を決定的に左右する**: Constrained Decodingはスキーマに基づいて有効なCypherクエリ空間を制約する → スキーマが不十分だと有効なクエリも制限される
- **Entity属性の充実度がEntity Resolution精度に直結**: ベクトル類似度検索で entities をgrounding → Entity の full_name, aliases, sector 等の属性が豊富なほど精度向上
- **Multi-hop queries の前提として Entity間リレーションが必須**: 2-hop 以上のクエリテンプレートが高精度回答に寄与 → 現状の Entity間19本ではmulti-hopが成立しない

### Tier E: Temporal KG・Financial Event Propagation

| 論文 | arXiv ID | 著者 / 機関 | 年 | 要点 |
|------|----------|------------|-----|------|
| **FinRipple** | 2505.23826 | Xu et al. / HKUST(GZ) | 2025 | イベントの波及効果（Ripple Effect）をLLM+時変KGで予測。CAPM残差でR²=0.340。サプライチェーン・リーダーシップ・特許・ファンド保有の4種関係を時変KGに統合。ポートフォリオ最適化でSharpe 1.153達成 |
| Network Momentum across Asset Classes | 2308.11294 | Pu et al. / Oxford | 2023 | ネットワークモメンタム（企業間関係を通じたモメンタムの波及） |
| Systemic Risk Radar | 2512.17185 | Neela | 2025 | マルチレイヤーグラフで金融システミックリスクの早期警告 |
| CAMEF | 2502.04592 | Zhang et al. | 2025 | マクロ経済イベントの因果的金融予測 |
| Predictive AI with External Knowledge for Stocks | 2504.20058 | Dukkipati et al. / IISc | 2025 | 外部知識注入による株価予測。346 visits |
| KG Enhanced Event Extraction in Finance | 2109.02592 | Guo et al. / ShanghaiTech | 2021 | KG強化型金融イベント抽出 |
| FinRipple: Evidence Subgraphs for Risk | 2503.06441 | Du et al. / Beihang + Ant | 2025 | 因果推論でリスク検出のエビデンスサブグラフを特定 |

#### FinRipple の research-neo4j への示唆

- **Entity間関係の4カテゴリ設計**: リーダーシップ、ファンド保有、特許、サプライチェーン → 現在のCOMPETES/PARTNERS/SUBSIDIARY/CUSTOMER/INVESTEDに加え、SHARES_BOARD、SAME_FUND_HOLDING、TECH_OVERLAP等の関係タイプが有用
- **時変KGの必要性**: 固定的な関係ではなく、時間とともに変化する関係を表現 → FiscalPeriodとの連携で実現可能
- **サプライチェーン関係が最も重要**: Ablation studyでサプライチェーン除去が最大の性能低下 → SUPPLIER_OF リレーション優先
- **CAPM残差による品質評価**: KGの品質を「説明力」で定量評価するアイデア → 品質ダッシュボードに組み込み可能

### 調査全体の統合（3回分）

#### 論文総数: 50+ 論文（重複除く）

#### 6つの研究領域と research-neo4j への適用マップ

| 領域 | 代表論文 | research-neo4j への適用 | 優先度 |
|------|---------|----------------------|--------|
| **A. KG品質評価** | Steps to KG Quality, FinReflectKG | 7カテゴリ指標体系（済み）+ CheckRules/LLM-as-Judge追加 | 済+中 |
| **B. グラフスキーマ設計** | Graph-Native Normalization, PG-HIVE, PG-Schema | GO-FD冗長性分析 + Neo4j制約形式化 | 中 |
| **C. Entity間関係推論** | InterCorpRel-LLM, Company Competition Graph, JPEC | 共起→Topic媒介→LLM推論の3段階アプローチ | **最高** |
| **D. GraphRAG統合** | GraphRAFT, Graph-R1, GRAG | スキーマ品質がGraphRAG精度を決定 → B,Cが前提条件 | 高（下流） |
| **E. Temporal KG** | FinRipple, FinDKG, TKG Completion survey | 時変Entity関係の表現。FiscalPeriod連携 | 中-高 |
| **F. Financial Event KG** | FinRipple, KG Enhanced Event Extraction, CAMEF | イベントノード追加検討。Claim拡張で対応可能 | 中 |

## 本日の最終結果（Phase 1-3 + Phase 4プラン）

| 指標 | 開始時 | 完了時 | 改善 |
|------|--------|-------|------|
| Entity間リレーション | 19本 (5種) | 888本 (10種) | 47倍、+5タイプ |
| 全リレーション | 5,310 | 6,441 | +21% |
| ノード数 | 3,411 | 3,425 | +Sector11, -重複7 |
| Entity完全孤立 | 36件 | 18件 | 50%減 |
| 平均パス長 | 4.08 hops | ~3.4 hops | 0.68短縮 |
| company→Sector接続率 | 0% | 100% | 全102社 |
| SICコード付き企業 | 0社 | 32社 | SEC EDGAR検証済 |
| 重複ノード | 7件 | 0件 | 解消 |

## 次回の議論・実装トピック

- [ ] **Phase 4-A**: KG品質ダッシュボード実装（プラン策定済み: `docs/plan/2026-03-19_kg-quality-dashboard-plan.md`）
- [ ] **Phase 4-B**: GraphRAG実験（基本KG-RAGパイプライン + 投資仮説生成）
- [ ] Entity表記揺れ対策の本格実装（aliases充実 + ファジーマッチング）
- [ ] GraphRAFT方式のGraphRAG統合の検討
- [ ] FinRipple風の時変KG・イベント波及モデルの設計
- [ ] 残り18件の完全孤立ノード対応
