# x-post-generator スキル高度化プラン

## Context

現在の `x-post-generator` スキルは単一の SKILL.md のみで構成されており、書き出し3パターン（A逆説・B疑問形・C数字）とカテゴリ別ハッシュタグ辞書を提供している。

高度化の目的：
1. **ターゲット層別投稿** — `meta.yaml` の `target_audience`（beginner/intermediate/advanced）に応じて文体・フック・ハッシュタグを自動切り替える
2. **参照ライブラリ** — 優良投稿サンプルを `references/` に蓄積し、生成時に類似サンプルをヒントとして活用することで品質を継続的に向上させる
3. **ディレクトリ構造の整備** — 他スキル（`coding-standards/`, `finance-news-workflow/`）に倣い、templates/ と references/ サブディレクトリを構築する

---

## 完成後のディレクトリ構造

```
.claude/skills/x-post-generator/
├── SKILL.md                    ← 大幅改訂
├── guide.md                    ← 新規（詳細ルールのオフロード）
│
├── templates/
│   ├── beginner.md             ← 初心者向け文体・構成ルール
│   ├── intermediate.md         ← 中級者向け文体・構成ルール
│   ├── advanced.md             ← 上級者向け文体・構成ルール
│   └── hook-patterns.md        ← 4パターン×3層 = 12パターン対応表
│
└── references/
    ├── README.md               ← ライブラリ運用ルール・追加方法
    ├── index.yaml              ← 全サンプルのインデックス（検索用）
    ├── asset_management/
    │   ├── beginner-ideco-hook-C.md
    │   ├── beginner-fund-age-hook-B.md
    │   └── intermediate-index-hook-B.md
    ├── asset_management/
    │   └── beginner-behavior-hook-A.md
    ├── macro_economy/
    │   ├── intermediate-boj-hook-D.md         ← 新規サンプル
    │   └── intermediate-oil-hook-C.md         ← 新規サンプル
    └── stock_analysis/
        └── intermediate-dividend-hook-B.md    ← 新規サンプル
```

---

## 変更ファイル一覧

| ファイル | 操作 | 概要 |
|---------|------|------|
| `SKILL.md` | 改訂 | Step 0 追加・参照ライブラリフロー・4パターン・出力フロントマター拡張 |
| `guide.md` | 新規 | SKILL.md からオフロードした詳細ルール（層別差分・禁止表現など） |
| `templates/beginner.md` | 新規 | beginner 専用テンプレート |
| `templates/intermediate.md` | 新規 | intermediate 専用テンプレート |
| `templates/advanced.md` | 新規 | advanced 専用テンプレート |
| `templates/hook-patterns.md` | 新規 | 4パターン×3層 = 12パターンの文型と例文 |
| `references/README.md` | 新規 | ライブラリ運用ルール（追加条件・更新契機・削除条件） |
| `references/index.yaml` | 新規 | 全サンプルの検索インデックス |
| `references/asset_management/beginner-ideco-hook-C.md` | 新規 | 既存 x_post.md から移植（iDeCo記事） |
| `references/asset_management/beginner-fund-age-hook-B.md` | 新規 | 既存 x_post.md から移植（ファンド年齢別） |
| `references/asset_management/intermediate-index-hook-B.md` | 新規 | 既存 x_post.md から移植（インデックス投資） |
| `references/asset_management/beginner-behavior-hook-A.md` | 新規 | 既存 x_post.md から移植（投資心理学） |
| `references/macro_economy/intermediate-boj-hook-D.md` | 新規 | 新規サンプル（日銀・マクロ） |
| `references/macro_economy/intermediate-oil-hook-C.md` | 新規 | 新規サンプル（原油・家計） |
| `references/stock_analysis/intermediate-dividend-hook-B.md` | 新規 | 新規サンプル（高配当株） |

---

## SKILL.md 改訂の設計

### 新パラメータ

| パラメータ | デフォルト | 説明 |
|-----------|----------|------|
| `@article_dir` | 文脈から推測 | 記事ディレクトリ |
| `--audience` | `meta.yaml` の `target_audience` | `beginner` / `intermediate` / `advanced` |
| `--hook` | フック推奨マトリックスから自動決定 | `A`（逆説）/ `B`（疑問形）/ `C`（数字）/ `D`（宣言 ← 新規追加） |
| `--ref` | 自動検索 | 特定参照ファイルを直接指定 |
| `--no-ref` | false | 参照ライブラリをスキップして高速生成 |

