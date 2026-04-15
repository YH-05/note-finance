---
name: article-publish
description: |
  articles/ ディレクトリにある金融記事のドラフト（revised_draft.md）を
  株投資ラボの note.com アカウントに下書き投稿するスキル。
  Playwright ブラウザ自動化で note.com エディタを操作し、
  見出し・段落・リスト・画像・目次を自動入力して下書き保存する。
  「記事を投稿」「noteに投稿」「下書きに投稿」「article-publish」
  「noteに下書き保存」「投稿して」と言われたら必ずこのスキルを使うこと。
  記事ディレクトリ指定または記事一覧からの選択に対応。
---

# article-publish: 株投資ラボ note.com 下書き投稿

`articles/` 配下の金融記事を株投資ラボの note.com アカウントに下書き投稿する。

## 前提

- 投稿対象: `articles/{category}/{slug}/02_draft/revised_draft.md`
- セッション: `data/config/note-storage-state.json`（株投資ラボ用）
- ツール: `scripts/publish_to_note.py`（Playwright ブラウザ自動化）

## 引数

| パラメータ | 必須 | 説明 |
|-----------|------|------|
| `@article_dir` | ※ | 記事ディレクトリパス |
| `--dry-run` | - | パースのみ（ブラウザ操作なし） |
| `--login-only` | - | ログインしてセッション保存のみ |
| `--no-update-meta` | - | meta.yaml を更新しない |

※ `--login-only` 時は不要。引数なしの場合は投稿可能な記事一覧を表示。

## パス解決

`.claude/commands/_shared/path-resolution.md` の共通ロジックに従う。

- `@articles/macro_economy/2026-03-20_article/` → そのまま記事ルート
- `@articles/.../02_draft/revised_draft.md` → 親ディレクトリが記事ルート
- 引数なし → Step 1 の記事一覧を表示してユーザーに選択してもらう

## 処理フロー

### Step 1: 投稿可能な記事の特定

引数がある場合はパス解決を実行。引数なしの場合:

```bash
# articles/ 配下の全記事を走査
# meta.yaml の status が "review" または "draft" のものを一覧表示
```

表示フォーマット:

```
投稿可能な記事:

 # | カテゴリ         | トピック                         | ステータス | 文字数
---|-----------------|--------------------------------|----------|------
 1 | macro_economy   | インドネシア通信セクター分析       | review   | 4,200字
 2 | asset_management| 新NISA実践ガイド                | draft    | 3,800字
 3 | stock_analysis  | TSMC決算分析                   | review   | 5,100字

投稿する記事の番号を入力してください:
```

### Step 2: 前提確認

1. `02_draft/revised_draft.md` の存在確認
2. `meta.yaml` の読み込みとステータス確認
   - `status` が `"review"` でない場合は警告を出し、続行するか確認
3. セッションファイル `data/config/note-storage-state.json` の存在確認
   - 存在しない場合: ログインフローを案内
4. **タイトルフォーマット検証**（`category: earnings` の場合は必須）
   - 詳細ルールは `.claude/skills/finance-article-writer/references/earnings.md` 「タイトルフォーマット」節を参照
   - 必須形式: `【🇺🇸米株決算】{企業名}（{ティッカー}）Q{1-4} {YYYY} 決算プレビュー` または `...決算レビュー`
   - 検証項目:
     - プレフィックス `【🇺🇸米株決算】` が付いているか
     - `Q{1-4}` と4桁の年が含まれているか
     - 末尾が `決算プレビュー` または `決算レビュー` か
     - 対象企業が米国上場であるか（`meta.yaml` の `market: US`、または `av_company_overview.Country == "USA"`、または SEC EDGAR に CIK 登録あり）
   - 検証失敗時: 投稿を中止し、ユーザーに修正を促す。フロントマター `title` と本文最初の `# ` 見出しの両方を修正対象とする
   - 米国外企業（TSMC / ASML / Alibaba 等）の場合: `【🇺🇸米株決算】` を使用してはならない。カテゴリ再検討を促す

```
note.com セッションが未設定です。
初回ログインを実行してください:

NOTE_HEADLESS=false uv run python scripts/publish_to_note.py --login-only

ブラウザが開くので、株投資ラボのアカウントでログインしてください。
```

### Step 3: ドライラン（推奨）

投稿前に必ずドライランで内容を確認する:

```bash
uv run python scripts/publish_to_note.py {article_dir} --dry-run
```

ドライラン結果を表示:

