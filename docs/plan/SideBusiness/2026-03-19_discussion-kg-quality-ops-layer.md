# 議論メモ: KG品質計測 運用レイヤー実装

**日付**: 2026-03-19
**参加**: ユーザー + AI

## 背景・コンテキスト

KG品質計測の基盤（`scripts/kg_quality_metrics.py` 2,378行、テスト1,717行、7カテゴリ中6実装）は整っていたが、運用面が未整備で品質改善のPDCAが回らない状態だった。

具体的な課題:
- 手動実行のみで時系列トラッキング不可
- 品質低下時のアラートなし
- accuracy が stub で Overall を常に7.6pt押し下げ
- entity_id NULL 136件・レガシーリレーション110件が consistency/compliance を悪化

## 実装サマリー

推奨実行順序 **D → A → C → B** で4Phase全て実装完了。**180テスト全パス**。

### Phase D: データ品質修正（独立・最初に実行）

| ファイル | 種別 | 内容 |
|---------|------|------|
| `scripts/fix_entity_id_null.py` | 新規 | entity_id NULL を UUID5 で補完 |
| `scripts/fix_legacy_relationships.py` | 新規 | RELATED_TO→RELATES_TO 等3種リネーム（バッチ100件） |
| `tests/scripts/test_fix_entity_id_null.py` | 新規 | 13テスト |
| `tests/scripts/test_fix_legacy_relationships.py` | 新規 | 14テスト |

### Phase A: 定期実行 + スナップショット蓄積

| ファイル | 種別 | 内容 |
|---------|------|------|
| `Makefile` | 修正 | `kg-quality` ターゲット追加 |
| `scripts/kg_quality_metrics.py` | 修正 | `--exit-code`/`--min-score`/`--skip-accuracy`/`--accuracy-sample-size`/`--alert` フラグ追加 |
| `.github/workflows/ci.yml` | 修正 | `kg-quality` dry-run smoke test job 追加 |
| `scripts/kg_quality_weekly.sh` | 新規 | ローカル週次実行ラッパー |

バグ修正: `_find_latest_snapshot()` に `exclude_date` パラメータ追加（同日比較バグ防止）

### Phase C: accuracy 実装（LLM-as-Judge）

| ファイル | 種別 | 内容 |
|---------|------|------|
| `scripts/kg_accuracy_judge.py` | 新規 | LLM-as-Judge 評価モジュール |
| `data/config/kg_accuracy_config.yaml` | 新規 | サンプルサイズ・キャッシュ設定 |
| `tests/scripts/test_kg_accuracy_judge.py` | 新規 | 10テスト |

設計:
- 3軸評価: Factual Correctness (40%) / Source Grounding (30%) / Temporal Validity (30%)
- コスト制御: サンプル20件、claude-sonnet-4、SHA-256キャッシュ（30日有効）
- 決定論的サンプリング: `random.seed(date_str)` で同日同サンプル

### Phase B: アラート・通知

| ファイル | 種別 | 内容 |
|---------|------|------|
| `scripts/kg_quality_alert.py` | 新規 | アラート評価 + GitHub Issue 自動作成 |
| `tests/scripts/test_kg_quality_alert.py` | 新規 | 8テスト |

アラート条件:
- Overall score -10pt以上低下 → critical
- Overall score -5pt以上低下 → warning
- CheckRule pass_rate 95%未満 → warning

重複防止: `gh issue list --label kg-quality-alert --state open` で既存チェック

## 決定事項

1. 実行順序は D → A → C → B（データ修正でベースライン改善 → スナップショット蓄積 → stub解消 → アラート有効化）
2. accuracy は LLM-as-Judge パターンで実装（experience-db-critique 参考）
3. アラートは GitHub Issue で通知（`kg-quality-alert` ラベル）
4. CI は dry-run のみ（Neo4j 接続不可のため）

## アクションアイテム

- [ ] `fix_entity_id_null.py --execute` で entity_id NULL 補完を実行（優先度: 高）
- [ ] `fix_legacy_relationships.py --execute` でレガシーリレーションリネーム実行（優先度: 高）
- [ ] `make kg-quality` でベースライン計測・スナップショット蓄積開始（優先度: 中）
- [ ] accuracy 評価を実行（`--accuracy-sample-size 10` でテスト後、20件で本番計測）（優先度: 中）

## 成果物

| Phase | 新規ファイル | 修正ファイル | テスト |
|-------|------------|------------|-------|
| D | 2 scripts | — | 2 test files (27テスト) |
| A | 1 script | 3 files | 既存テスト拡張 (8テスト追加) |
| C | 1 module + 1 config | 1 file | 1 test file (10テスト) |
| B | 1 module | 2 files | 1 test file (8テスト) |
| **計** | **5 新規** | **3 修正** | **4 テストファイル, 180テスト全パス** |

## Neo4j 保存先

- Discussion: `disc-2026-03-19-kg-quality-ops-layer`
- Decisions: `dec-2026-03-19-kg-ops-phase-{d,a,c,b}`
- ActionItems: `act-2026-03-19-{001..004}`
