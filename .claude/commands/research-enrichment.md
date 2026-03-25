---
description: research-neo4j の知識ギャップを自動拡充する（ギャップ分析→検索→LLM構造化→パイプライン投入を終了時刻まで繰り返し）
allowed-tools: Read, Write, Bash, Grep, Glob
---

research-neo4j の知識ギャップを自動拡充します。ギャップ分析 → 検索 → LLM 構造化 → パイプライン投入を `--until` 時刻まで繰り返します。

パラメータ: $ARGUMENTS

**--until は必須パラメータです。** 終了時刻を HH:MM 形式（24時間制）で指定してください。

## 使用例

```
/research-enrichment --until 23:30
/research-enrichment --until 20:00 --focus-entity amd::company
/research-enrichment --until 15:00 --dry-run
/research-enrichment --until 22:00 --focus-entity nvidia::company --dry-run
```

## パラメータ一覧

| パラメータ | 必須 | 説明 | 例 |
|-----------|------|------|----|
| `--until` | **必須** | 終了時刻（HH:MM 形式、24時間制） | `--until 23:30` |
| `--focus-entity` | 任意 | 特定 Entity に絞って拡充（entity_key 形式） | `--focus-entity amd::company` |
| `--dry-run` | 任意 | 検索・構造化のみ実行し投入をスキップ | `--dry-run` |

## スキル読み込みと実行

1. Read `.claude/skills/research-enrichment/SKILL.md`
2. Read `.claude/skills/research-enrichment/references/gap-analysis-queries.md`
3. Read `.claude/skills/research-enrichment/references/search-strategy.md`
4. Read `.claude/skills/research-enrichment/references/transform-prompt.md`
5. SKILL.md の手順に従い Phase 0 から実行開始