```
## ドライラン結果

- タイトル: {title}
- ブロック数: {block_count}
  - 見出し(h2): {h2_count}
  - 見出し(h3): {h3_count}
  - 段落: {paragraph_count}
  - リスト: {list_count}
  - 画像: {image_count}
  - 目次: あり/なし
- 画像ファイル: {image_paths}

この内容でnote.comに下書き投稿しますか？
```

ユーザーが確認したら Step 4 に進む。`--dry-run` のみの場合はここで終了。

### Step 4: 投稿実行

```bash
NOTE_SESSION_PATH=data/config/note-storage-state-kabu-lab.json uv run python scripts/publish_to_note.py {article_dir}
```

スクリプトが以下を自動実行する:
1. ブラウザ起動（headless）
2. セッション復元
3. 新規下書き作成ページへ遷移
4. タイトル入力
5. 本文ブロック順次挿入（見出し、段落、リスト、引用、画像、区切り線）
6. 下書き保存
7. 下書きURL取得

**注意**: 144ブロック程度の記事で2-3分かかる。ブラウザ操作中は他の操作をしないこと。

**画像が未生成の場合**: 参照先の画像ファイルが存在しない場合はスキップされる（投稿は続行）。
事前に `/generate-table-image` で表画像を生成することを推奨。

**セッション切れの場合**: `NOTE_HEADLESS=false` でブラウザを表示して再ログインする:

```bash
NOTE_HEADLESS=false uv run python scripts/publish_to_note.py --login-only
```

**TOC（目次）について**: 標準パーサーはTOCを自動挿入しない。
TOCが必要な場合は、note.com上の下書きエディタで手動追加するか、
記事内に明示的に目次セクションを含めること。

### Step 5: 後処理

投稿成功時:

1. **公開ファイルのコピー**

```bash
mkdir -p {article_dir}/03_published
cp {article_dir}/02_draft/revised_draft.md {article_dir}/03_published/article.md
```

2. **meta.yaml の更新**

```yaml
status: "published"
note_url: "{draft_url}"
updated_at: "YYYY-MM-DD"
workflow:
  publish: "done"
```

3. **結果報告**

```
## note.com 下書き投稿完了

- トピック: {topic}
- カテゴリ: {category}
- タイトル: {title}
- 下書きURL: {draft_url}

### 次のステップ
1. note.com で下書きを確認・プレビュー
2. カバー画像を設定
3. ハッシュタグを設定
4. 公開ボタンで公開
```

## note.com 自動投稿の技術仕様

`scripts/publish_to_note.py` + `scripts/note_publisher/` パッケージがブラウザ自動化を担当する。
以下のルールを守らないと投稿結果が壊れるため、revised_draft.md の品質確認時に参照すること。

### 自動変換される記法

| markdown | note.com の表示 | 挿入方法 |
|----------|----------------|---------|
| `## text` | 大見出し（h2） | 「+」メニュー → 「大見出し」 |
| `### text` | 小見出し（h3） | 「+」メニュー → 「小見出し」 |
| `> text` | 引用ブロック | 「+」メニュー → 「引用」 |
| `- text` | 箇条書きリスト | 「+」メニュー → 「箇条書きリスト」 |
| `1. text` | 番号付きリスト | 「+」メニュー → 「番号付きリスト」（自動採番） |
| `---` | 区切り線 | 直接入力 |
| `![alt](path)` | 画像 | ファイルアップロード |
| 最初の `##` 直前 | 目次ブロック | 自動挿入（手書き不要） |

### 自動除去・整形されるセクション

パーサーは revised_draft.md を note.com に投稿する際、以下を自動で除外・整形する。
**revised_draft.md 側には従来どおり各セクションを記載してよい**（アーカイブ用に保持される）。

| 対象 | 挙動 | 実装箇所 |
|------|------|---------|
| `## 修正履歴` セクション以降 | 完全に除外 | `markdown_parser.py::_remove_revision_history` |
| `## 参考データソース` / `## 参考情報` セクション | 完全に除外（次の `免責事項` または次の `##` 見出しまで） | `markdown_parser.py::_remove_references_section` |
| 免責事項直前の複数 `---` 区切り線 | 常に1本だけに統一 | `markdown_parser.py::_relocate_disclaimer` |
| 連続する段落ブロック間 | 空段落ブロックを1つ挿入（note.com上で1行分空ける） | `markdown_parser.py::_insert_paragraph_spacing` |

段落スペーシングは `paragraph` → `paragraph` の遷移のみ対象。見出し・リスト・画像・引用との境界には挿入されない（それらのブロックは note.com 側で独自の視覚的分離を持つため）。

