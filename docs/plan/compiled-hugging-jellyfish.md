# KG品質計測 運用レイヤー実装プラン

## Context

KG品質計測の基盤（`scripts/kg_quality_metrics.py` 2,378行、テスト1,717行、7カテゴリ中6実装）は整っているが、**運用面が未整備**で品質改善のPDCAが回らない状態。具体的には：
- 手動実行のみで時系列トラッキング不可
- 品質低下時のアラートなし
- accuracy が stub で Overall を常に7.6pt押し下げ
- entity_id NULL 136件・レガシーリレーション110件が consistency/compliance を悪化

本プランで4つの Phase を実装し、KG品質の継続的改善を可能にする。

## 推奨実行順序

```
D (データ修正) → A (定期実行) → C (accuracy実装) → B (アラート)
```

理由：D でベースライン改善 → A でスナップショット蓄積開始 → C で stub 解消 → B で安定計測後にアラート有効化

---

## Phase D: データ品質修正（独立、最初に実行）

### 目的
entity_id NULL 136件の補完 + レガシーリレーション3種のリネームで consistency/compliance スコアを改善。

### 変更ファイル

| ファイル | 種別 | 内容 |
|---------|------|------|
| `scripts/fix_entity_id_null.py` | 新規 | entity_id NULL を UUID5 で補完 |
| `scripts/fix_legacy_relationships.py` | 新規 | RELATED_TO→RELATES_TO 等リネーム |
| `tests/scripts/test_fix_entity_id_null.py` | 新規 | |
| `tests/scripts/test_fix_legacy_relationships.py` | 新規 | |

### 実装ステップ

**D-1: `fix_entity_id_null.py`**
- `find_null_entity_ids(session)`: `WHERE n.entity_id IS NULL` で検索
- `fix_entity_ids(session, entities, dry_run=True)`: `id_generator.generate_entity_id(name, entity_type)` で UUID5 生成、`entity_key = f"{name}::{entity_type}"` も同時設定
- CLI: `--dry-run`（デフォルト）/ `--execute`（明示的承認）
- `entity_type` が NULL の場合は `"unknown"` にフォールバック
- neo4j-write-rules.md の修復作業例外に該当

**D-2: `fix_legacy_relationships.py`**
- `LEGACY_MAPPING = {"RELATED_TO": "RELATES_TO", "HAS_FACT": "STATES_FACT", "TAGGED_WITH": "TAGGED"}`
- Neo4j はリレーションタイプのリネーム不可 → `CREATE (a)-[r2:NEW]->(b) SET r2 = properties(r) DELETE r` パターン
- バッチサイズ100件ずつ処理（トランザクションタイムアウト防止）
- CLI: `--dry-run`（デフォルト）/ `--execute`

### 再利用するコード
- `src/pdf_pipeline/services/id_generator.py:273` — `generate_entity_id(name, entity_type)` 関数
- `scripts/neo4j_utils.py` — `create_driver()` DB接続

### 検証
```bash
# dry-run で件数確認
uv run python scripts/fix_entity_id_null.py --dry-run
uv run python scripts/fix_legacy_relationships.py --dry-run

# 実行後、品質スコア再計測
uv run python scripts/kg_quality_metrics.py --category consistency
# → entity_id violation_count が 0、relationship_compliance が 100% になること
```

---

## Phase A: 定期実行 + スナップショット蓄積

### 目的
週次自動計測でスナップショットを蓄積し、品質トレンドを追跡可能にする。

### 変更ファイル

| ファイル | 種別 | 内容 |
|---------|------|------|
| `Makefile` | 修正 | `kg-quality` ターゲット追加 |
| `scripts/kg_quality_metrics.py` | 修正 | `--exit-code` / `--min-score` フラグ追加 |
| `.github/workflows/ci.yml` | 修正 | `kg-quality` job 追加（dry-run） |
| `scripts/kg_quality_weekly.sh` | 新規 | ローカル週次実行ラッパー |
| `tests/scripts/test_kg_quality_metrics.py` | 修正 | `--exit-code` テスト追加 |

### 実装ステップ

