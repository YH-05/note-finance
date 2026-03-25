# Project 25: research-enrichment スキル開発

## 概要

research-neo4j (bolt://localhost:7688) の知識ギャップを体系的に埋める自動拡充ループスキル。
4軸統合スコア（カテゴリバランス/Entity空洞/鮮度/財務データ）でターゲットを選定し、
動的ソース選択（Tavily/SEC EDGAR/alphaxiv/Reddit/Wikipedia）で収集、
LLM が web-research 入力 JSON を直接生成、
entity_linker.py → emit_research_queue.py → /save-to-research-graph の3段パイプラインで投入する。

## メタ情報

| 項目 | 値 |
|------|-----|
| GitHub Project | [#102](https://github.com/users/YH-05/projects/102) |
| タイプ | skill |
| 開始日 | 2026-03-25 |
| ステータス | Planning Complete |

## Issue 一覧

| # | Issue | Wave | 依存 | ステータス |
|---|-------|------|------|----------|
| 1 | [#252](https://github.com/YH-05/note-finance/issues/252) Config ファイル作成 | Wave 1 | なし | Todo |
| 2 | [#253](https://github.com/YH-05/note-finance/issues/253) Gap 分析 Cypher クエリ集 | Wave 2 | #252 | Todo |
| 3 | [#254](https://github.com/YH-05/note-finance/issues/254) 検索戦略リファレンス | Wave 2 | #252 | Todo |
| 4 | [#255](https://github.com/YH-05/note-finance/issues/255) Transform プロンプト | Wave 2 | #252, #253, #254 | Todo |
| 5 | [#256](https://github.com/YH-05/note-finance/issues/256) SKILL.md メイン | Wave 3 | #252-#255 | Todo |
| 6 | [#257](https://github.com/YH-05/note-finance/issues/257) スラッシュコマンド | Wave 4 | #256 | Todo |

## Wave 構成

```
Wave 1: [#252] Config
Wave 2: [#253] Gap Queries  [#254] Search Strategy  [#255] Transform Prompt
Wave 3: [#256] SKILL.md
Wave 4: [#257] Command
```

## 依存グラフ

```
#252 ─┬─→ #253 ─┐
      ├─→ #254 ─┼─→ #255 ─→ #256 ─→ #257
      └─────────┘
```

## Critical リスク

1. **entity_linker.py --instance 省略禁止**: デフォルト `creator` で creator-neo4j に誤接続。`--instance research --v3` を必ず明示。
2. **authority_level 必須**: emit_research_queue.py が KeyError でクラッシュ。transform-prompt.md で強調。

## 参照

- テンプレート: `.claude/skills/creator-enrichment/SKILL.md`
- 元プランファイル: `docs/project/project-25/original-plan.md`
- 設計議論: `docs/plan/SideBusiness/2026-03-24_discussion-research-enrichment-design.md` 他2件
