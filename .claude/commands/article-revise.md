---
description: revised_draft.md にフィードバックを反映して記事を更新します。
argument-hint: @<article_dir> "フィードバック内容" [--diff]
---

revised_draft.md にユーザーのフィードバックを反映して記事を更新します。

## スキル参照

`.claude/skills/article-revise/SKILL.md` を読み込み、処理フローに従って実行すること。

## 入力パラメータ

| パラメータ | 必須 | デフォルト | 説明 |
|-----------|------|-----------|------|
| @article_dir | ○ | - | 記事ディレクトリのパス |
| feedback | ○ | - | ユーザーのフィードバック（引用符で囲む） |
| --diff | - | false | セクション単位の詳細 before/after を表示 |

## 引数の解釈ルール

共通パス解決ロジックに従う。詳細は `.claude/commands/_shared/path-resolution.md` を参照。

```
/article-revise @articles/stock_analysis/2026-03-28_xxx/ "もっと具体例を増やして"
/article-revise @articles/macro_economy/2026-03-25_fed/ --diff "導入を短くして"
```

## 実行手順

1. `.claude/skills/article-revise/SKILL.md` を読み込む
2. Step 1〜4 を順番に実行する
3. 完了報告を表示する
