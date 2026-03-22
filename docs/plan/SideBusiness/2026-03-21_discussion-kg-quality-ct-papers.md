# 議論メモ: KG品質チェック + 圏論↔金融ギャップ分析 + 論文42本投入

**日付**: 2026-03-21
**参加**: ユーザー + AI

## 背景・コンテキスト

research-neo4j の定期品質チェックを実施。KG品質ダッシュボード（7カテゴリ）の計測に加え、圏論クラスタと金融ドメインの孤立問題を調査し、NAS Papers の新規論文を一括投入した。

## 実施内容

### 1. KG品質チェック（Overall 60.7/B）

| カテゴリ | スコア | 主な課題 |
|---------|------:|---------|
| structural | 75.0 | Edge Density低 |
| completeness | 50.0 | Property Coverage 86.6%（目標95%） |
| consistency | 50.0 | 制約違反1件 |
| accuracy | 50.0 | **Source Grounding 致命的（全件0.1）** |
| timeliness | 66.7 | Coverage Span 3日のみ |
| finance_specific | 66.7 | Metrics/Company 2.07 |
| discoverability | 66.7 | Path Diversity低 |

### 2. Accuracy評価（LLM-as-Judge）

20件のFact/Claimサンプルを3軸評価:
- Factual Correctness: **0.715**（良好）
- Source Grounding: **0.100**（致命的 — 全件ソース未接続）
- Temporal Validity: **0.530**（中程度）
- Overall: **0.475**

### 3. 創発的発見ポテンシャル（Discovery Score: 0.66）

4件の発見・仮説を構築:
1. インドネシア・マクロ-テレコム-コモディティ連環仮説
2. ISAT EBITDA Margin 4年連続低下 vs AI TechCo投資の矛盾
3. ASEANテレコム比較データの完全欠落
4. 圏論クラスタの金融ドメインからの孤立

### 4. 圏論↔金融ギャップ分析（alphaxiv調査）

alphaxivで75件の論文を検索。3つの接続レイヤーを発見:

**レイヤー1: CT直接応用（萌芽期、2025〜）**
- Ghrist et al. "Clearing Sections of Lattice Liability Networks" (2503.17836)
- Ghani, Hedges et al. "Compositional Game Theory" (1603.04641)
- Pollicino "CT Framework for Macroeconomic Modeling: Argentina" (2508.13233)

**レイヤー2: TDA間接橋渡し（成熟分野）**
- Goel et al. "Class of Topological Portfolios" (2601.03974)
- Gidea et al. "Why TDA Detects Financial Bubbles" (2304.06877)
- Wolf & Monod "Sheaf-Theoretic Community Detection" (2310.05767)

**レイヤー3: 金融KG（CTとは無関係）**
- FinDKG, FinReflectKG, CompanyKG 等

### 5. 論文投入（合計42本）

| グループ | 本数 | Entity | Fact | Claim | Rel |
|---------|------|--------|------|-------|-----|
| TDA/CT橋渡し論文 | 5 | ~84 | ~115 | ~30 | ~780 |
| JSAI SIG-FIN-036 (2026) | 34 | ~400 | ~300 | ~120 | ~1,900 |
| その他（言語処理学会、arXiv） | 3 | ~16 | ~10 | ~5 | ~60 |
| **合計** | **42** | **~500** | **~425** | **~155** | **~2,740** |

## 決定事項

1. **圏論と金融を無理に接続しない**: 孤立には構造的理由がある（抽象レベル不一致、萌芽的研究のみ）
2. **TDA間接接続戦略を採用**: Sheaf Theory → Persistent Homology → Financial Analysis の経路
3. **Source Grounding修復が最優先**: accuracyスコア+15pt改善見込み

## アクションアイテム

- [ ] **[高]** emit_graph_queue.py の STATES_FACT/MAKES_CLAIM リレーションチェーン修復
- [ ] **[中]** ASEAN テレコムデータ補完（True Corp, AIS, XLSmart）
- [ ] **[中]** Stance ノード summary 欠落の修復（76件）
- [ ] **[低]** ノイズ Fact/Claim フィルタリングゲート導入

## 次回の議論トピック

- Source Grounding修復の実装方針
- JSAI SIG-FIN-036 論文のEntity重複整理（同一概念の異表記統合）
- 投入済み42本の論文からの創発的発見の再評価
