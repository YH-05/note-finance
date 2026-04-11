# KG投入結果レポート

**生成日**: 2026-04-11
**セッションID**: article-research-jpmorgan-q1-2026-earnings-preview-20260411-1200

---

## 投入ステータス

| ステップ | 結果 | 詳細 |
|---------|------|------|
| ① emit_research_queue.py | ✅ 成功 | graph-queue JSON生成完了 |
| ② entity_linker.py | ✅ 成功 | resolved JSON生成完了 |
| ③ neo4j_loader.py | ⚠️ スキップ | bolt://localhost:7688 応答なし |

## 生成ファイル

| ファイル | パス |
|---------|------|
| 入力JSON | `.tmp/research-input/article-research-jpmorgan-q1-2026-earnings-preview-20260411-1200.json` |
| graph-queue JSON | `.tmp/graph-queue/web-research/gq-20260411000823-3321a96f.json` |
| resolved JSON | `.tmp/graph-queue/web-research/gq-20260411000823-3321a96f.resolved.json` |

## 投入予定データ（Neo4j起動後に手動投入可能）

| ノード種別 | 件数 |
|----------|------|
| Source | 11件 |
| Fact | 7件 |
| Entity (Company/Person/Organization) | 7件 |
| Topic | 6件 |

## 手動投入コマンド

```bash
# Neo4j起動後に実行
uv run python src/data_pipeline/neo4j_loader.py \
  --instance research \
  --input .tmp/graph-queue/web-research/gq-20260411000823-3321a96f.resolved.json
```

## ギャップ解消状況（投入予定データ）

| ギャップ | 解消データ |
|---------|-----------|
| stale_data | 2026-04-06〜09の最新ソース11件 |
| no_coverage | Q1 2026決算プレビューFact7件 |
| missing_bear_case | Dimon警告・クレジット正常化Fact追加 |
| open_questions | NII/IBフィー/カードCO/マクロ全解消 |
