# 議論メモ: note.comスクレイピングパイプライン実装完了

**日付**: 2026-03-25
**参加**: ユーザー + AI

## 背景・コンテキスト

`disc-2026-03-25-notecom-scraping-pipeline` で設計した統合パイプラインの全コンポーネントを実装。

## 実装サマリー

### 新規作成ファイル

| ファイル | 内容 |
|---------|------|
| `src/data_pipeline/collectors/note_com_browser.py` | Playwright async ラッパー（NoteComBrowser, NoteArticle） |
| `src/data_pipeline/collectors/note_com.py` | NoteComCollector（BaseCollector 継承） |
| `src/data_pipeline/collectors/note_com_rss.py` | NoteComRssMonitor（RSS新着検知 + Playwright本文取得） |
| `data/config/note-com-creators.json` | クリエイター管理config |
| `src/quants/__init__.py` | quants パッケージ |
| `src/quants/utils/__init__.py` | utils サブパッケージ |
| `src/quants/utils/logging_config.py` | structlog ベース get_logger() |

### 変更ファイル

| ファイル | 変更内容 |
|---------|---------|
| `src/data_pipeline/__main__.py` | `note-com` (scrape/monitor/add/list/remove) + `ingest` サブコマンド追加 |
| `src/data_pipeline/pipeline.py` | `run_ingest_from_rawstore()` 追加、collectors に `"note-com"` 追加 |
| `data/config/collection_methods.json` | `"note-com"` メソッド定義追加 |
| `data/config/source_registry.json` | note-com ソースエントリ追加 |
| `src/creator_enrichment/phases/search.py` | RawStore 保存統合（`_save_to_rawstore()`） |
| `pyproject.toml` | hatch packages に `src/quants` 追加 |

## E2E テスト結果

### scrape テスト

| クリエイター | 記事数 | 保存 | 有料スキップ | 重複スキップ |
|---|---|---|---|---|
| yukihata | 2 | 2 | 0 | 0 |
| shupeiman | 5 | 4 | **1** (¥300) | 0 |
| yukihata (2回目) | 2 | 0 | 0 | **2** |

### ingest テスト (yukihata → creator-neo4j)

| ステップ | 結果 |
|---|---|
| RawStore 読み出し | 2件 |
| LLM抽出 (ContentExtractor) | Story 1件（1件はJSONパースエラーでスキップ） |
| emit_creator_queue_v2 | 1 source, 5 concepts, 1 story |
| creator-neo4j 投入 | **7 nodes, 8 relations** |

## 決定事項

1. **Playwright ページ読み込み戦略**: `wait_until="load"` + `wait_for_selector()` の組み合わせ。`domcontentloaded` はSSR前で不可、`networkidle` はタイムアウト
2. **quants パッケージ新設**: note-finance 内に `src/quants/` を作成し structlog ベースの `get_logger()` を提供。scripts/ 内12ファイルの import エラーを解消

## 次回の議論トピック

- RSSモニタリングの cron スケジュール設定
- `ingest --target research` のテスト
- ユニットテスト作成（Wave 4）
- note.com の DOM 変更監視（セレクタ破損検知）

## 参考: CLI コマンド一覧

```bash
uv run python -m data_pipeline note-com scrape {username} [--max-articles 50]
uv run python -m data_pipeline note-com monitor
uv run python -m data_pipeline note-com add {username} [--genre career]
uv run python -m data_pipeline note-com list
uv run python -m data_pipeline note-com remove {username}
uv run python -m data_pipeline ingest --source {source_id} --target creator|research [--dry-run]
```

## スキルコマンド

`/note-scrape` で全パイプラインを実行可能:
```bash
/note-scrape {username}                    # 一括取得 → creator-neo4j
/note-scrape {username} --scrape-only      # RawStore保存のみ
/note-scrape {username} --target research  # research-neo4j に投入
/note-scrape --monitor                     # RSSモニタリング
/note-scrape --list / --add / --remove     # クリエイター管理
```

## 追加決定事項

3. **スキル名**: `note-com-pipeline` → `note-scrape` にリネーム（簡潔さ優先）
4. **quants パッケージ**: `src/quants/` を note-finance 内に新設（structlog `get_logger()` 提供、scripts/ 12ファイルの import エラー解消）
5. **Playwright ページ読み込み**: `wait_until="load"` + `wait_for_selector()` 15秒（domcontentloaded/networkidle は不適）
