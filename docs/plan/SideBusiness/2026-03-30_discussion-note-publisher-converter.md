# 議論メモ: note.com投稿コンバーター改善 & ディスクレーマー統一

**日付**: 2026-03-30
**参加**: ユーザー + AI

## 背景・コンテキスト

note.comへの記事投稿フロー（`revised_draft.md` → Playwright自動投稿）において、変換ロジックの改善が必要になった。
また、複数のディスクレーマースニペットが乱立しており、統一する必要があった。

## 議論のサマリー

### 変換ロジックの問題点

1. **インラインURL**: `[text](url)` 形式がnote.com上で崩れて表示される
2. **ディスクレーマーの位置**: 記事中途に配置されており、読者体験を妨げていた
3. **H1タイトルの重複**: note.comはタイトル入力フィールドが別途あるため、本文内のH1が二重になる

### スニペット乱立問題

以下の4ファイルが用途が重複しており混乱を招いていた:
- `snippets/not-advice.md` → trash移動
- `snippets/investment-risk.md` → trash移動
- `snippets/nisa-disclaimer.md` → trash移動
- `snippets/disclaimer.md` → 4種を統合した単一スニペットに書き換え

`_relocate_disclaimer()` が「免責事項」キーワードで検出するため、スニペット側の見出しを「免責事項」に統一することで整合性を確保した。

## 決定事項

1. **インラインURL削除ルール**: `_INLINE_LINK_PATTERN.sub(r"\1", text)` で `[text](url)` → `text` に変換
2. **ディスクレーマー末尾移動**: `_relocate_disclaimer()` 関数で「免責事項」含むブロックをseparator+paragraph形式で末尾に再配置
3. **H1タイトル除去**: `_remove_title_from_body()` で body_blocks から level=1 の heading を除去
4. **スニペット統一**: `snippets/disclaimer.md` 1ファイルに4種を統合、見出し「免責事項」に統一

## 変更ファイル一覧

### Python実装
- `scripts/note_publisher/markdown_parser.py` — 3ルール追加
- `tests/scripts/note_publisher/test_markdown_parser.py` — 新テスト追加（26テスト全通過）

### スニペット
- `snippets/disclaimer.md` — 4スニペット統合版に書き換え
- `trash/not-advice.md`, `trash/investment-risk.md`, `trash/nisa-disclaimer.md` — 旧ファイル移動

### Claude設定ファイル（11件）
- `.claude/skills/finance-article-writer/references/common-rules.md`
- `.claude/skills/finance-article-writer/references/asset-management.md`
- `.claude/agents/finance-reviser.md`
- `.claude/agents/asset-management-reviser.md`
- `.claude/agents/finance-critic-compliance.md`
- `.claude/resources/critique-criteria/compliance-standards.md`
- `.claude/resources/critique-criteria/writer-rules-evaluation.md`
- `.claude/skills/asset-management-workflow/SKILL.md`
- `.claude/skills/asset-management-workflow/guide.md`
- `.claude/skills/article-revise/SKILL.md`
- `.claude/commands/asset-management.md`

## アクションアイテム

- [ ] 今日note.com下書き投稿した2記事を新変換ルールで再投稿、旧下書きを手動削除 (優先度: 中)
  - `articles/investment_education/2026-03-30_index-investing-beginners-guide/`
  - `articles/investment_education/2026-03-30_orukan-vs-sp500-diversification-shift/`
- [ ] `/sync-claude-gemini` で `.agents/` ミラーを同期し、旧スニペット参照を更新 (優先度: 低)

## 次回の議論トピック

- 既存記事の再投稿ワークフローの整備（上書き投稿機能の検討）