### 絶対禁止（投稿前チェック）

| 禁止 | 理由 |
|------|------|
| `**太字:**` を見出し代わりに使う | 太字がそのまま表示され見出しブロックにならない |
| `# ` (h1) を本文中に使う | タイトル行として解釈される |
| マークダウン表をそのまま残す | note.com では崩れる。`/generate-table-image` で画像化必須 |

### 目次（TOC）と イントロ段落

スクリプトが最初の `## ` 見出しの直前に自動で目次ブロックを挿入する。
イントロ段落（`## ` の前のテキスト）がないと目次が記事先頭に来て不自然になるため、
revised_draft.md に必ずイントロ段落を含めること。

## セッション管理

| 項目 | 値 |
|------|-----|
| アカウント | 株投資ラボ |
| セッションファイル | `data/config/note-storage-state-kabu-lab.json` |
| 環境変数 | `NOTE_SESSION_PATH` で指定（必須） |
| セッション有効期限 | 定期的に再ログインが必要 |

**重要**: 投稿コマンドには必ず `NOTE_SESSION_PATH=data/config/note-storage-state-kabu-lab.json` を付与すること。
デフォルトの `note-storage-state.json` は別アカウント用であり、株投資ラボには投稿されない。

セッション切れの場合:

```bash
# ブラウザが開くので株投資ラボアカウントで手動ログイン
NOTE_HEADLESS=false NOTE_SESSION_PATH=data/config/note-storage-state-kabu-lab.json uv run python scripts/publish_to_note.py --login-only
```

## 環境変数

| 変数 | 説明 | デフォルト |
|------|------|-----------|
| `NOTE_HEADLESS` | ヘッドレスモード | `true` |
| `NOTE_SESSION_PATH` | セッションファイル | `data/config/note-storage-state.json` |
| `NOTE_TIMEOUT_MS` | タイムアウト(ms) | `30000` |
| `NOTE_TYPING_DELAY_MS` | タイピング遅延(ms) | `50` |

## エラーハンドリング

| コード | 説明 | 対処法 |
|--------|------|--------|
| E001 | revised_draft.md が見つからない | `/article-draft` + `/article-critique` で記事を作成 |
| E002 | Markdown パースエラー | revised_draft.md の形式を確認 |
| E003 | ブラウザ起動エラー | `uv run playwright install chromium` を実行 |
| E004 | note.com ログインエラー | `--login-only` で再ログイン |
| E005 | 下書き保存エラー | note.com の状態を確認し再実行 |

### セッション切れの自動検出

投稿実行時にログインチェックが失敗した場合、スクリプトは手動ログイン待機モードに移行する。
`NOTE_HEADLESS=false` を設定してから再実行すること。

## 投稿前品質チェックリスト

revised_draft.md の投稿前に以下を確認:

- [ ] マークダウン表がそのまま残っていないか（画像化済みか）
- [ ] 主要データにソースURLが埋め込まれているか
- [ ] `**太字:**` を見出し代わりに使っていないか（`##`/`###` を使うこと）
- [ ] イントロ段落が最初の `## ` の前にあるか
- [ ] 画像ファイルが `images/` に存在するか（参照パスが正しいか）
- [ ] ハッシュタグが記事末尾に含まれているか
- [ ] **earnings カテゴリのみ**: タイトルが `【🇺🇸米株決算】{企業名}（{ティッカー}）Q{1-4} {YYYY} 決算プレビュー/レビュー` 形式か
- [ ] **earnings カテゴリのみ**: 対象が米国上場企業であることを確認済みか（米国外企業にはプレフィックスを付けない）

## 使用例

```bash
# 記事一覧から選択して投稿
/article-publish

# 特定の記事を投稿
/article-publish @articles/macro_economy/2026-03-20_indonesia-telecom/

# ドライランで確認のみ
/article-publish @articles/asset_management/2026-03-15_new-nisa/ --dry-run

# 初回ログイン（セッション保存）
/article-publish --login-only
```

## 関連スキル・コマンド

| スキル/コマンド | 説明 |
|---------------|------|
| `/article-critique` | 投稿前の批評・修正（status → review） |
| `/article-full` | 全工程一括実行 |
| `/generate-table-image` | マークダウン表をPNG画像に変換 |
| `/generate-chart-image` | チャートをPNG画像に生成 |
| `/generate-image-prompt` | サムネイル画像のAIプロンプト生成 |
| `/x-post-generator` | 記事からX投稿文を生成 |
