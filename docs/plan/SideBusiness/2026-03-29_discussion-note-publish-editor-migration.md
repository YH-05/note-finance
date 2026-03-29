# 議論メモ: note.com エディター移行対応 & インドネシアテレコム記事投稿完了

**日付**: 2026-03-29
**参加**: ユーザー + AI

## 背景・コンテキスト

note.com が記事エディターを `note.com/notes/new` から `editor.note.com/new` サブドメインに移行した。
これにより、既存の Playwright ヘッドレス Chromium による自動投稿が失敗するようになった。

## 議論のサマリー

- `NOTE_HEADLESS=true`（デフォルト）で実行すると `editor.note.com` で無限ローディングになる
- ヘッドレス検出回避が必要：`NOTE_HEADLESS=false` + `channel="chrome"` で実際のChromeを使うと正常動作
- セッション管理の問題：`--login-only` 実行時に `NOTE_SESSION_PATH` を未指定だと `/Volumes/NeoData/note-finance-data/config/` に保存しようとするが、このディレクトリが存在しないため保存失敗
- デバッグ手順：スクリーンショット取得で現象を確認、セレクター検査で原因特定

## 決定事項

1. **note.com自動投稿は `NOTE_HEADLESS=false` で実行する**（ヘッドレスモード禁止）
   - `editor.note.com` がヘッドレスChromiumを検出し無限ローディングになることを確認
   - `channel="chrome"` で実際のChromeを使うことで正常動作

2. **投稿・ログインコマンドには必ず `NOTE_SESSION_PATH=data/config/note-storage-state-kabu-lab.json` を付与する**
   - デフォルトパスは NeoData（外付けSSD）を指しており、`config/` ディレクトリが存在しない
   - セッション保存に失敗してもエラーにならず、旧ファイルが残るため気づきにくい

3. **インドネシア通信セクター記事（2026-03-28_indonesia-telecom-sector）を下書き投稿完了**
   - 下書きURL: https://editor.note.com/notes/n2e2a53609a1a/edit/
   - 内容: rev5（リンク全削除・競争環境表画像化・TOWR/TBIG Neo4jデータ補完済み）
   - 注: `table_competition.png` は `02_draft/images/` 以下で探されるため未アップロード → 手動対応必要

## アクションアイテム

- [ ] note.com で下書きを確認、`table_competition.png` を手動でアップロード（優先度: 高）
- [ ] article-publish SKILL.md に `NOTE_HEADLESS=false` 必須・`NOTE_SESSION_PATH` 明示指定を追記（優先度: 高）
- [ ] 残り2本のIndonesia Telecom関連記事を投稿（act-2026-03-29-002、進捗1/3）

## 技術詳細

### デバッグで判明した事実

```python
# セッション確認
session_ok = True  # _restore_session() は _note_session_v5 クッキーで True を返す

# URL確認（非headless Chrome）
# note.com/notes/new → editor.note.com/new → editor.note.com/notes/{id}/edit/

# セレクター（新エディターでも有効）
'div[contenteditable="true"]'  # FOUND
'.ProseMirror'                  # FOUND
```

### 正しい実行コマンド

```bash
# ログイン
NOTE_HEADLESS=false NOTE_SESSION_PATH=data/config/note-storage-state-kabu-lab.json \
  uv run python scripts/publish_to_note.py --login-only

# 投稿
NOTE_HEADLESS=false NOTE_SESSION_PATH=data/config/note-storage-state-kabu-lab.json \
  uv run python scripts/publish_to_note.py articles/stock_analysis/2026-03-28_indonesia-telecom-sector
```

### 画像パス問題

スクリプトが `article_dir/02_draft/images/` 以下で画像を探すが、実際の画像は `article_dir/images/` にある。
→ note.com上で手動アップロードするか、スクリプトの画像パス解決ロジックを修正する。
