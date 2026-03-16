---
description: 記事をnote.comに下書き投稿します。
argument-hint: @<article_dir> [--dry-run] [--login-only]
---

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
/article-publish --login-only
```

### 2. ファイルパス指定（`@filepath`）

共通パス解決ロジックに従う。詳細は `.claude/commands/_shared/path-resolution.md` を参照。

```
/article-publish @articles/asset_management/2026-03-15_new-nisa-guide/
```

### 3. 引数なし

引数が指定されていない場合は、ユーザーに記事ディレクトリのパスの入力を求める。

## 前提条件

### セッションの準備（初回のみ）

note.comへの投稿にはログイン済みセッションが必要です。初回は以下を実行してください:

```bash
NOTE_HEADLESS=false uv run python scripts/publish_to_note.py --login-only
```

ブラウザが開くので、手動でnote.comにログインしてください。ログイン完了後、セッションが `data/config/note-storage-state.json` に保存されます。

### 記事の準備

- `revised_draft.md` が `{article_dir}/02_draft/revised_draft.md` に存在すること
- `/article-critique` で批評・修正が完了済みであること
- `meta.yaml` の `status` が `"review"` であることを推奨

## 処理フロー

```
Step 1: 前提確認
├── meta.yaml の status 確認
├── revised_draft.md の存在確認
└── セッションファイルの存在確認

Step 2: ドライラン（推奨）
├── Markdownパース実行
├── パース結果のサマリー表示
└── ユーザー確認

Step 3: 投稿実行
├── ブラウザ起動
├── セッション復元
├── 新規下書き作成
├── タイトル・本文入力
├── 画像アップロード
└── 下書き保存

Step 4: 後処理
├── 03_published/article.md にコピー
├── meta.yaml 更新
└── 結果報告
```

## 実行手順

### Step 1: 前提確認

1. **記事ディレクトリの解決**

   引数から記事ディレクトリを特定し、以下を確認:
   - `meta.yaml` が存在するか
   - `02_draft/revised_draft.md` が存在するか

2. **ステータス確認**

   ```
   meta.yaml を読み込み:
   - status が "review" でない場合:

   ⚠️ 記事ステータスが "review" ではありません。
   現在のステータス: {status}

   /article-critique で批評・修正を完了してから投稿してください。
   それでも投稿する場合は「続行」と入力してください。
   ```

3. **セッション確認**

   ```
   data/config/note-storage-state.json の存在を確認:
   - 存在しない場合:

   ⚠️ note.com セッションが未設定です。
   初回ログインを実行してください:

   /article-publish --login-only
   ```

### Step 2: ドライラン

4. **ドライラン実行**

   ```bash
   uv run python scripts/publish_to_note.py {article_dir} --dry-run
   ```

   **注意**: ドライランでは `02_draft/revised_draft.md` を対象にパースします。

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

   スクリプトは `02_draft/revised_draft.md` を投稿対象として処理します。

### Step 4: 後処理

7. **公開ファイルのコピー**

   ```bash
   cp 02_draft/revised_draft.md 03_published/article.md
   ```

8. **meta.yaml の更新**

   ```yaml
   status: "published"
   workflow:
     publish: "done"    # ← 更新
   note_url: "{draft_url}"
   updated_at: "YYYY-MM-DD"
   ```

9. **成功時の報告**

   ```markdown
   ## note.com 下書き投稿完了

   - **トピック**: {topic}
   - **カテゴリ**: {category}
   - **タイトル**: {title}
   - **下書きURL**: {draft_url}
   - **ステータス**: published

   ### 更新されたファイル
   - `meta.yaml` - status を "published" に更新
   - `03_published/article.md` - 最終版をコピー

   ### 次のステップ
   1. note.com で下書きを確認
   2. カバー画像・タグを設定
   3. 公開ボタンで公開
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
/article-publish --login-only

# ドライランで確認
/article-publish @articles/asset_management/2026-03-15_new-nisa-guide/ --dry-run

# 投稿実行
/article-publish @articles/asset_management/2026-03-15_new-nisa-guide/

# サブディレクトリからの指定も可能
/article-publish @articles/asset_management/2026-03-15_new-nisa-guide/02_draft/revised_draft.md
```

## エラーハンドリング

### エラーコード一覧

| コード | 説明 | 対処法 |
|--------|------|--------|
| E001 | revised_draft.md が見つからない | /article-critique で記事を作成 |
| E002 | Markdownパースエラー | revised_draft.md の形式を確認 |
| E003 | ブラウザ起動エラー | playwright install chromium を実行 |
| E004 | note.com ログインエラー | --login-only で再ログイン |
| E005 | 下書き保存エラー | note.com の状態を確認し再実行 |

## 関連コマンド

- **前提コマンド**: `/article-critique`（批評・修正完了で `status=review`）
- **統合コマンド**: `/article-full`（全工程一括実行）
- **旧コマンド**: `/publish-to-note`（このコマンドで置き換え）
- **CLIスクリプト**: `scripts/publish_to_note.py`
