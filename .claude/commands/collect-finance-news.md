---
description: 金融ニュースを RSS から収集し GitHub Project に投稿
skill-preload: finance-news-workflow
---

# /collect-finance-news - 金融ニュース収集

> **スキル参照**: `.claude/skills/finance-news-workflow/SKILL.md`
>
> **注意**: このコマンドは Python CLI ベースのニュース収集を実行します。
> 簡易版は `/article-research` も参照してください。

RSS フィードから金融ニュースを収集し、AI 要約して GitHub Project #15 に Issue として投稿します。

## 使用例

```bash
# 全カテゴリを収集
/collect-finance-news

# ドライラン（GitHub投稿をスキップ）
/collect-finance-news --dry-run

# 特定カテゴリのみ
/collect-finance-news --status index,macro

# 記事数を制限
/collect-finance-news --max-articles 10
```

## カテゴリ

| カテゴリ | 説明 |
|---------|------|
| `index` | 株価指数 |
| `stock` | 個別銘柄 |
| `sector` | セクター |
| `macro` | マクロ経済 |
| `ai` | AI 関連 |
| `finance` | 金融・政策 |

## 処理フロー

```
RSS収集 → 本文抽出 → AI要約 → カテゴリ分類 → GitHub Issue投稿
```
