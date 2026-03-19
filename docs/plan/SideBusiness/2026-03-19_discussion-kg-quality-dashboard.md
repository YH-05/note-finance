# 議論メモ: KG品質ダッシュボード定量評価の実行と改善

**日付**: 2026-03-19
**参加**: ユーザー + AI

## 背景・コンテキスト

KG品質ダッシュボード（`kg_quality_metrics.py`）は Phase 4-A/4-B（Issues #199-#204）で実装済みだったが、実際の計測は未実施だった。今回初めて実行し、スナップショットを取得・保存した。

## 初回計測結果（Before: スキーマ更新前）

| カテゴリ | スコア | レーティング |
|---------|--------|-------------|
| structural | 75.0 | B |
| completeness | 50.0 | C |
| **consistency** | **16.7** | **D** |
| accuracy | 0.0 | D (stub) |
| timeliness | 66.7 | B |
| finance_specific | 66.7 | B |
| discoverability | 66.7 | B |
| **Overall** | **48.8** | **C** |

### ボトルネック分析

- consistency が16.7/100で最大の足引き
  - entity_type許可リスト外: 94件（article_proposal等）
  - relationship_type許可リスト外: 21件（COMPETES_WITH等）
  - entity_id NULL: 136件

## 実施した改善: スキーマ v2.3 → v2.4

DB実態とスキーマ定義の乖離を解消。

### entity_type拡張（+14種）

technology, central_bank, broker, etf, bond, currency_pair, exchange, government, region, subsidiary, product, macro, fintech, theme

### relationship定義追加（+16種）

SHARES_TOPIC, CO_MENTIONED_WITH, MEASURES, IN_SECTOR, COMPETES_WITH, CUSTOMER_OF, SUBSIDIARY_OF, PARTNERS_WITH, INVESTED_IN, GOVERNS, OPERATES_IN, INFLUENCES, LED_BY, SPUN_OFF_FROM, MENTIONS, SOURCED_FROM, BELONGS_TO, FOR_METRIC

### バグ修正: timeliness計測

`Source.fetched_at` がDATETIME/STRING混在のため `duration.between()` でエラー。Python側で `collect(toString())` → ISO 8601パースに変更。

## 改善後の計測結果

| カテゴリ | Before | After | 変化 |
|---------|--------|-------|------|
| structural | 75.0 | 75.0 | — |
| completeness | 50.0 | 50.0 | — |
| **consistency** | **16.7** | **50.0** | **+33.3** |
| accuracy | 0.0 | 0.0 | — (stub) |
| timeliness | 66.7 | 66.7 | — |
| finance_specific | 66.7 | 66.7 | — |
| discoverability | 66.7 | 66.7 | — |
| **Overall** | **48.8** | **53.6** | **+4.8** |

### CheckRules改善

| ルール | Before | After |
|-------|--------|-------|
| schema_compliance | 77.83% (94違反) | 96.70% (14違反) |
| relationship_compliance | 41.67% (21違反) | 91.67% (3違反) |

## 決定事項

1. knowledge-graph-schema.yaml を v2.4 に更新（entity_type +14種、relationship +16種）
2. timeliness計測はPython側フォールバック方式を採用（Neo4j CE制約回避）

## アクションアイテム

- [ ] entity_id NULL 136件を補完 (優先度: 高)
- [ ] レガシーリレーション名リネーム: RELATED_TO→RELATES_TO(72), HAS_FACT→STATES_FACT(35), TAGGED_WITH→TAGGED(3) (優先度: 中)
- [ ] kg_quality_metrics.py の定期実行設定（週次） (優先度: 中)

## 次回の議論トピック

- accuracy (LLM-as-Judge) の実装方針
- entity_id NULL補完のバッチスクリプト設計
- 品質スコア目標値の設定（Rating B = 60以上を目標とすべきか）

## 保存先

- スナップショットJSON: `data/processed/kg_quality/snapshot_20260319.json`
- Neo4j QualitySnapshot: `qs_20260319`
- Markdownレポート: `data/processed/kg_quality/report_20260319_v2.md`
