---
name: generate-image-prompt
description: >
  note記事のサムネイル画像用AIプロンプト（Nano Banana向け英語プロンプト）を生成するスキル。
  記事のrevised_draft.mdとmeta.yamlを読み込み、カテゴリ別スタイルプリセットに基づいて
  noteサムネイル用（1280x670）とX投稿用（1200x675）の2種類の画像プロンプトを出力する。
  「サムネイル画像」「画像プロンプト」「image prompt」「Nano Banana」「サムネ作って」
  「OGP画像」「カバー画像のプロンプト」と言われたら必ずこのスキルを使うこと。
  article-publish前にプロアクティブに使用を提案すること。
allowed-tools: Read, Write, Glob
---

# 画像プロンプト生成スキル

note記事ディレクトリから、Nano Banana（AI画像生成ツール）向けの英語プロンプトを生成する。
カテゴリ別スタイルプリセットに基づき、noteサムネイル用とX投稿用の2種類を出力。

## 入力

| パラメータ | 必須 | デフォルト | 説明 |
|-----------|------|----------|------|
| `@article_dir` | ○ | 文脈から推測 | 記事ディレクトリ（`articles/{category}/{YYYY-MM-DD}_{slug}/`） |

```
/generate-image-prompt @articles/macro_economy/2026-03-19_boj-rate-hike/
/generate-image-prompt @articles/asset_management/2026-03-15_new-nisa-guide/
```

## 出力

`{article_dir}/02_draft/image_prompts.md`

出力形式:

```markdown
---
article_id: {meta.yamlのarticle_id}
category: {category}
target_tool: nano_banana
generated_at: {ISO 8601}
---

## noteサムネイル用プロンプト (1280x670)

### プロンプト（英語）

{英語プロンプト}

### 日本語メモ

{このプロンプトの意図の日本語説明}

---

## X投稿用サムネイル用プロンプト (1200x675)

### プロンプト（英語）

{英語プロンプト}

### 日本語メモ

{このプロンプトの意図の日本語説明}
```

## 処理フロー

```
Step 1: 記事コンテンツ読み込み ─── meta.yaml + revised_draft.md
    |
Step 2: スタイルプリセット決定 ─── カテゴリ→スタイルマッピング
    |
Step 3: テーマ・キーワード抽出 ─── 記事から視覚要素を特定
    |
Step 4: noteサムネイル用プロンプト生成 ─── 1280x670
    |
Step 5: X投稿用プロンプト生成 ─── 1200x675
    |
Step 6: ファイル出力 ─── image_prompts.md
```

### Step 1: 記事コンテンツ読み込み

1. `meta.yaml` からカテゴリ・タイトル・テーマ・target_audience を取得
2. 優先順位: `02_draft/revised_draft.md` > `02_draft/first_draft.md`
3. 記事がない場合はエラー

### Step 2: カテゴリ別スタイルプリセット

詳細は `guide.md` を参照。概要:

| カテゴリ | スタイル | カラートーン |
|---------|---------|------------|
| macro_economy | photorealistic | deep blue, gold accents |
| asset_management | flat illustration | warm green, soft blue |
| stock_analysis | conceptual art | navy blue, teal |
| market_report | photorealistic | dark blue, red/green accents |
| side_business | flat illustration | orange, purple |
| quant_analysis | technical/abstract | dark theme, neon blue/cyan |
| investment_education | flat illustration | bright blue, yellow |

### Step 3: テーマ・キーワード抽出

記事から以下を特定:
- メインテーマ（1-2語）
- サブテーマ・キーワード（3-5語）
- 記事のトーン（ポジティブ/ニュートラル/警告的）
- 具体的な対象（銘柄名、国名、指標名など）

### Step 4: noteサムネイル用プロンプト生成

英語で以下の構造のプロンプトを生成:

```
[Style description], [Main subject/scene], [Color palette], [Mood/atmosphere], [Composition notes], [Technical specs: 1280x670, high quality, no text overlay]
```

### Step 5: X投稿用プロンプト生成

noteサムネイルをベースに調整:
- よりアイキャッチ力を高める（bold, eye-catching, vibrant）
- シンプルで一目で理解できる構図
- サイズ: 1200x675 (16:9)

### Step 6: ファイル出力

`{article_dir}/02_draft/image_prompts.md` に出力。
既存ファイルがある場合はユーザーに確認。

## 完了報告

```
## 画像プロンプトを生成しました

- **カテゴリ**: {category}
- **スタイル**: {style_preset}
- **メインテーマ**: {main_theme}
- **出力ファイル**: {article_dir}/02_draft/image_prompts.md

### noteサムネイル用プロンプト（プレビュー）
> {プロンプトの最初の100文字}...

### X投稿用サムネイル用プロンプト（プレビュー）
> {プロンプトの最初の100文字}...

Nano Bananaにコピー&ペーストして画像を生成してください。
```

## MUST / SHOULD / NEVER

### MUST

- プロンプトは必ず英語で生成する
- カテゴリ別スタイルプリセットに従う
- "no text, no letters, no words" を必ず含める
- サイズ/アスペクト比を指定する
- 日本語メモで意図を説明する

### SHOULD

- 記事の具体的な対象（国名、企業名など）を視覚的比喩に変換する
- 季節感や時事性を反映する（例: 春の桜→日本経済の話題なら桜のモチーフ）
- カラーパレットをカテゴリのブランドカラーに揃える

### NEVER

- プロンプト内に日本語を混ぜない
- 実在の人物の顔を指定しない
- 著作権のあるキャラクターやロゴを指定しない
- テキスト/文字を画像内に入れる指示をしない

## 関連リソース

| ファイル | 内容 |
|---------|------|
| `guide.md` | カテゴリ別スタイルプリセット詳細・プロンプト構築ルール・トラブルシューティング |
| `.claude/skills/x-post-generator/SKILL.md` | X投稿生成（同じ記事ディレクトリを入力に使用） |
| `.claude/skills/generate-chart-image/SKILL.md` | チャート画像生成（記事内チャート用） |
| `.claude/skills/generate-table-image/SKILL.md` | 表画像生成（記事内テーブル用） |

## 完了条件

- [ ] meta.yaml とドラフトが正常に読み込まれている
- [ ] カテゴリに対応するスタイルプリセットが適用されている
- [ ] noteサムネイル用プロンプト（1280x670）が英語で生成されている
- [ ] X投稿用プロンプト（1200x675）が英語で生成されている
- [ ] 両プロンプトに "no text, no letters, no words" が含まれている
- [ ] 日本語メモが付記されている
- [ ] `{article_dir}/02_draft/image_prompts.md` に出力されている
