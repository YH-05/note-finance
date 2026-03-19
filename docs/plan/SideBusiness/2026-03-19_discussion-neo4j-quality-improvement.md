# 議論メモ: Neo4j グラフDB品質分析・改善

**日付**: 2026-03-19
**参加**: ユーザー + AI

## 背景・コンテキスト

research-neo4j (port 7688) と note-neo4j (port 7687) のグラフDBとしての品質を分析し、発見された問題を P0/P1/P2 の3段階で改善した。さらに、パイプライン側のコードも修正して再発を防止した。

## 品質スコア Before → After

| 観点 | research Before | After | note Before | After |
|---|---|---|---|---|
| スキーマ一貫性 | 4/10 | 7/10 | 6/10 | 8/10 |
| データ完全性 | 3/10 | 5/10 | 7/10 | 8/10 |
| 重複管理 | 4/10 | 8/10 | 8/10 | 8/10 |
| インデックス/制約 | 7/10 | 8/10 | 1/10 | 7/10 |
| リレーション品質 | 5/10 | 8/10 | 8/10 | 8/10 |
| スキーマ衛生 | 6/10 | 9/10 | 9/10 | 9/10 |
| **総合** | **4.8** | **7.5** | **6.5** | **8.0** |

## 実施内容

### P0: 即座対応（完了）

1. **Entity重複マージ** — Indonesia, Federal Reserve, XLSmart の3組をマージ（マルチロールは許容）
2. **entity_type正規化** — 31種→24種、全て lowercase に統一
3. **note-neo4j制約追加** — discussion_id, decision_id, action_id に UNIQUENESS 制約

### P1: 早期対応（完了）

4. **created_at型統一** — STRING(737件) + epoch文字列(36件) + INTEGER(222件) → 全て DATETIME
5. **SHARES_TOPICフィルタ** — shared_topic_count < 3 を削除（11,480→731件、93.6%削減）
6. **entity_key NULL補完** — 52件に `Name::type` 形式を付与

### P2: 中期対応（完了）

7. **source_type正規化** — 25種→12種に統合（分析系→analysis, データ系→data 等）
8. **孤立ノード削除** — Memory(1) + Implementation(1) のレガシーノード削除
9. **幽霊制約削除** — Article/Question/Quote/XPost の空制約4件を除去
10. **Discussion.date型統一** — STRING(5件) → DATE

### パイプライン修正（完了）

| ファイル | 修正 |
|---|---|
| `emit_graph_queue.py` | `_normalize_entity_type()`, `_normalize_source_type()`, `_SOURCE_TYPE_NORMALIZATION` マップ追加 |
| `emit_graph_queue.py:_make_source()` | source_type 自動正規化 |
| `emit_graph_queue.py:2957` | `"original"` → `"report"` |
| `strengthen_entity_connections.py:436` | SHARES_TOPIC 閾値 >= 1 → >= 3 |
| テスト | 292件全パス確認 |

## 数値サマリー

| 指標 | Before | After |
|---|---|---|
| research-neo4j ノード | 4,943 | 4,912 (-31) |
| research-neo4j リレーション | 24,056 | 19,815 (-4,241) |
| SHARES_TOPIC 占有率 | 47.7% | 3.7% |
| entity_type 種類 | 31 | 24 |
| source_type 種類 | 25 | 12 |
| created_at 型混在 | 3型 | DATETIME統一 |
| entity_key NULL | 52件 | 0件 |
| note-neo4j 制約数 | 0 | 3 |

## 決定事項

1. Entity重複マージ時、マルチロール（company/organization/broker等）は重複とみなさない
2. entity_type は全て lowercase で統一
3. SHARES_TOPIC は shared_topic_count >= 3 のみ保持
4. source_type は12種の正規値に統合
5. パイプライン側に正規化ロジックを組み込み再発防止

## アクションアイテム

- [ ] Fact/Claim のNULL率改善（source_url 68.7%, as_of_date 48.7%） — 優先度: 中
- [ ] 孤立Claim 5件（ASEANテレコム関連）の再接続 — 優先度: 低
- [ ] 孤立FiscalPeriod 4件のDataPoint紐付け — 優先度: 低
- [ ] 改善後データでAuraDBバックアップ再実行 — 優先度: 高

## 次回の議論トピック

- Fact/Claim のNULL率改善のためのパイプライン強化方針
- KG品質の自動計測ダッシュボード（kg_quality_metrics.py の活用）