**A-1: Makefile ターゲット**
```makefile
kg-quality:
	uv run python scripts/kg_quality_metrics.py \
		--save-snapshot \
		--compare latest \
		--report data/processed/kg_quality/report_$$(date +%Y%m%d).md
```

**A-2: `--exit-code` フラグ（CI用）**
- `parse_args()` に `--exit-code`（store_true）と `--min-score`（float, default 30.0）追加
- `main()` で `snapshot.overall_score < args.min_score` なら `sys.exit(1)`

**A-3: `--compare latest` のバグ修正**
- 現在 `_find_latest_snapshot()` は同日スナップショットも返す → `--save-snapshot` 直後に `--compare latest` すると自分自身と比較してしまう
- 修正: `_find_latest_snapshot()` に `exclude_date` パラメータ追加、同日のスナップショットを除外

**A-4: GitHub Actions（dry-run smoke test）**
- CI は GitHub-hosted runner で Neo4j に接続不可 → `--dry-run` でスキーマ検証のみ
- 実際のDB計測はローカル cron or 手動 `make kg-quality`

**A-5: ローカル週次ラッパー `kg_quality_weekly.sh`**
```bash
#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
make kg-quality 2>&1 | tee data/processed/kg_quality/run_$(date +%Y%m%d).log
```

### 検証
```bash
make kg-quality
# → snapshot_YYYYMMDD.json と report_YYYYMMDD.md が生成されること
# → --compare latest で前回との差分が表示されること

uv run python scripts/kg_quality_metrics.py --exit-code --min-score 50 --dry-run
# → dry-run でも exit code テスト可能
```

---

## Phase C: accuracy 実装（LLM-as-Judge）

### 目的
accuracy カテゴリの stub を実装に置き換え、Overall スコアの精度を向上。

### 変更ファイル

| ファイル | 種別 | 内容 |
|---------|------|------|
| `scripts/kg_accuracy_judge.py` | 新規 | LLM-as-Judge 評価モジュール |
| `scripts/kg_quality_metrics.py` | 修正 | `measure_accuracy()` 差し替え、CLI引数追加 |
| `data/config/kg_accuracy_config.yaml` | 新規 | サンプルサイズ・キャッシュ設定 |
| `tests/scripts/test_kg_accuracy_judge.py` | 新規 | |

### 設計（experience-db-critique パターン参考）

**評価3軸:**
1. **Factual Correctness** (40%): Fact/Claim の事実正確性
2. **Source Grounding** (30%): Source ノードとの整合性・URL有効性
3. **Temporal Validity** (30%): 情報の鮮度・時間的妥当性

**コスト制御:**
- サンプルサイズ: デフォルト20件（`--accuracy-sample-size`）
- モデル: `claude-sonnet-4-20250514`（コスト効率）
- キャッシュ: `data/processed/kg_quality/accuracy_cache.json`（SHA-256キー、30日有効）
- スキップ: `--skip-accuracy` フラグ
- 決定論的サンプリング: `random.seed(date_str)` で同日同サンプル

**`kg_accuracy_judge.py` の主要関数:**
```python
sample_facts(session, sample_size=20) -> list[dict]  # Neo4j からサンプル抽出
evaluate_single(fact, client) -> AccuracyEvaluation    # 1件評価
evaluate_batch(facts, client, cache) -> list[AccuracyEvaluation]  # バッチ評価+キャッシュ
```

### 実装ステップ

**C-1: `kg_accuracy_judge.py` 作成**
- `AccuracyEvaluation` dataclass（fact_id, 3軸スコア, overall, reasoning）
- `sample_facts()`: Fact/Claim + Source コンテキストを JOIN で取得
- `evaluate_single()`: Anthropic API 呼び出し、構造化JSON応答パース
- `evaluate_batch()`: キャッシュチェック → 未評価のみ API 呼び出し → キャッシュ保存

**C-2: `measure_accuracy()` 差し替え**
- `skip=True` の場合は既存 stub を返す（後方互換）
- `skip=False` の場合は `kg_accuracy_judge` を呼び出し
- MetricValue を3つ（Factual/Grounding/Temporal）返すように変更

