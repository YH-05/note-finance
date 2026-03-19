# Phase 4-A: KG品質ダッシュボード実装計画

## Context

research-neo4j（3,425ノード/6,441リレーション）の品質を定量的に計測・追跡するスクリプトを実装する。Phase 1-3でEntity間リレーション19→888本、Sectorノード化、重複解消を実施済み。これらの改善効果を定量化し、今後の品質改善のROIを測定する基盤が必要。

学術論文調査（FinReflectKG, Steps to KG Quality Assessment等）で定義した7カテゴリの品質指標 + FinReflectKG CheckRules + Shannon Entropy分析を1本のPythonスクリプトで実装する。

## 実装対象

**新規ファイル**: `scripts/kg_quality_metrics.py`（単一ファイル、800-1000行）

**出力先**: `data/processed/kg_quality/snapshot_{date}.json`

## 参照ファイル

| ファイル | 用途 |
|---------|------|
| `scripts/validate_neo4j_schema.py` | CLI構造・Neo4j接続・ロギングのパターン踏襲 |
| `data/config/knowledge-graph-schema.yaml` | スキーマ定義（完全性・一貫性チェックのSSoT） |
| `scripts/classify_authority_level.py` | research-neo4j (port 7688) 接続パターン |

## モジュール構成

```
scripts/kg_quality_metrics.py
├── Constants: THRESHOLDS, ALLOWED_ENTITY_TYPES, DEFAULT_URI=bolt://localhost:7688
├── DataClasses: MetricValue, CategoryResult, CheckRuleResult, QualitySnapshot
├── Infrastructure: create_driver(), load_schema(), get_counts()
├── 7 Category Functions:
│   ├── measure_structural()      — エッジ密度, 平均次数, 連結性, 孤立率
│   ├── measure_completeness()    — プロパティ充填率(スキーマYAML動的生成), リレーション型カバレッジ
│   ├── measure_consistency()     — 型一貫性, 重複率, 制約違反
│   ├── measure_accuracy()        — v1はスタブ（LLM-as-Judge未実装）
│   ├── measure_timeliness()      — 鮮度, 更新頻度, 時間カバレッジ
│   ├── measure_finance_specific() — セクターカバレッジ, メトリクス/社, E-E関係密度
│   └── measure_discoverability() — パス多様性(サンプリング), ブリッジ率, 平均パス長
├── FinReflectKG CheckRules (4関数):
│   ├── check_subject_reference() — Entity.nameに代名詞が含まれないか
│   ├── check_entity_length()     — Entity.name <= 5語
│   ├── check_schema_compliance() — entity_typeが許可リスト内か
│   └── check_relationship_compliance() — リレーション型がスキーマ定義内か
├── Entropy: compute_shannon_entropy(), compute_semantic_diversity()
├── Output: render_console(Rich), save_json(), save_neo4j(), generate_markdown()
└── CLI: argparse + main()
```

## CLI仕様

```bash
uv run python scripts/kg_quality_metrics.py                        # 全カテゴリ計測+コンソール出力
uv run python scripts/kg_quality_metrics.py --category structural  # 単一カテゴリ
uv run python scripts/kg_quality_metrics.py --save-snapshot        # JSON保存 + Neo4j QualitySnapshotノード
uv run python scripts/kg_quality_metrics.py --report               # Markdownレポート出力
uv run python scripts/kg_quality_metrics.py --compare 2026-03-19   # 前回スナップショットとの差分
```

## 閾値定義（Green/Yellow/Red）

| 指標 | Green | Yellow | Red | 方向 |
|------|-------|--------|-----|------|
| edge_density | >= 0.0001 | >= 0.00005 | < 0.00005 | 高い方が良い |
| average_degree | >= 5.0 | >= 2.0 | < 2.0 | 高い方が良い |
| connectivity | >= 0.90 | >= 0.70 | < 0.70 | 高い方が良い |
| orphan_rate | <= 0.05 | <= 0.15 | > 0.15 | 低い方が良い |
| schema_fill_rate | >= 0.80 | >= 0.60 | < 0.60 | 高い方が良い |
| type_consistency | >= 0.98 | >= 0.90 | < 0.90 | 高い方が良い |
| duplication_rate | <= 0.01 | <= 0.05 | > 0.05 | 低い方が良い |
| freshness_days | <= 7 | <= 30 | > 30 | 低い方が良い |
| entity_entity_ratio | >= 3.0 | >= 1.0 | < 1.0 | 高い方が良い |
| path_diversity | >= 0.80 | >= 0.50 | < 0.50 | 高い方が良い |
| avg_path_length | <= 3.0 | <= 5.0 | > 5.0 | 低い方が良い |
| check_rule_pass_rate | >= 0.95 | >= 0.85 | < 0.85 | 高い方が良い |
| normalized_entropy | >= 0.70 | >= 0.40 | < 0.40 | 高い方が良い |

## Neo4j QualitySnapshotノード

```cypher
MERGE (qs:QualitySnapshot {snapshot_id: $snapshot_id})
SET qs.snapshot_date = datetime(),
    qs.node_count = $node_count,
    qs.relationship_count = $rel_count,
    qs.score_structural = $s1,
    qs.score_completeness = $s2,
    -- (各カテゴリスコア)
    qs.overall_score = $overall,
    qs.overall_rating = $rating,
    -- (主要メトリクスをフラット化)
    qs.entity_entity_rels = $ee_rels,
    qs.avg_path_length = $avg_path,
    qs.created_at = datetime()
```

## 実装順序

| Step | 内容 | 見積 |
|------|------|------|
| 1 | CLI + Neo4j接続 + スキーマ読込 + データクラス | 基盤 |
| 2 | measure_structural() | 最も単純なCypherクエリ群 |
| 3 | measure_completeness() | スキーマYAMLから動的クエリ生成 |
| 4 | measure_consistency() | 型チェック + 重複検出 |
| 5 | measure_timeliness() + measure_finance_specific() | 日付集計 + ドメイン指標 |
| 6 | measure_discoverability() | サンプリングベースのパス計算 |
| 7 | CheckRules(4関数) + Entropy | バリデーションルール |
| 8 | render_console(Rich) + save_json() | 出力フォーマット |
| 9 | save_neo4j() + generate_markdown() + compare | 永続化・比較機能 |

## 設計上の注意点

- **Memory除外**: 全クエリで `WHERE NOT 'Memory' IN labels(n)` を付与
- **Neo4j CE制約**: GDSなし。連結成分はBFS近似、betweenness centralityはラベル多様性ヒューリスティック
- **パフォーマンス**: 各カテゴリ5秒以内。Discoverabilityのパスサンプリングは200ペア上限
- **ポート**: デフォルトは `bolt://localhost:7688`（research-neo4j）
- **Sectorノード**: スキーマYAMLに未定義だがIN_SECTOR/Sector は計測対象に含める

## 検証方法

```bash
# 1. スクリプト実行
uv run python scripts/kg_quality_metrics.py

# 2. JSON出力確認
cat data/processed/kg_quality/snapshot_2026-03-19.json | python -m json.tool

# 3. Neo4j QualitySnapshotノード確認
# MCP: mcp__neo4j-research__research-read_neo4j_cypher
# MATCH (qs:QualitySnapshot) RETURN qs

# 4. 品質チェック
make lint && make typecheck

# 5. 比較機能
uv run python scripts/kg_quality_metrics.py --save-snapshot
# (データ変更後)
uv run python scripts/kg_quality_metrics.py --compare 2026-03-19
```
