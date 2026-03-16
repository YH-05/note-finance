---
name: x-post-generator
description: note記事からX（旧Twitter）投稿文を生成するスキル。記事ディレクトリを指定すると、revised_draft.mdまたはfirst_draft.mdの内容を読んでフックの利いた280字以内の投稿文をx_post.mdに出力する。カテゴリ別ハッシュタグと{URL}プレースホルダーを自動挿入。「X投稿を作成して」「ツイートを書いて」「X用の文章」「SNS投稿」「note記事をXにシェアしたい」「x_post.mdを作って」と言われたら必ずこのスキルを使うこと。記事ディレクトリが指定されている場合も積極的に使うこと。
---

# X投稿生成スキル

note記事ディレクトリから、フックの利いた280字以内のX投稿文を生成する。
ターゲット層（beginner/intermediate/advanced）に応じて文体・フック・ハッシュタグを自動切り替え。
参照ライブラリの優良サンプルをヒントに品質を継続的に向上させる。

## 入力

| パラメータ | 必須 | デフォルト | 説明 |
|-----------|------|----------|------|
| `@article_dir` | ○ | 文脈から推測 | 記事ディレクトリ（`articles/{category}/{YYYY-MM-DD}_{slug}/`） |
| `--audience` | - | meta.yaml の `target_audience` → `intermediate` | `beginner` / `intermediate` / `advanced` |
| `--hook` | - | フック推奨マトリックスから自動決定 | `A`（逆説）/ `B`（疑問形）/ `C`（数字）/ `D`（宣言） |
| `--ref` | - | 自動検索 | 特定参照ファイルを直接指定（例: `references/asset_management/intermediate-index-hook-B.md`） |
| `--no-ref` | - | false | 参照ライブラリをスキップして高速生成 |

```
/x-post @articles/asset_management/2026-03-06_index-investing-portfolio/
/x-post @articles/macro_economy/2026-03-08_boj-rate-hike-yen-scenario/ --audience intermediate
/x-post @articles/... --audience beginner --hook D
/x-post @articles/... --no-ref
```

## 出力

`{article_dir}/02_draft/x_post.md`

```markdown
---
article_id: {article_id}
category: {category}
audience: {beginner|intermediate|advanced}
platform: x
hook_pattern: {A|B|C|D}
char_limit: 280
char_count: {実際の文字数}
status: draft
reference_used: [{参照したサンプルのファイルパス}]
---

{投稿本文}
```

## 処理フロー

### Step 0: パラメータ解決

1. `--audience` が指定されていれば使用
2. 未指定なら `meta.yaml` の `target_audience` を読む
3. それも未設定なら `intermediate` をデフォルト

`--hook` の自動決定（`--hook` 未指定の場合）:

| category | beginner | intermediate | advanced |
|---------|---------|-------------|---------|
| asset_management | C | B | B |
| asset_management | A | B | A |
| macro_economy | C | D | A |
| stock_analysis | B | B | D |
| market_report | C | D | — |
| side_business | B | B | — |
| quant_analysis | C | C | D |
| investment_education | C | B | D |

`—` の場合は intermediate の推奨パターンを使用。

### Step 1: 記事コンテンツの読み込み

優先順位に従って記事本文を読む:
1. `02_draft/revised_draft.md`（最優先）
2. `02_draft/first_draft.md`（フォールバック）

`meta.yaml` からカテゴリ・トピック・target_audience・article_id を取得。

### Step 2: 参照ライブラリ検索（`--no-ref` がない場合）

1. `.claude/skills/x-post-generator/references/index.yaml` を読む
2. `category + audience + hook_pattern` の3軸で最大2件のサンプルを特定
   - 完全一致（category × audience × hook）を優先
   - なければ category × audience で検索
   - 0件の場合はスキップ（フォールバック: 参照なしで通常生成）
3. 特定したサンプルファイルを読み込む
4. `why_it_works` フィールドをヒントとして保持し、生成時に参考にする
5. `--ref` が指定された場合はそのファイルのみを読む

### Step 3: 記事の核心を抽出

記事から以下を特定する:
- **タイトル・テーマ**: 読者が得る最大の価値は何か
- **フックになる事実/逆説**: 意外性のある数字、「常識」への反論、感情的共鳴ポイント
- **記事の核心3点**: 読者が「続きを読みたい」と思うポイント
- **具体的な数字**: あれば必ず使う（例: 「2倍」「7%」「年4.3万円」）

### Step 4: 層別テンプレートの適用

