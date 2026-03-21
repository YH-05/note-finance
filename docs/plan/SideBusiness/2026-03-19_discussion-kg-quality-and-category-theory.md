# 議論メモ: KG品質運用レイヤー + 圏論に基づくグラフ構造改善

**日付**: 2026-03-19
**参加**: ユーザー + AI

## 背景・コンテキスト

KG品質計測の基盤（`kg_quality_metrics.py` 2,378行、7カテゴリ）は整っていたが、
運用面（定期実行・アラート・accuracy実装）が未整備。さらに「AIがグラフから創発的発見を
行えるか」という観点が欠如していた。

## セッションの流れ

### Part 1: KG品質運用レイヤー実装（4 Phase）

推奨順序 D→A→C→B で実装。180テスト全パス。

| Phase | 内容 | 成果 |
|-------|------|------|
| D | データ修正 | entity_id NULL 77件補完、レガシーRel 110件リネーム |
| A | 定期実行 | Makefile kg-quality、--exit-code/--min-score、CI dry-run、週次ラッパー |
| C | accuracy | LLM-as-Judge 3軸評価、キャッシュ30日、--skip-accuracy/--accuracy-sample-size |
| B | アラート | -10pt critical/-5pt warning、CheckRule 95%、GitHub Issue自動作成 |

### Part 2: Claude Code LLM-as-Judge 方式の確立

ANTHROPIC_API_KEY がシェル環境変数に未設定 → Claude Code 自身が MCP 経由で
Fact/Claim をサンプリングし直接評価する方式に決定。キャッシュ（SHA-256キー）経由で
Python スクリプトと統合。

### Part 3: /kg-quality-check スキル開発

5 Phase 構成のスキル+スラッシュコマンドを新設:
1. 6カテゴリ Python 計測
2. Claude Code LLM-as-Judge accuracy 評価（20件サンプル）
3. 創発的発見ポテンシャル評価（5プローブ+4軸自己評価）
4. 統合スナップショット再計測
5. レポート出力

### Part 4: 圏論研究調査（12本 → research-neo4j 保存）

alphaxiv MCP で検索、key papers のコンテンツ取得、graph-queue パイプライン経由で投入。

| 論文 | 核心概念 | KGへの示唆 |
|------|---------|-----------|
| Boudourides 2026 | Sheaf Semantics for KG | Grothendieck位相→局所-大域推論 |
| Krasnovsky 2025 | Sheaf-Theoretic Causal Emergence | マクロがミクロより情報量大→因果的創発指標 |
| Spivak 2011 | Ologs | 圏としてのオントロジー設計の原点 |
| Buehler 2025 | Agentic Deep Graph Reasoning | 自律KG拡張→スケールフリー+ブリッジ創発 |
| Li et al. 2024 | Categorical Emergent Effects | ネットワークのミクロ→マクロファンクター |
| Sennesh et al. 2023 | DisCoPyro | SMC+確率的プログラミングで構造学習 |

### Part 5: 圏論に基づく6提案の全実装

| # | 提案 | 投入件数 |
|---|------|--------:|
| 1 | CONTRADICTS + SUPPORTED_BY 活性化 | 5,393 |
| 2 | CAUSES 拡充 | 42 |
| 3 | Topic間 INFLUENCES | 1,635 |
| 4 | Insight DERIVED_FROM | 1,686 |
| 5 | SHARES_TOPIC analogy | 2,363 |
| 6 | path_weight + Reified Path | 1,756 |
| **計** | **リレーション +49%増** | **12,875** |

### Part 6: パイプライン修正

`emit_graph_queue.py` に `_build_wr_causal_rels()` 追加。
入力 JSON の `causal_links` で CAUSES/CONTRADICTS/SUPPORTED_BY/DERIVED_FROM/INFLUENCES を指定可能に。

## 決定事項

1. accuracy 評価は Claude Code 直接実行方式（ANTHROPIC_API_KEY 不要）
2. `/kg-quality-check` スキル+コマンド新設（5 Phase 構成）
3. 創発的発見ポテンシャルを KG 品質の評価軸に追加（4軸: Cross-Domain Bridging / Hypothesis Novelty / Evidence Density / Actionability）
4. 圏論研究12本を research-neo4j に永続化（Source 12, Fact 15, Entity 12, Topic 5）
5. 6提案全実装でリレーション +49%（25,773→38,282）
6. パイプラインに causal_links サポート追加

## アクションアイテム

- [ ] `/kg-quality-check` を週次実行し創発的発見ポテンシャルの推移をトラッキング（優先度: 中）
- [ ] CAUSES リレーションを3段チェーン（マクロ→セクター→企業）に拡充（目標200件）（優先度: 中）
- [ ] 圏論研究をnote記事化（Sheaf理論×KG×AIの創発的発見）（優先度: 低）

## 成果物一覧

### 新規ファイル
- `scripts/fix_entity_id_null.py` — entity_id NULL 補完
- `scripts/fix_legacy_relationships.py` — レガシーリレーションリネーム
- `scripts/kg_accuracy_judge.py` — LLM-as-Judge accuracy 評価モジュール
- `scripts/kg_quality_alert.py` — アラート・GitHub Issue 自動作成
- `scripts/kg_quality_weekly.sh` — 週次実行ラッパー
- `data/config/kg_accuracy_config.yaml` — accuracy 評価設定
- `.claude/skills/kg-quality-check/SKILL.md` — KG品質チェックスキル
- `.claude/commands/kg-quality-check.md` — スラッシュコマンド
- `tests/scripts/test_fix_entity_id_null.py`
- `tests/scripts/test_fix_legacy_relationships.py`
- `tests/scripts/test_kg_accuracy_judge.py`
- `tests/scripts/test_kg_quality_alert.py`

### 修正ファイル
- `scripts/kg_quality_metrics.py` — --exit-code, --min-score, --skip-accuracy, --accuracy-sample-size, --alert, _find_latest_snapshot exclude_date
- `scripts/emit_graph_queue.py` — _build_wr_causal_rels() 追加
- `Makefile` — kg-quality ターゲット追加
- `.github/workflows/ci.yml` — kg-quality dry-run job 追加

## Neo4j 保存先

- Discussion: `disc-2026-03-19-kg-quality-and-category-theory`
- Decisions: `dec-2026-03-19-{llm-as-judge-claude-code, kg-quality-check-skill, category-theory-graph-improvement, pipeline-causal-links}`
- ActionItems: `act-2026-03-19-{005..007}`
- 前回Discussion: `disc-2026-03-19-kg-quality-ops-layer`（RESULTED_IN で接続）
