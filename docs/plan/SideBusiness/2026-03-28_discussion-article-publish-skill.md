# 議論メモ: article-publish スキル作成 — 株投資ラボ note.com 下書き投稿

**日付**: 2026-03-28
**参加**: ユーザー + AI

## 背景・コンテキスト

articles/ ディレクトリの金融記事を株投資ラボの note.com アカウントに下書き投稿するワークフローが必要だった。既存の kuroto-area-note（玄人領域）の note 投稿ロジックを参考に、金融記事専用のスキルを作成した。

## 議論のサマリー

### 1. スキル設計・実装
- `.claude/skills/article-publish/SKILL.md` を新規作成
- 既存の `scripts/publish_to_note.py`（Playwright ブラウザ自動化）を活用
- kuroto の `--creator-mode` を参考にしつつ、標準モード（`markdown_parser.py` → `DraftPublisher`）を使用

### 2. テスト投稿で発見した問題
- **画像未生成エラー**: `browser_client.py` の `upload_image` が `FileNotFoundError` を raise してブロック → warning + skip に修正
- **セッション混同**: デフォルトの `note-storage-state.json` が別アカウント（不明）用で、株投資ラボではなかった
- **TOC 未挿入**: 標準パーサーは TOC 自動挿入未対応（creator モードのみ対応）
- **ドラフト URL 未出力**: 標準モードで stdout に URL を print していなかった

### 3. アカウント別セッション管理
- `note-storage-state-kabu-lab.json` を株投資ラボ専用セッションとして作成
- スキルで `NOTE_SESSION_PATH` 環境変数を明示指定する設計に変更
- 最終テスト: FOMC 記事を株投資ラボアカウントに投稿成功（exit code 0）

## 決定事項

1. **アカウント別セッション管理**: 株投資ラボ用は `note-storage-state-kabu-lab.json`。`NOTE_SESSION_PATH` で明示指定必須。
2. **画像未生成時はスキップ**: `FileNotFoundError` → warning + return に変更。投稿中断せず続行。

## アクションアイテム

- [ ] 標準パーサーに TOC 自動挿入機能を追加（優先度: 中）
- [ ] structlog の最終ログ欠落問題を調査・修正（優先度: 低）
- [ ] 投稿済み記事の表画像を generate-table-image で生成（優先度: 中）

## 変更ファイル

| ファイル | 変更内容 |
|---------|---------|
| `.claude/skills/article-publish/SKILL.md` | 新規作成 |
| `scripts/note_publisher/browser_client.py` | 画像未生成時 skip |
| `scripts/publish_to_note.py` | 標準モードで draft URL を stdout 出力 |
| `data/config/note-storage-state-kabu-lab.json` | 株投資ラボ用セッション新規作成 |

## セッション一覧

| ファイル | アカウント |
|---------|----------|
| `note-storage-state.json` | 不明（旧デフォルト） |
| `note-storage-state-kabu-lab.json` | 株投資ラボ |
| `note-storage-state-mitsuki.json` | mitsuki |

## テスト結果

- FOMC 記事（144 ブロック）を株投資ラボアカウントに投稿成功
- 下書き URL: `https://editor.note.com/notes/ndaaedf0cb9fb/edit/`
