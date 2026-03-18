# 議論メモ: ISAT IJ 情報ギャップ調査

**日付**: 2026-03-18
**参加**: ユーザー + AI

## 背景・コンテキスト

research-neo4j に蓄積された ISAT IJ (Indosat Ooredoo Hutchison) のデータから技術全体像を抽出。
既存の Insight ノードで4つの情報ギャップが特定されていた:
1. GPUaaS事業の実現可能性（顧客名、GPU調達先、データセンター詳細）
2. ARPU持続性の要因分解（値上げ vs ミックス改善）
3. FibreCo売却条件（買い手候補、マルチプル比較、リースバック条件）
4. 5Gオークション財務インパクト（過去の落札価格、ASEAN比較、財務シミュレーション）

## 実施内容

### Phase 1: 技術全体像の抽出

research-neo4j から Indosat Ooredoo Hutchison に紐づく全データを抽出:
- Entity: `Indosat Ooredoo Hutchison::company`
- 接続ノード: Fact, Claim, Insight, FinancialDataPoint, Stance, Topic (ASEAN Telecom)
- 7カテゴリに整理: モバイルネットワーク、ファイバー、AI/GPUaaS、デジタルプラットフォーム、タワー、データトラフィック、収益構成

### Phase 2: 4エージェント並列Web調査

4つのリサーチエージェントを並列起動し、各ギャップを網羅的に調査:

| エージェント | 対象 | 所要時間 | ソース数 |
|------------|------|---------|---------|
| gpuaas-research | GPUaaS事業 | ~5.5分 | 33 |
| arpu-research | ARPU持続性 | ~5.5分 | 29 |
| fibreco-research | FibreCo売却 | ~5.3分 | 19 |
| spectrum-research | 5Gオークション | ~5.4分 | 24 |
| **合計** | | | **105** |

### Phase 3: research-neo4j への投入

調査結果を KG v2 スキーマに準拠して投入:

| ノード種別 | 件数 |
|-----------|------|
| Source | 1 |
| Entity | 12（新規） |
| Fact | 19 |
| Claim | 4 |
| Insight | 4 |
| FinancialDataPoint | 9 |
| リレーション | 70 |

### Phase 4: データ品質検証

