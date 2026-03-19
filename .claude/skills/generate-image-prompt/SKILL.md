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
カテゴリ別カラープリセットに基づき、noteサムネイル用とX投稿用の2種類を出力。

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
Step 2: カラープリセット決定 ─── カテゴリ→カラーマッピング
    |
Step 3: テーマ→抽象モチーフ変換 ─── 記事の構造を視覚的動勢に翻訳
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

### Step 2: ブランド統一スタイル + カテゴリ別カラープリセット

**全カテゴリ共通**: 抽象画（油彩・アクリル）ベース。
カテゴリの差別化はカラーパレットと動勢（ストロークの方向性）で行う。
詳細は `guide.md` を参照。

#### ブランド共通ビジュアルシグネチャ

全プロンプトに以下の要素を必ず含める:
- **deep charcoal or black background** (暗い背景で色彩を際立たせる)
- **thick impasto brushstrokes with visible texture** (厚塗りで絵画の物質感を出す)
- **metallic gold accents** (ブランド共通のゴールドアクセント)
- **oil on canvas texture** (キャンバスの質感で「本物の絵画」感を出す)

これらの要素がnoteアカウント全体のブランドトーンを統一する。
どのカテゴリの記事サムネイルを並べても「同じシリーズの作品」と認識できる。

#### カテゴリ別カラープリセット概要

| カテゴリ | カラーパレット | 動勢（ストローク方向） | 参照アーティスト |
|---------|-------------|-------------------|---------------|
| macro_economy | deep blue + gold | 水平に広がる大きな面 | Rothko, Motherwell |
| asset_management | warm green + earth tones | 下から上へ有機的に成長 | Monet (abstract), Frankenthaler |
| stock_analysis | navy + teal + silver | 鋭い対角線が交差 | Kline, Soulages |
| market_report | dark blue + red + green | 力強い水平衝突 | de Kooning, Hartung |
| side_business | amber + violet + teal | 複数の流れが一点に収束 | Kandinsky, Zaha Hadid |
| quant_analysis | cool blue + cyan + black | 精密な幾何学パターン | Mondrian, Vasarely |
| investment_education | warm gold + cream + blue | 柔らかく外側へ展開 | Turner (abstract), Rothko |

### Step 3: テーマ→抽象モチーフ変換

記事の内容を具体的なモノではなく、**動勢・エネルギー・構造**として抽出する:
- 記事の核心的な「動き」は何か（収束？拡散？衝突？成長？）
- テーマ数に対応する色数（例: 3つの副業 → 3色の流れ）
- 記事のトーン → ストロークの激しさ（ポジティブ=流麗 / 警告=荒い）
- 具体物は描かない。色・形・動きだけで記事の本質を表現する

### Step 4: noteサムネイル用プロンプト生成

英語で以下の構造のプロンプトを生成:

```
[Abstract painting style + artist reference], [Color composition + movement], [Texture: thick impasto, palette knife, visible brushwork], [Background: deep charcoal/black], [Gold accents], [Technical specs: oil on canvas, landscape 1280x670, no text, no letters, no words]
```

### Step 5: X投稿用プロンプト生成

noteサムネイルをベースに調整:
- よりシンプルで大胆な構図（要素を減らす）
- コントラスト強化（SNSフィードで目立つ）
- 抽象表現主義的な「一撃の爆発力」
- サイズ: 1200x675 (16:9)

### Step 6: ファイル出力

`{article_dir}/02_draft/image_prompts.md` に出力。
既存ファイルがある場合はユーザーに確認。

## 完了報告

```
## 画像プロンプトを生成しました

- **カテゴリ**: {category}
- **カラー**: {primary colors}
- **動勢**: {movement description}
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
- **全カテゴリで抽象画（油彩/アクリル）スタイルを使用する**
- **ブランド共通要素を必ず含める**: dark background, impasto texture, metallic gold accents, oil on canvas
- **絵画の物質感を指定する**: thick impasto, palette knife texture, visible brushwork, drips のいずれかを含める（AI生成のツルツル感を回避するため）
- "no text, no letters, no words" を必ず含める
- サイズ/アスペクト比を指定する
- 日本語メモで意図を説明する

### SHOULD

- 記事の構造（収束・拡散・衝突・成長）を抽象的な動勢に変換する
- 記事のテーマ数に対応する色数を使う
- カテゴリのカラープリセットに従いつつ、記事固有のバリエーションを出す
- 参照アーティスト名を含めてスタイルの方向性を示す
- 全記事のサムネイルが「同じギャラリーの作品」に見えるトーンを維持する

### NEVER

- プロンプト内に日本語を混ぜない
- 具体的な人物・オブジェクト・風景を主題にしない（抽象に徹する）
- 著作権のあるキャラクターやロゴを指定しない
- テキスト/文字を画像内に入れる指示をしない
- "smooth", "clean", "digital art", "3D render" など AI生成っぽくなる語を使わない

## 関連リソース

| ファイル | 内容 |
|---------|------|
| `guide.md` | カテゴリ別カラープリセット詳細・アーティスト参照・プロンプト構築ルール |
| `.claude/skills/x-post-generator/SKILL.md` | X投稿生成（同じ記事ディレクトリを入力に使用） |
| `.claude/skills/generate-chart-image/SKILL.md` | チャート画像生成（記事内チャート用） |
| `.claude/skills/generate-table-image/SKILL.md` | 表画像生成（記事内テーブル用） |

## 完了条件

- [ ] meta.yaml とドラフトが正常に読み込まれている
- [ ] カテゴリに対応するカラープリセットが適用されている
- [ ] 記事の構造が抽象的な動勢に変換されている
- [ ] noteサムネイル用プロンプト（1280x670）が英語で生成されている
- [ ] X投稿用プロンプト（1200x675）が英語で生成されている
- [ ] 両プロンプトにブランド共通要素（dark bg, impasto, gold, canvas）が含まれている
- [ ] 両プロンプトに "no text, no letters, no words" が含まれている
- [ ] 日本語メモが付記されている
- [ ] `{article_dir}/02_draft/image_prompts.md` に出力されている
