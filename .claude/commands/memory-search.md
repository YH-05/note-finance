---
description: セッションメモリから過去の会話チャンクを検索
---

# /memory-search - セッションメモリ検索

`memory-cli search` を呼び出して、SQLite に保存済みの会話チャンクを全文検索します。

## 使用例

```bash
# 基本的な検索
/memory-search neo4j スキーマ

# JSON 出力モード
/memory-search --json "TDD 実装"

# 検索モード指定
/memory-search --mode fts "バルクインポート"

# 件数制限
/memory-search --limit 5 "記事作成"
```

## パラメータ

| パラメータ | 必須 | デフォルト | 説明 |
|-----------|------|-----------|------|
| `$ARGUMENTS` | はい | - | 検索クエリ文字列 |
| `--mode` | いいえ | `fts` | 検索モード（`fts` / `vector` / `hybrid`） |
| `--limit` | いいえ | `10` | 最大結果件数 |
| `--json` | いいえ | `false` | JSON 形式で出力 |
| `--db-path` | いいえ | `data/cache/session_memory.db` | SQLite DB パス |

## 実行手順

1. 以下のコマンドを実行して検索する:

```bash
uv run memory-cli search --query "$ARGUMENTS" --limit 10
```

2. 結果をユーザーに表示する（Rich テーブル形式）

3. 結果が 0 件の場合は、クエリのキーワードを分割して再検索を提案する

## 検索モード

| モード | 説明 | 用途 |
|--------|------|------|
| `fts` | FTS5 全文検索 | キーワードベースの高速検索 |
| `vector` | ベクトル類似検索 | 意味的に近いチャンクを発見（要 embedding） |
| `hybrid` | FTS + Vector の RRF 統合 | 最も高精度（要 embedding） |

## 注意事項

- embedding が未生成の場合、`vector` / `hybrid` モードは `fts` にフォールバック
- DB ファイルが存在しない場合はエラーメッセージを表示
- 大量の結果がある場合は `--limit` で絞り込みを推奨