- Bloomberg Law (#73) のペイウォール記事について、取得できたのは冒頭の無料プレビューのみであることを確認
- Fact/FinancialDataPoint はスクレイピング結果からの直接取得で問題なし
- Claim/Insight は複数ソースの AI 合成であることが判明 → source_context に明記

## 決定事項

1. **4エージェント並列調査を実施し、research-neo4j に結果を投入する**
   - 背景: 既存 Insight で情報ギャップが特定されていた
2. **AI 合成の Claim/Insight には source_context に「AI synthesis based on ...」と明記する**
   - 背景: ペイウォール記事の検証でデータの出自の透明性が重要と判明
3. **graph-queue JSON と Neo4j の source_context を同期し整合性を保つ**
   - 背景: Neo4j のみ更新してファイルが古いままだと不整合が生じる

## 主要調査結果サマリー

### GPUaaS: 6社+の顧客判明
- INF Tech (~$100M, GB200 NVL72 x 2,304 GPU)
- Tanla Platforms, GoTo, Accenture, Hippocratic AI
- 20社+の銀行・コモディティ企業（具体名非公開）
- BDx JV: 10MW稼働 → 1GW目標 (2030年)

### ARPU: Telkomsel を逆転
- IDR 44,000 (4Q25) > Telkomsel IDR 43,400 (3Q25)
- 主因: 料金値上げ（スターターパック IDR 35,000 統一）+ ミックス改善 + SIM整理
- Data yield 底打ちサイン（implied yield +22-34%）

### FibreCo: 買い手確定
- Arsari Group + Northstar Group コンソーシアム (Dec 2025 IA締結)
- EV: IDR 14.6T (~$870M), EV/EBITDA ~8x
- 純手取額 ~$700M, FibreCo IPO Q3 2026予定

### 5Gスペクトラム: 財務余力十分
- 700MHz + 2.6GHz, Q2 2026予定
- ベースケース: ND/EBITDA 0.39x → ~0.52x
- 最大緩和材料: FibreCo $700M がほぼ同時期に流入

## アクションアイテム

- [ ] **[高]** ISAT IJ Initial Report 執筆（research-neo4j データ活用）
- [ ] **[中]** XLSmart データ補完（競合3社分析用）
- [ ] **[中]** 5G スペクトラムオークション結果フォロー（Q2 2026 後）
- [ ] **[中]** FibreCo IPO フォロー（Q3 2026）
- [ ] **[低]** AI 合成データ透明性ルールを .claude/rules/ に標準化検討

---

## Session 2: research-neo4j 構造診断 & 改善 (2026-03-18 夕方)

### 診断: 構造的障壁

AIがグラフトラバーサルで投資仮説を構築する際の障壁を6項目特定:

1. **Entity間リレーションの完全欠如** [Critical] — COMPETES_WITH/PARTNERS_WITH/SUBSIDIARY_OF = 0件
2. **Entityのsector/industryが全てnull** [High] — セクター起点の探索不可
3. **ISATのTopicタグが1つだけ** [High] — Sourceの9 Topicが未伝播
4. **FinancialDataPointの4件がFiscalPeriod未接続** [Medium] — GPUaaS Revenue等
5. **Claimのas_of_dateプロパティがない** [Medium] — 時系列センチメント分析不可
6. **Sourceが1件に集約されすぎ** [Low] — 個別レポートが未分離

### 実行結果

#### Action 1: graph-queue投入
- `isat-research-gaps-2026-03-18.json` を research-neo4j に投入
- 15 Entity, 19 Fact, 4 Claim, 4 Insight, 9 FDP, 1 Source + 全リレーション

#### Action 2: Entity間リレーション追加 (19件)
- COMPETES_WITH: ISAT↔Telkomsel↔XL Axiata↔XLSmart (12件)
- SUBSIDIARY_OF: Telkomsel→Telkom, Mitratel→Telkom (2件)
- PARTNERS_WITH: ISAT→NVIDIA, ISAT→GoTo, ISAT→BDx (3件)
- CUSTOMER_OF: INF Tech→ISAT, Tanla→ISAT (2件)
- INVESTED_IN: Arsari Group→ISAT (1件, FibreCo 55%取得)

#### Action 3: Entity sector/industry一括付与 (15 Entity)
- Telecommunications: 7社 (ISAT, TLKM, Telkomsel, XL Axiata, XLSmart, Smartfren, Link Net)
- Technology: 4社 (NVIDIA, GoTo, BDx Indonesia, INF Tech, Tanla)
- その他: Mitratel(Tower), Arsari(Conglomerate), Northstar(PE), Komdigi(Government)

#### Action 4: Entity→Topic TAGGED伝播 (556件)
- Claim→Entity→Topic: 30件
- Source→Claim→Entity→Topic: 526件
- ISATのTopicは1件→多数に拡大

### 追加決定事項

4. **EXCL/XLSmartの財務時系列データ補完は手元にデータがないため今後対応**
5. **Stance/Claimの時間情報設計は既存パターンの調査結果を踏まえて方針決定**

### 更新アクションアイテム

- [x] **[高]** graph-queue投入完了
- [x] **[高]** Entity間リレーション追加完了 (19件)
- [x] **[高]** sector/industry一括付与完了 (15 Entity)
- [x] **[高]** Topic TAGGED伝播完了 (556件)
- [ ] **[高]** ISAT IJ Initial Report 執筆（research-neo4j データ活用）
- [ ] **[中]** XLSmart データ補完（競合3社分析用）— セルサイドレポート入手待ち
- [ ] **[中]** Stance/Claim時間情報の設計方針決定
- [ ] **[中]** 5G スペクトラムオークション結果フォロー（Q2 2026 後）
- [ ] **[中]** FibreCo IPO フォロー（Q3 2026）

## 保存先

| 保存先 | 内容 |
|--------|------|
| note-neo4j | Discussion `disc-2026-03-18-isat-research-gaps` + Decision 5件 + ActionItem 6件 |
| research-neo4j | Entity 15件 + Fact 19件 + Claim 4件 + Insight 4件 + FDP 9件 + Source 1件 + リレーション575件 |
| ファイル | `data/graph-queue/isat-research-gaps-2026-03-18.json` |
| ドキュメント | `docs/plan/SideBusiness/2026-03-18_discussion-isat-research-gaps.md`（本ファイル） |