`audience` に応じたテンプレートを参照:
- `beginner`: `.claude/skills/x-post-generator/templates/beginner.md`
- `intermediate`: `.claude/skills/x-post-generator/templates/intermediate.md`
- `advanced`: `.claude/skills/x-post-generator/templates/advanced.md`

フックパターンの詳細は `.claude/skills/x-post-generator/templates/hook-patterns.md` を参照。

**層別主要差分（詳細は各テンプレートを参照）:**

| 次元 | beginner | intermediate | advanced |
|------|---------|-------------|---------|
| 専門用語 | 禁止（括弧解説必須） | 適度に使用 | 積極使用・解説省略 |
| 感情軸 | 共感・安心・「自分でもできる」 | 好奇心・「損してた」 | 反論・逆張り |
| 絵文字 | 積極使用（✅💡📊） | 節度（1-2個） | 原則なし |
| CTA語尾 | 「〜しました！」 | 「〜しました。」 | 「〜を検証しました。」 |
| ハッシュタグ数 | 4-5個 | 3-4個 | 3個 |
| 文字数目安 | 180-230字 | 220-270字 | 230-280字 |

### Step 5: 投稿文の構成

以下のテンプレートに沿って構成する:

```
{フック（選択したパターンA/B/C/Dの書き出し）}

{記事の核心ポイント 2〜3点（箇条書き）}

{誘導文（層に応じたCTA語尾）}
{URL}

{ハッシュタグ}
```

**構成上の制約:**
- 全体で **280字以内**（URLは23字として計算しない ← Twitterのt.co短縮を想定）
- 箇条書きは `・` または `-` で統一
- ハッシュタグ間はスペース区切り
- `{URL}` はプレースホルダーのままにする

### Step 6: ハッシュタグ選択

カテゴリ別デフォルトタグ + 記事キーワードで調整:

| カテゴリ | デフォルトハッシュタグ |
|---------|----------------------|
| asset_management | #資産形成 #投資初心者 #新NISA |
| asset_management | #資産形成 #投資初心者 #NISA |
| stock_analysis | #株式投資 #株 #投資 |
| macro_economy | #マクロ経済 #経済 #投資 |
| market_report | #米国株 #週間レポート #投資 |
| quant_analysis | #クオンツ #投資戦略 #データ分析 |
| investment_education | #投資教育 #投資入門 #投資初心者 |
| side_business | #副業 #資産形成 |

記事キーワードに応じた追加タグ（詳細は `guide.md` 参照）。

**beginner の場合**: `#投資初心者` を必ず含む
**advanced の場合**: `#投資初心者` は使わない

### Step 7: 文字数チェックと調整

実際に文字数をカウントする（`{URL}` は23字として計算）。

**280字超の場合の削減優先順位:**
1. 箇条書きの説明を短縮
2. 箇条書きを3点→2点に削減
3. フックの文章を短縮
4. ハッシュタグを1-2個削減（ただし最低3個は残す）

### Step 8: ファイル出力

`02_draft/x_post.md` を出力:

```markdown
---
article_id: {meta.yamlのarticle_id}
category: {meta.yamlのcategory}
audience: {beginner|intermediate|advanced}
platform: x
hook_pattern: {A|B|C|D}
char_limit: 280
char_count: {実際の文字数（URLを23字計算）}
status: draft
reference_used: [{使用したサンプルのファイルパス, 空なら[]}]
---

{投稿本文}
```

既存の `x_post.md` がある場合は上書きではなく内容を確認し、
ユーザーに「既存ファイルを上書きしますか？」と確認する。

## 完了報告

```
## X投稿文を生成しました

- **文字数**: {char_count}字 / 280字
- **カテゴリ**: {category}
- **ターゲット層**: {audience}
- **書き出しパターン**: {A/B/C/D型}
- **ハッシュタグ**: {tags}
- **参照サンプル**: {reference_used または「なし（--no-ref）」}
- **出力ファイル**: {article_dir}/02_draft/x_post.md

投稿前に `{URL}` を実際のnote記事URLに置き換えてください。
```

## 関連ファイル

| ファイル | 用途 |
|---------|------|
| `templates/hook-patterns.md` | 4パターン×3層の文型と例文 |
| `templates/beginner.md` | beginner向け詳細テンプレート |
| `templates/intermediate.md` | intermediate向け詳細テンプレート |
| `templates/advanced.md` | advanced向け詳細テンプレート |
| `references/README.md` | ライブラリ運用ルール |
| `references/index.yaml` | サンプル検索インデックス |
| `guide.md` | 詳細ルール（ハッシュタグ辞書・禁止表現・層別差分） |
