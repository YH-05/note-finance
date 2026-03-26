---
name: note-scrape
description: >
  note.com クリエイターの記事をスクレイピングし、RawStore に保存後、creator-neo4j に投入するパイプラインスキル。
  「note.comをスクレイピング」「note.com記事を取得」「note.comからcreator-neo4jに投入」
  「note.com {username} の記事を集めて」「note.comクリエイターを追加」「note RSSモニター」
  と言われたら必ずこのスキルを使うこと。
  Use PROACTIVELY when the user mentions note.com scraping, creator article collection,
  or note.com → Neo4j ingestion.
---

# note-com-pipeline スキル

note.com クリエイターの公開記事を Playwright でスクレイピングし、RawStore に中間保存した後、
creator-neo4j（または research-neo4j）に投入する一連のパイプラインを実行する。

## 処理フロー

```
Phase 1: クリエイター指定 + スクレイピング
    |  ユーザーから username を取得（または引数から）
    |  Playwright で記事一覧取得 → 有料記事スキップ → 無料記事の本文取得
    |  RawStore に保存
    |
Phase 2: 投入先選択 + Neo4j 投入
    |  --target creator（デフォルト）or research を選択
    |  RawStore → LLM 抽出 → emit → Neo4j 投入
    |
Phase 3: RSSモニター登録（オプション）
    |  スクレイピング完了後、RSSモニター対象に追加するか質問
    |
Phase 4: 結果レポート
```

## モード

### モード1: 一括スクレイピング + 投入（デフォルト）

```bash
/note-com-pipeline {username}
/note-com-pipeline {username} --max-articles 30
/note-com-pipeline {username} --target research
/note-com-pipeline {username} --scrape-only  # RawStore保存のみ、Neo4j投入なし
```

### モード2: RSSモニタリング

```bash
/note-com-pipeline --monitor
```

### モード3: クリエイター管理

```bash
/note-com-pipeline --list
/note-com-pipeline --add {username}
/note-com-pipeline --remove {username}
```

### モード4: RawStore からの再投入

```bash
/note-com-pipeline --ingest {username} --target creator
/note-com-pipeline --ingest {username} --target research --date 2026-03-25
```

## Phase 1: スクレイピング

### 1.1 引数の解析

引数から以下を取得:
- `username`: note.com ユーザー名（必須、モード1の場合）
- `--max-articles`: 最大記事数（デフォルト: 無制限）
- `--target`: 投入先 `creator`（デフォルト）or `research`
- `--scrape-only`: RawStore 保存のみ
- `--genre`: ジャンル（デフォルト: `career`）
- `--dry-run`: Neo4j 投入をスキップ

引数がない場合は AskUserQuestion で username を質問する。

### 1.2 スクレイピング実行

```bash
uv run python -m data_pipeline note-com scrape {username} --max-articles {max_articles}
```

実行結果から以下を確認:
- 取得した記事数
- 有料スキップ数
- 重複スキップ数
- 保存件数

### 1.3 結果確認

スクレイピング結果をユーザーに報告:
```
note.com/{username} のスクレイピング完了
  記事URL: {url_count} 件
  保存: {saved} 件
  有料スキップ: {skipped_paid} 件
  重複スキップ: {skipped_dup} 件
```

## Phase 2: Neo4j 投入

`--scrape-only` でなければ投入を実行。

```bash
uv run python -m data_pipeline ingest --source note-com-{username} --target {target} --genre {genre}
```

dry-run の場合:
```bash
uv run python -m data_pipeline ingest --source note-com-{username} --target {target} --dry-run
```

投入結果を報告:
```
RawStore → {target}-neo4j 投入完了
  読み込み: {items} 件
  Facts: {facts}, Tips: {tips}, Stories: {stories}
  Neo4j: {nodes} ノード, {relations} リレーション
```

## Phase 3: RSSモニター登録

スクレイピングで記事が保存された場合、AskUserQuestion で質問:
「{username} をRSSモニター対象に追加しますか？新着記事を自動検知できます。」

「はい」の場合:
```bash
uv run python -m data_pipeline note-com add {username} --genre {genre}
```

## Phase 4: 結果レポート

全フェーズの結果をまとめて報告。

## その他のモード

### --monitor: RSSモニタリング

```bash
uv run python -m data_pipeline note-com monitor
```

新着記事が見つかった場合、投入するかどうかを AskUserQuestion で質問。

### --list / --add / --remove: クリエイター管理

```bash
uv run python -m data_pipeline note-com list
uv run python -m data_pipeline note-com add {username} --genre {genre}
uv run python -m data_pipeline note-com remove {username}
```

### --ingest: RawStore からの再投入

過去にスクレイピング済みのデータを別ターゲットに投入:

```bash
uv run python -m data_pipeline ingest --source note-com-{username} --target {target} --genre {genre}
```

## 前提条件

- `playwright install chromium` 済みであること
- creator-neo4j (bolt://localhost:7689) が起動していること（`--target creator` の場合）
- research-neo4j (bolt://localhost:7688) が起動していること（`--target research` の場合）
- `claude-agent-sdk` がインストール済みであること（LLM 抽出に必要）

## 関連ファイル

| ファイル | 説明 |
|---------|------|
| `src/data_pipeline/collectors/note_com_browser.py` | Playwright async ラッパー |
| `src/data_pipeline/collectors/note_com.py` | NoteComCollector |
| `src/data_pipeline/collectors/note_com_rss.py` | NoteComRssMonitor |
| `src/data_pipeline/pipeline.py` | `run_ingest_from_rawstore()` |
| `src/data_pipeline/__main__.py` | CLI エントリポイント |
| `data/config/note-com-creators.json` | クリエイター管理 config |

## MUST

- スクレイピング前に username が有効か確認（空文字チェック）
- 有料記事は絶対にスクレイピングしない（Playwright が自動スキップ）
- Neo4j 投入前に dry-run で件数確認を提案する
- robots.txt 準拠（note.com の記事ページ・クリエイターページはアクセス許可）

## NEVER

- 非公式 API (`/api/v2/`, `/api/v3/`) を使用する
- 有料記事・限定公開記事の本文を取得しようとする
- headless=False で実行する（ユーザーが明示的に指定しない限り）
