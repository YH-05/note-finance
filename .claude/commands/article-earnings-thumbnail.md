---
description: 決算記事のnote.comサムネイル（1280×670 PNG）を自動生成します。
argument-hint: @<article_dir>
---

決算記事（`category: earnings`）のサムネイル画像を自動生成します。Wikidata P154 経由で企業ロゴを取得し、Pencilテンプレ「Thumbnail - 決算」に埋め込んだ PNG を `{article_dir}/images/thumbnail.png` に出力します。

## スキル参照

`.claude/skills/article-earnings-thumbnail/SKILL.md` を読み込み、処理フロー Step 1〜5 に従って実行すること。

## 入力パラメータ

| パラメータ | 必須 | 説明 |
|-----------|------|------|
| `@article_dir` | ○ | 決算記事ディレクトリ（例: `@articles/earnings/2026-04-15_nflx-q1-2026-earnings-preview/`） |

## 引数の解釈ルール

共通パス解決ロジックに従う。詳細は `.claude/commands/_shared/path-resolution.md` を参照。

```
/article-earnings-thumbnail @articles/earnings/2026-04-15_nflx-q1-2026-earnings-preview/
/article-earnings-thumbnail @articles/earnings/2026-04-22_ibm-q1-2026-earnings-preview/
```

## 前提条件

- `meta.yaml` の `category` が `earnings` である
- `meta.yaml` に `symbols[0]`（ティッカー）、`earnings_date`、`type`（`earnings_preview` または `earnings_review`）が設定されている
- Pencil ファイル `/Users/yukihata/Desktop/new.pen` が存在し、`Thumbnail - 決算` フレーム（nodeId=`CAXCU`）を含む

## 実行手順

1. `.claude/skills/article-earnings-thumbnail/SKILL.md` を読み込む
2. meta.yaml をバリデーション（`category=earnings` 以外はスキップ）
3. `uv run python scripts/fetch_company_logo.py --meta-yaml {article_dir}/meta.yaml` を実行
4. Pencil MCP でテンプレ `CAXCU` を上書き → エクスポート → 記事ディレクトリに配置 → テンプレをリセット
5. 完了報告を表示

## 出力例

```
## サムネイル生成完了

ティッカー: NFLX
企業ロゴ: assets/company_logos/NFLX.png (Wikidata P154 経由)
出力先: articles/earnings/2026-04-15_nflx-q1-2026-earnings-preview/images/thumbnail.png
サイズ: 2560×1340 px (scale=2, Retina対応)
```

## 自動発動

以下のコマンドでは、`category: earnings` の記事について revised_draft.md 生成後に本コマンドが自動的に呼び出される:

- `/article-revise`
- `/article-critique`（finance-reviser 経由のリライト後）