**C-3: CLI 引数追加**
- `--skip-accuracy`（store_true）
- `--accuracy-sample-size`（int, default 20）

### 再利用するコード
- `anthropic` パッケージ（pyproject.toml に既存）
- experience-db-critique の加重スコアリングパターン

### 検証
```bash
# skip モードで既存動作確認
uv run python scripts/kg_quality_metrics.py --skip-accuracy

# LLM評価実行（ANTHROPIC_API_KEY 必要）
uv run python scripts/kg_quality_metrics.py --accuracy-sample-size 5

# テスト（API モック）
uv run pytest tests/scripts/test_kg_accuracy_judge.py -v
```

---

## Phase B: アラート・通知

### 目的
品質低下時に GitHub Issue を自動作成し、見逃しを防止。

### 変更ファイル

| ファイル | 種別 | 内容 |
|---------|------|------|
| `scripts/kg_quality_alert.py` | 新規 | アラート評価 + Issue 作成 |
| `scripts/kg_quality_metrics.py` | 修正 | `--alert` フラグ追加 |
| `Makefile` | 修正 | `kg-quality` に `--alert` 追加 |
| `tests/scripts/test_kg_quality_alert.py` | 新規 | |

### アラート条件

| 条件 | severity | 閾値 |
|------|----------|------|
| Overall score 低下 | critical | 前回比 -10pt 以上 |
| Overall score 低下 | warning | 前回比 -5pt 以上 |
| CheckRule pass_rate | warning | 95% 未満 |

### 実装ステップ

**B-1: `kg_quality_alert.py` 作成**
- `AlertCondition` dataclass（name, severity, message, current_value, threshold）
- `evaluate_alerts(current, previous, check_rules)` → `list[AlertCondition]`
- `create_github_issue(alerts, snapshot)` → `gh issue create --repo $(git remote get-url origin | sed ...) --label kg-quality-alert`
- 重複防止: `gh issue list --label kg-quality-alert --state open` で既存チェック

**B-2: `--alert` フラグ統合**
- `main()` に `--alert` 追加
- 前回スナップショット読み込み → `evaluate_alerts()` → Issue 作成

**B-3: Issue テンプレート**
```
タイトル: [KG品質] {severity}: {summary}
ラベル: kg-quality-alert
本文: スコア変化テーブル + CheckRules違反 + 推奨アクション
```

### 検証
```bash
# アラート評価（Issue 作成なし）
uv run python scripts/kg_quality_alert.py --dry-run

# 全体フロー
make kg-quality  # --alert 含む
# → スコア低下時に GitHub Issue が作成されること

# テスト
uv run pytest tests/scripts/test_kg_quality_alert.py -v
```

---

## 全体の検証計画

```bash
# 1. Phase D: データ修正
uv run python scripts/fix_entity_id_null.py --execute
uv run python scripts/fix_legacy_relationships.py --execute

# 2. Phase A: ベースライン計測
make kg-quality
# → snapshot 保存 + レポート生成 + (前回比較)

# 3. Phase C: accuracy 計測
uv run python scripts/kg_quality_metrics.py --save-snapshot --accuracy-sample-size 10

# 4. Phase B: アラートテスト
uv run python scripts/kg_quality_metrics.py --save-snapshot --compare latest --alert

# 5. テスト全体
uv run pytest tests/scripts/test_kg_quality_metrics.py tests/scripts/test_kg_quality_alert.py tests/scripts/test_kg_accuracy_judge.py tests/scripts/test_fix_entity_id_null.py tests/scripts/test_fix_legacy_relationships.py -v
```

## 成果物サマリー

| Phase | 新規ファイル | 修正ファイル | テスト |
|-------|------------|------------|-------|
| D | 2 scripts | — | 2 test files |
| A | 1 script | 3 files (Makefile, kg_quality_metrics.py, ci.yml) | 既存テスト拡張 |
| C | 1 module + 1 config | 1 file (kg_quality_metrics.py) | 1 test file |
| B | 1 module | 2 files (kg_quality_metrics.py, Makefile) | 1 test file |
| **計** | **5 新規** | **3 修正** | **4 テストファイル** |
