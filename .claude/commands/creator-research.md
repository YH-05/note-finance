---
description: 特定トピックをマルチソースで深掘りリサーチし、creator-neo4j に投入する
---

# Creator Research

`creator-research` スキルを実行します。

特定のトピックについてマルチソースで深掘りリサーチし、
Fact/Tip/Story/Entity/Concept を抽出して creator-neo4j（bolt://localhost:7689）に永続化します。

## 使い方

```
/creator-research --topic "副業ブログ収益化" --genre career --depth standard
/creator-research --topic "マッチングアプリ 成功率" --genre beauty-romance
/creator-research --topic "タロット副業" --genre spiritual --depth deep
/creator-research --topic "フリーランス エンジニア" --dry-run
/creator-research --topic "婚活 体験談" --skip-kg
```

## パラメータ

| パラメータ | 必須 | デフォルト | 説明 |
|-----------|------|-----------|------|
| `--topic` | 必須 | - | リサーチトピック |
| `--genre` | 推奨 | auto | `career` / `beauty-romance` / `spiritual` |
| `--depth` | - | standard | `quick`(5-8検索) / `standard`(12-18) / `deep`(20-30) |
| `--dry-run` | - | false | 検索・抽出のみ。投入をスキップ |
| `--skip-kg` | - | false | creator-neo4j 未起動時に使用 |

## 処理フロー

```
Phase 0: creator-neo4j 既存データ照会 + ギャップ分析
Phase 1: マルチソース検索（Tavily/WebSearch/WebFetch/Reddit）
Phase 2: Fact/Tip/Story/Entity/Concept 抽出
Phase 3: サイクル入力 JSON 構築
Phase 4: emit_creator_queue_v2.py → /save-to-creator-graph 投入
Phase 5: 結果レポート
```

## creator-enrichment との違い

| | creator-research | creator-enrichment |
|--|---------|---------|
| 実行形式 | 単発（1回で完了） | 時間ループ（`--until` まで継続） |
| トピック指定 | `--topic` で明示指定 | ギャップ分析でトピック自動選択 |
| ジャンル | `--genre` で指定（auto判定あり） | ローテーション |
| 深度 | `--depth` で制御 | サイクル毎に固定 |
| 用途 | 特定トピックの一点深掘り | 全体的な拡充 |

## 出力ファイル

- `.tmp/creator-research-{slug}_{timestamp}.gap.md` — ギャップ分析結果
- `.tmp/creator-research-{slug}_{timestamp}.input.json` — パイプライン入力 JSON
- `.tmp/creator-research-{slug}_{timestamp}.md` — 結果レポート

---

$ARGUMENTS

スキルを読み込んで実行してください:

```
Read .claude/skills/creator-research/SKILL.md
```

上記スキルの指示に従って、指定されたパラメータでリサーチを実行してください。
