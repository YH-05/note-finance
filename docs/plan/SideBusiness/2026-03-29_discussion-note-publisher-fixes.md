# 議論メモ: note_publisher パッケージのバグ修正・機能改善

**日付**: 2026-03-29
**参加**: ユーザー + AI

## 背景・コンテキスト

`/article-publish` でインドネシア通信セクター記事を note.com に下書き投稿した際、画像が表示されない・マークダウン記法が残るという問題が発生。原因調査と修正を実施した。

## 修正内容

### markdown_parser.py

| 修正 | 内容 |
|------|------|
| 画像パス解決 | `_resolve_image_path()` 追加。`02_draft/` → 記事ルートの順にフォールバック |
| 番号付きリスト | `_NUMBERED_LIST_PATTERN` 追加。`1. text` → `numbered_list_item` ブロック |
| Bold 除去 | `_BOLD_PATTERN` で `**text**` → `text` に変換 |
| Italic 除去 | `_ITALIC_PATTERN` で `*text*` → `text` に変換（ディスクレーマー対応） |
| テーブル画像パス | `_handle_table` が `article_root/images/table_N.png` に解決（`tables/` → `images/` 統一） |

### browser_client.py

| 修正 | 内容 |
|------|------|
| 画像アップロードタイミング | `_trigger_image_upload()` を「+」→ wait → 「画像」→ wait の順次処理に変更 |
| file input 検出 | `wait_for_selector` に `state="attached"` を指定（note.com が hidden で追加するため） |
| 区切り線 | `_insert_separator()` を「+」メニュー → 「区切り線」のメニュー経由に変更 |
| upload_image 待機 | 画像処理のため `asyncio.sleep(2)` を追加 |

### テスト修正

- 全テストのディレクトリ構造を実運用（`02_draft/revised_draft.md` + 記事ルート `images/`）に合わせて修正
- 17テスト全合格

## 決定事項

1. 画像パスは `02_draft/` → 記事ルートの順にフォールバック解決する
2. テーブル画像は `article_root/images/table_N.png` に保存（`tables/` ではなく）
3. `input[type="file"]` は `state="attached"` で検索する（note.com の hidden 対応）
4. 区切り線は「+」メニュー経由で挿入する
5. 太字のみ行(`**text**`)の引用ブロック変換は**不採用**（ユーザー判断で取りやめ）

## 変更ファイル

- `scripts/note_publisher/markdown_parser.py`
- `scripts/note_publisher/browser_client.py`
- `tests/scripts/note_publisher/test_markdown_parser.py`
- `articles/stock_analysis/2026-03-28_indonesia-telecom-sector/meta.yaml`
