---
description: 記事をnote.comに下書き投稿します。revised_draft.mdをパースし、Playwrightでnote.comエディタに自動入力します。
---

# note.com 下書き投稿ワークフロー

## パラメータ

| パラメータ | 必須 | デフォルト | 説明 |
|-----------|------|-----------|------|
| article_dir | ○※ | - | 記事ディレクトリのパス |
| --dry-run | - | false | Markdownパースのみ（ブラウザ操作なし） |
| --login-only | - | false | ログインしてセッション保存のみ |

※ `--login-only` 時は不要

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
- `meta.yaml` の `status` が `"ready_for_publish"` であることを推奨

## 処理フロー

```
Step 1: 前提確認
├── meta.yaml の status 確認
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
└── meta.yaml 更新

Step 4: 結果報告
```

## 実行手順

### Step 1: 前提確認

1. **記事ディレクトリの解決**

   引数から記事ディレクトリを特定し、以下を確認:
   - `meta.yaml` が存在するか
   - `02_draft/revised_draft.md` が存在するか

2. **ステータス確認**

   meta.yaml の status が `"ready_for_publish"` でない場合は警告を表示。

3. **セッション確認**

   `data/config/note-storage-state.json` の存在を確認。

### Step 2: ドライラン

4. **ドライラン実行**

   // turbo

   ```bash
   uv run python scripts/publish_to_note.py {article_dir} --dry-run
   ```

5. **パース結果の表示**

   `--dry-run` のみの場合はここで終了。

### Step 3: 投稿実行

6. **投稿コマンド実行**

   ```bash
   uv run python scripts/publish_to_note.py {article_dir}
   ```

### Step 4: 結果報告

7. **成功時**: 下書きURL、更新ファイル、次のステップを表示
8. **失敗時**: エラーコードと対処法を表示

## 環境変数

| 変数名 | 説明 | デフォルト |
|--------|------|-----------|
| NOTE_HEADLESS | ブラウザのヘッドレスモード | true |
| NOTE_TIMEOUT_MS | ブラウザ操作のタイムアウト(ms) | 30000 |
| NOTE_TYPING_DELAY_MS | タイピング遅延(ms) | 50 |
| NOTE_SESSION_PATH | セッションファイルのパス | data/config/note-storage-state.json |

## エラーハンドリング

| コード | 説明 | 対処法 |
|--------|------|--------|
| E001 | revised_draft.md が見つからない | /finance-edit で記事を作成 |
| E002 | Markdownパースエラー | revised_draft.md の形式を確認 |
| E003 | ブラウザ起動エラー | playwright install chromium を実行 |
| E004 | note.com ログインエラー | --login-only で再ログイン |
| E005 | 下書き保存エラー | note.com の状態を確認し再実行 |

## 関連リソース

| リソース | パス |
|---------|------|
| CLIスクリプト | `scripts/publish_to_note.py` |
| パッケージ | `scripts/note_publisher/` |
| 前提コマンド | `/finance-edit` |
| 統合コマンド | `/finance-full` |