### 新規 Step 0: パラメータ解決

`--audience` 未指定 → `meta.yaml` の `target_audience` → デフォルト `intermediate`
`--hook` 未指定 → 下記マトリックスから自動決定

### フック推奨マトリックス

| category | beginner | intermediate | advanced |
|---------|---------|-------------|---------|
| asset_management | C | B | B |
| asset_management | A | B | A |
| macro_economy | C | D | A |
| stock_analysis | B | B | D |
| market_report | C | D | — |
| side_business | B | B | — |
| quant_analysis | C | C | D |

### 新規 Step 2: 参照ライブラリ検索（`--no-ref` がない場合）

1. `references/index.yaml` を読む
2. `category + audience + hook_pattern` で最大2件のサンプルを特定
3. サンプルファイルを読み込み、`why_it_works` フィールドをヒントとして保持
4. 0件の場合はスキップ（フォールバック: 参照なしで通常生成）

### 出力フロントマターの拡張

```yaml
---
article_id: {article_id}
category: {category}
audience: {beginner|intermediate|advanced}   ← 追加
platform: x
hook_pattern: {A|B|C|D}                      ← D追加
char_limit: 280
char_count: {文字数}
status: draft
reference_used: [{ファイルパス}]              ← 追加（参照したサンプル）
---
```

---

## 参照ライブラリのファイルフォーマット

```yaml
---
sample_id: {category}-{audience}-{keyword}-hook-{pattern}-001
category: {category}
audience: {beginner|intermediate|advanced}
hook_pattern: {A|B|C|D}
engagement_score: null       # 実績エンゲージメント（後から追記）
impressions: null
posted_at: null
note_url: null
why_it_works: >
  {なぜこの投稿が刺さるかの解説（生成時のヒントになる）}
tags: [{キーワード1}, {キーワード2}]
created_at: "YYYY-MM-DD"
source_article: {articles/...}
---

# 本文

{投稿テキスト}
```

---

## 層別テンプレートの主な差分

| 次元 | beginner | intermediate | advanced |
|------|---------|-------------|---------|
| 専門用語 | 禁止（使う場合は括弧解説必須） | 適度に使用 | 積極使用、解説省略 |
| 感情軸 | 共感・安心・「自分でもできる」 | 好奇心・「損してた」 | 反論・逆張り |
| 絵文字 | 積極使用（✅💡📊） | 節度（1-2個） | 原則なし |
| CTA 語尾 | 「〜しました！」（感嘆符OK） | 「〜しました。」 | 「〜を検証しました。」 |
| ハッシュタグ数 | 4-5個 | 3-4個 | 3個 |
| 文字数の目安 | 180-230字 | 220-270字 | 230-280字 |

---

## 実装順序

1. `templates/hook-patterns.md` — 12パターン対応表（SKILL.md 改訂の前提知識）
2. `templates/beginner.md` / `intermediate.md` / `advanced.md`
3. `references/README.md` — 運用ルール
4. `references/index.yaml` — インデックス（既存4件 + 新規3件）
5. `references/{category}/` — 個別サンプルファイル（既存4件の移植 + 新規3件）
6. `SKILL.md` 改訂 — Step 0 / Step 2 追加、パラメータ拡張、出力フォーマット拡張
7. `guide.md` — SKILL.md から詳細ルールをオフロード

---

## 動作確認

実装後は以下で動作を確認する:

```bash
# 1. beginner × C数字型（既存記事で動作確認）
# → meta.yaml の target_audience = beginner を読んで自動決定されることを確認

# 2. intermediate × 参照ライブラリ使用
/x-post @articles/asset_management/2026-03-06_index-investing-portfolio/ --audience intermediate
# → references/index.yaml → intermediate-index-hook-B.md が参照されることを確認

# 3. --hook 強制指定
/x-post @articles/... --audience beginner --hook D
# → D宣言型フックで生成されることを確認

# 4. --no-ref モード（高速生成）
/x-post @articles/... --no-ref
# → 参照ライブラリをスキップして生成されることを確認

# 5. x_post.md のフロントマターに audience, hook_pattern, reference_used が追記されることを確認
```
