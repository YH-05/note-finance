# 議論メモ: note.com 下書き投稿ルール実装

**日付**: 2026-04-05
**参加**: ユーザー + AI

## 背景・コンテキスト

revised_draft.md から note.com に下書き投稿する際の表示品質を改善するため、
`scripts/note_publisher/markdown_parser.py` に3つの新ルールを実装した。

## 実装内容

### ルール1: 参考データソース節の除外

`## 参考データソース` または `## 参考情報` で始まるセクションを note.com 投稿から除外する。
revised_draft.md にはアーカイブ用として残してよい。

**実装**: `_remove_references_section(body: str) -> str`
- 対象見出し: `_REFERENCES_HEADINGS = ("## 参考データソース", "## 参考情報")`
- 除去範囲: 対象見出しから次の `免責事項` 行または次の `##`/`#` 見出しまで

### ルール2: 免責事項直前の区切り線を1本に統一

免責事項の直前には複数の `---` が置かれることがあったが、常に1本だけに統一する。

**実装**: `_relocate_disclaimer()` に末尾separator除去ループを追加
```python
while remaining_blocks and remaining_blocks[-1].block_type == "separator":
    remaining_blocks.pop()
```
その後、canonical separator を1本だけ追加してから免責事項ブロックを追加。

### ルール3: 段落間に空行を挿入（paragraph → paragraph）

連続する段落ブロックの間に空の段落ブロックを自動挿入し、
note.com 上で1行分の視覚的空白を確保する。

**実装**: `_insert_paragraph_spacing(body_blocks) -> list[ContentBlock]`
- `paragraph → paragraph` の遷移のみ対象
- 見出し・リスト・画像・引用との境界には挿入しない

### 実装方針の選択（ルール3）

**A案**: `browser_client.py` でEnterキーを2回押す  
**B案**: パーサーが空段落ブロックを挿入する（採用）

B案を採用した理由: paragraph→paragraph の遷移のみを対象にできる。
見出し・リスト・画像との境界に不要な空白が入らず、より制御しやすい。

## 修正ファイル

| ファイル | 変更内容 |
|---------|---------|
| `scripts/note_publisher/markdown_parser.py` | `_remove_references_section`, `_relocate_disclaimer`修正, `_insert_paragraph_spacing` 追加 |
| `tests/scripts/note_publisher/test_markdown_parser.py` | `TestReferencesSection`, `TestDisclaimerSeparatorCount`, `TestParagraphSpacing` 追加 |
| `.claude/skills/article-publish/SKILL.md` | 「自動除去・整形されるセクション」テーブル追記 |

## 検証結果

- 141テスト全通過
- pyright エラー 0件
- 実記事（iran-war-japan-investors）でのドライラン: 正常動作確認

## 決定事項

1. 参考データソース節は note.com 投稿から除外する（revised_draft.md には残す）
2. 免責事項直前の区切り線は常に1本に統一する
3. 段落スペーシングはパーサー側（B案）で実装する

## アクションアイテム

なし（実装・テスト・ドキュメント化すべて完了）

## 次回の議論トピック

- 他の自動除去・整形パターンがあれば追加検討
