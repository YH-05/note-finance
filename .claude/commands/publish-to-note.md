---
description: 記事をnote.comに下書き投稿します。revised_draft.mdをパースし、Playwrightでnote.comエディタに自動入力します。
argument-hint: @<article_dir> [--dry-run] [--login-only]
---

> ⚠️ **非推奨**: このコマンドは非推奨です。代わりに `/article-publish` を使用してください。
> 既存の記事パス形式（`articles/{old_format}/`）は引き続きサポートされますが、
> 新規記事は新しいコマンドで作成してください。

記事をnote.comに下書き投稿します。

## 入力パラメータ

| パラメータ | 必須 | デフォルト | 説明 |
|-----------|------|-----------|------|
| @article_dir | ○※ | - | 記事ディレクトリのパス |
| --dry-run | - | false | Markdownパースのみ（ブラウザ操作なし） |
| --login-only | - | false | ログインしてセッション保存のみ |

※ `--login-only` 時は不要

## 引数の解釈ルール

`$ARGUMENTS` を以下の優先順で解釈する:

### 1. `--login-only`

セッション未保存時の初回ログイン用。ブラウザが開くので、手動でnote.comにログインする。

```
/publish-to-note --login-only
```

### 2. ファイルパス指定（`@filepath`）

ユーザーが `@` でファイルまたはディレクトリを指定した場合、そのパスから記事ディレクトリを自動特定する。

```
/publish-to-note @articles/asset_formation/my-article/
```

**パス解決ロジック:**
1. 指定されたパスの絶対パスを取得する
2. パスに `/02_draft/` が含まれる場合 → その親ディレクトリを記事ルートとする
3. パスに `/01_research/` や `/03_published/` が含まれる場合 → 同様に親ディレクトリを記事ルートとする
4. 指定パスがディレクトリの場合 → そのディレクトリを記事ルートとする

### 3. `--dry-run`

Markdownパースのみを実行し、ブラウザ操作を行わない。投稿前の確認用。

```
/publish-to-note @articles/asset_formation/my-article/ --dry-run
```

## 前提条件

### セッションの準備（初回のみ）

note.comへの投稿にはログイン済みセッションが必要です。初回は以下を実行してください:

```bash
NOTE_HEADLESS=false uv run python scripts/publish_to_note.py --login-only
```

ブラウザが開くので、手動でnote.comにログインしてください。ログイン完了後、セッションが `data/config/note-storage-state.json` に保存されます。

### 記事の準備

- `revised_draft.md` が `{article_dir}/02_draft/revised_draft.md` に存在すること
- `/finance-edit` または `/finance-full` で編集完了済みであること
- `article-meta.json` の `status` が `"ready_for_publish"` であることを推奨

## 処理フロー

```
Step 1: 前提確認
├── article-meta.json の status 確認
├── revised_draft.md の存在確認
└── セッションファイルの存在確認

Step 2: ドライラン（推奨）
├── Markdownパース実行
├── パース結果のサマリー表示
│   ├── タイトル
│   ├── ブロック数
│   ├── 画像数
│   └── フロントマター
└── ユーザー確認

Step 3: 投稿実行
├── ブラウザ起動
├── セッション復元（または手動ログイン待機）
├── 新規下書き作成
├── タイトル入力
├── 本文ブロック挿入
│   ├── 見出し（h2, h3）
│   ├── 段落
│   ├── リスト
│   ├── 引用
│   ├── 画像アップロード
│   └── 区切り線
├── 下書き保存
└── article-meta.json 更新

Step 4: 結果報告
```

## 実行手順

### Step 1: 前提確認

1. **記事ディレクトリの解決**

   引数から記事ディレクトリを特定し、以下を確認:
   - `article-meta.json` が存在するか
   - `02_draft/revised_draft.md` が存在するか

2. **ステータス確認**

   ```
   article-meta.json を読み込み:
   - status が "ready_for_publish" でない場合:

   ⚠️ 記事ステータスが "ready_for_publish" ではありません。
   現在のステータス: {status}

   /finance-edit で編集を完了してから投稿してください。
   それでも投稿する場合は「続行」と入力してください。
   ```

3. **セッション確認**

   ```
   data/config/note-storage-state.json の存在を確認:
   - 存在しない場合:

   ⚠️ note.com セッションが未設定です。
   初回ログインを実行してください:

   NOTE_HEADLESS=false uv run python scripts/publish_to_note.py --login-only
   ```

### Step 2: ドライラン

4. **ドライラン実行**

   ```bash
   uv run python scripts/publish_to_note.py {article_dir} --dry-run
   ```

5. **パース結果の表示**

   ```
   ## ドライラン結果

   - **タイトル**: {title}
   - **ブロック数**: {block_count}
     - 見出し: {heading_count}
     - 段落: {paragraph_count}
     - リスト: {list_count}
     - 画像: {image_count}
   - **画像ファイル**: {image_paths}

   この内容でnote.comに下書き投稿しますか？ (y/n)
   ```

   `--dry-run` のみの場合はここで終了。

### Step 3: 投稿実行

6. **投稿コマンド実行**

   ```bash
   uv run python scripts/publish_to_note.py {article_dir}
   ```

   実行結果を確認:
   - `success=True`: 下書きURL取得
   - `success=False`: エラーメッセージ表示

### Step 4: 結果報告

7. **成功時の報告**

   ```markdown
   ## note.com 下書き投稿完了

   - **記事**: {article_id}
   - **タイトル**: {title}
   - **下書きURL**: {draft_url}
   - **ステータス**: published

   ### 更新されたファイル
   - `article-meta.json` - status を "published" に更新
   - `03_published/article.md` - 最終版をコピー

   ### 次のステップ
   1. note.com で下書きを確認
   2. カバー画像・タグを設定
   3. 公開ボタンで公開
   ```

8. **失敗時の報告**

   ```markdown
   ## note.com 投稿エラー

   - **エラーコード**: {error_code}
   - **エラー内容**: {error_message}

   ### エラーコード一覧
   | コード | 説明 | 対処法 |
   |--------|------|--------|
   | E001 | revised_draft.md が見つからない | /finance-edit で記事を作成 |
   | E002 | Markdownパースエラー | revised_draft.md の形式を確認 |
   | E003 | ブラウザ起動エラー | playwright install chromium を実行 |
   | E004 | note.com ログインエラー | --login-only で再ログイン |
   | E005 | 下書き保存エラー | note.com の状態を確認し再実行 |
   ```

## 環境変数

| 変数名 | 説明 | デフォルト |
|--------|------|-----------|
| NOTE_HEADLESS | ブラウザのヘッドレスモード | true |
| NOTE_TIMEOUT_MS | ブラウザ操作のタイムアウト(ms) | 30000 |
| NOTE_TYPING_DELAY_MS | タイピング遅延(ms) | 50 |
| NOTE_SESSION_PATH | セッションファイルのパス | data/config/note-storage-state.json |

## 使用例

```bash
# 初回ログイン（セッション保存）
/publish-to-note --login-only

# ドライランで確認
/publish-to-note @articles/asset_formation/my-article/ --dry-run

# 投稿実行
/publish-to-note @articles/asset_formation/my-article/

# ファイルパスからの指定も可能
/publish-to-note @articles/asset_formation/my-article/02_draft/revised_draft.md
```

## 関連コマンド

- **前提コマンド**: `/finance-edit`（編集完了で `status=ready_for_publish`）
- **統合コマンド**: `/finance-full`（全工程一括実行）
- **CLIスクリプト**: `scripts/publish_to_note.py`
- **パッケージ**: `scripts/note_publisher/`
