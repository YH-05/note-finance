# 実装メモ: scraped→Neo4j パイプライン

**日付**: 2026-03-29
**参加**: ユーザー + AI

## 背景・コンテキスト

NASに蓄積されたRSSスクレイピングJSONを、手動操作なしにNeo4jナレッジグラフへ自動投入する仕組みが必要だった。
これまで`scrape_finance_news.py`がスクレイプとNeo4j投入を兼務していたが、責務過多でメンテ困難だった。

## 実装内容

### 4段パイプライン

```
Stage 1: scrape_finance_news.py  → NAS/{source}/{date}/news_*.json
Stage 2: dedup_scraped.py        → .tmp/deduped-all-{ts}.json  （重複排除）
Stage 3: emit_research_queue.py  → .tmp/graph-queue/finance-news-workflow/*.json
Stage 4: ingest_graph_queue.py   → research-neo4j (bolt://localhost:7688)
```

### オーケストレーター

`scripts/pipeline_scraped_to_neo4j.py` が Stage 2→3→4 をサブプロセスで順次実行。
- Stage 2出力パスはstdout最終行から取得
- Stage 3出力パスは`Queue file: {path}`行から取得
- 新規記事0件の場合はStage 3/4をスキップして正常終了

### launchd スケジュール

| ジョブ | 実行時刻 | plist |
|--------|---------|-------|
| scrape (全11ソース) | 0/6/12/18h | 各ソース個別 |
| pipeline (dedup+emit+ingest) | 毎日 3:00 AM | `com.note-finance.pipeline-scraped-to-neo4j.plist` |

## 決定事項

1. **パイプライン分割**: 4段ステージに責務を分離（各ステージ独立テスト・再実行可能）
2. **launchdスケジュール**: scrape(4回/日) と dedup+ingest(1回/日) を時刻で分離
3. **scrape簡素化**: `scrape_finance_news.py` からNeo4j投入ロジックを完全削除、スクレイプ専任に

## 修正したバグ

### neo4j_loader.py: classification_rels ラベル解決バグ

**問題**: FROM_DOMAIN / RATED_AS / INGESTED_VIA リレーションが一切作成されていなかった。

**原因**: `classification_rels`処理でデフォルト値 `from_label="Entity"`, `to_label="Classification"` が使われ、
MATCHが全件失敗していた。

**修正**: `classification_nodes`データから `cn_keymap`（key_value → (label, key_prop)）を事前構築し、
`source_id_set`（Source IDセット）と組み合わせて正しいラベルを動的解決するよう変更。

```python
# 修正後の主要ロジック
cn_keymap: dict[str, tuple[str, str]] = {}
for cnode in queue_data.get("classification_nodes", []):
    cn_label = cnode.get("label", "")
    cn_key_prop = cnode.get("key_property", f"{cn_label.lower()}_id")
    cn_key_val = cnode.get("key_value", "")
    if cn_key_val and cn_label:
        cn_keymap[cn_key_val] = (cn_label, cn_key_prop)

source_id_set = {s.get("source_id") for s in queue_data.get("sources", [])}

for crel in queue_data.get("classification_rels", []):
    from_id = crel.get("from_id")
    to_id = crel.get("to_id")
    if from_id in source_id_set:
        from_label, from_key = "Source", "source_id"
    else:
        from_label = crel.get("from_label", "Entity")
        from_key = f"{from_label.lower()}_id"
    if to_id in cn_keymap:
        to_label, to_key = cn_keymap[to_id]
    else:
        to_label = crel.get("to_label", "Classification")
        to_key = f"{to_label.lower()}_id"
```

### dedup_scraped.py: dry-run誤メッセージ

dry-run時に「No new articles to ingest.」と表示していたを `elif args.dry_run` ブランチで修正。

## 初回投入結果（2026-03-29）

| 項目 | 件数 |
|------|------|
| 処理ソース数 | 11 |
| 新規記事 | 1127件 |
| Source ノード | 1127 |
| Claim ノード | 752 |
| 分類ノード（Domain/TrustLevel/Pipeline） | 51 |
| リレーション合計 | 3381 |

## 廃棄したもの

- NAS `/Volumes/personal_folder/graph-queue/finance-news-workflow/*.json` (88ファイル)
  → `trash/nas-graph-queue-20260329/` に移動
- `scrape_finance_news.py` の Neo4j 投入コード（`_neo4j_article()`, `_ingest_source_to_neo4j()`等）

## Neo4j ノード参照

| ノード | ID |
|--------|-----|
| Discussion (計画) | `disc-2026-03-29-scraped-to-neo4j-pipeline` |
| Discussion (実装) | `disc-2026-03-29-pipeline-implementation` |
| Decision (アーキ) | `dec-2026-03-29-pipeline-arch` |
| Decision (スケジュール) | `dec-2026-03-29-launchd-schedule` |
| Decision (scrape簡素化) | `dec-2026-03-29-scrape-simplify` |
