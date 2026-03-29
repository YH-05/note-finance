# 議論メモ: dedup_scraped.py 詳細設計

**日付**: 2026-03-29
**参加**: ユーザー + AI

## 背景・コンテキスト

scraped JSON → Neo4j 投入パイプライン再設計（`disc-2026-03-29-scraped-to-neo4j-pipeline`）で
Stage 2 として `dedup_scraped.py` を実装することが決定済み。
本セッションでその詳細設計を決定した。

## 決定事項

### 1. 処理単位: ソースごとに処理 → 1ファイルにまとめて出力（案C）

- 各ソースの `scraped/{source}/` を個別に処理
- 全ソースの新規記事を集めて `.tmp/deduped-all-{ts}.json` を1ファイル出力
- `emit_research_queue.py` は1回だけ呼ぶ

### 2. レジストリ形式: JSONL 追記形式

```
{"url": "https://...", "ingested_at": "2026-03-29T07:00:00Z", "source": "cnbc"}
{"url": "https://...", "ingested_at": "2026-03-29T07:00:00Z", "source": "jetro"}
```

- パス: `/Volumes/personal_folder/scraped/_registry/processed_urls.jsonl`
- 書き込みは追記のみ（高速）
- 読み込み時は全行スキャン

### 3. dedup 範囲: 全ソース横断

レジストリ照合により、異なるソース間の同一URLも自動排除される。

### 4. 完全重複ファイルも `processed/` に移動

新規記事0件のファイルも `processed/` に移動する。次回スキャン対象から除外。

### 5. エラー時: ロールバックなし

処理済みのソースは `processed/` 移動・レジストリ登録を維持したまま終了。
次回実行時に残ソースから再開。

## アルゴリズム

```python
def run():
    all_new_articles = []

    for source in SOURCES:  # 全11ソース
        # 1. 未処理ファイルを取得（processed/ は除外）
        unprocessed = find_unprocessed_files(f"scraped/{source}/")
        if not unprocessed:
            continue

        # 2. 全ファイルから記事を読み込み
        raw_articles = load_articles(unprocessed)

        # 3. ソース内 URL 重複排除（最古エントリ採用）
        deduped = dedup_by_url(raw_articles)

        # 4. レジストリで既投入 URL を除外
        new_articles = filter_by_registry(deduped)

        # 5. 元ファイルを processed/ に移動（新規0件でも移動）
        move_to_processed(unprocessed, source)

        # 6. レジストリに新規 URL を追記
        append_to_registry(new_articles)

        all_new_articles.extend(new_articles)

    if not all_new_articles:
        return  # 新規なし、Stage 3/4 スキップ

    # 7. .tmp/deduped-all-{ts}.json を出力（finance-news-workflow 形式）
    output = {
        "articles": [to_finance_news_format(a) for a in all_new_articles],
        "session_id": f"dedup-{timestamp}",
        "batch_label": "rss-scrape",
    }
    write_tmp(output)
```

## フィールドマッピング（scraped → finance-news-workflow）

| scraped JSON | finance-news-workflow |
|---|---|
| `url` | `url` |
| `title` | `title` |
| `summary` | `summary` |
| `source` | `feed_source` |
| `published` | `published` |

## NAS ディレクトリ構造

```
/Volumes/personal_folder/scraped/
├── cnbc/
│   ├── 2026-03-28/
│   │   └── news_*.json         ← 未処理
│   └── processed/
│       └── 2026-03-27/
│           └── news_*.json     ← 処理済み
├── ...（全11ソース）
└── _registry/
    └── processed_urls.jsonl    ← 全ソース横断レジストリ
```

## 次回の議論トピック

- `pipeline_scraped_to_neo4j.py`（Stage 2→3→4 オーケストレーター）の設計

## Neo4j ノード

- Discussion: `disc-2026-03-29-dedup-scraped-design`
- Decision: `dec-2026-03-29-dedup-processing-unit`, `dec-2026-03-29-dedup-registry-format`, `dec-2026-03-29-dedup-cross-source`, `dec-2026-03-29-dedup-full-dup-files`, `dec-2026-03-29-dedup-error-handling`
