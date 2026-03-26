# Deterministic Backfill Guide

`research-neo4j` の既存データだけから一意に導ける補完だけを実行するガイド。

## Scope

対象 stage:

- `domains`: `Source.domain` と `(:Source)-[:FROM_DOMAIN]->(:Domain)`
- `facts`: `Fact.source_url` と `Fact.as_of_date`
- `claims`: `(:Claim)-[:ABOUT]->(:Entity)`
- `insights`: `(:Insight)-[:ABOUT]->(:Entity)`

対象外:

- `Topic <-[:BELONGS_TO]- Entity`
- `Fact -> Topic TAGGED`
- `Insight -> DERIVED_FROM`
- 新規 `Entity` 作成
- `Source.publisher`
- `FinancialDataPoint -> Metric / Entity / FiscalPeriod`

## Command

Dry-run:

```bash
uv run python scripts/backfill_deterministic_research_gaps.py --dry-run
```

段階実行:

```bash
uv run python scripts/backfill_deterministic_research_gaps.py --stage domains
uv run python scripts/backfill_deterministic_research_gaps.py --stage facts
uv run python scripts/backfill_deterministic_research_gaps.py --stage claims
uv run python scripts/backfill_deterministic_research_gaps.py --stage insights
```

件数を絞る:

```bash
uv run python scripts/backfill_deterministic_research_gaps.py --stage all --limit 100
```

## Recommended Order

1. `--dry-run --stage all`
2. `--stage domains`
3. `--stage facts`
4. `--stage claims`
5. `--stage insights`

`facts` は `Source` 側の日付・URLに依存するため、`domains` の後に回す。

## Deterministic Rules

### `domains`

- `Source.url` が `http` で始まる
- `domain` が空、または `FROM_DOMAIN` が未接続
- URL から domain を一意に抽出できる

### `facts`

- `Fact` が `EXTRACTED_FROM` で `Source` 1件にだけ接続
- `Fact.source_url` が空なら `Source.url` を継承
- `Fact.as_of_date` が空なら `published_at -> published_date -> filing_date` の優先順で継承
- 複数 `Source` に接続している `Fact` は補完しない

### `claims`

- `(Claim)-[:SUPPORTED_BY]->(Fact)-[:RELATES_TO]->(Entity)` がある
- 既に同じ `ABOUT` があれば追加しない

### `insights`

- `Insight` に `ABOUT` がない
- `DERIVED_FROM` の先から辿れる `Entity` がちょうど1件
- `Fact/Claim` は `ABOUT` と `RELATES_TO` を許可
- `Source` は `ABOUT` のみ許可
- 0件または複数件に分岐する場合は補完しない

## Validation Queries

`Source` の未接続確認:

```cypher
MATCH (s:Source)
WHERE s.url STARTS WITH 'http'
  AND (
    coalesce(s.domain, '') = ''
    OR NOT EXISTS { MATCH (s)-[:FROM_DOMAIN]->(:Domain) }
  )
RETURN count(s) AS remaining_sources;
```

`Fact` の URL / 日付欠損確認:

```cypher
MATCH (f:Fact)
RETURN
  count { CASE WHEN coalesce(f.source_url, '') = '' THEN 1 END } AS missing_source_url,
  count { CASE WHEN coalesce(f.as_of_date, '') = '' THEN 1 END } AS missing_as_of_date;
```

`Claim` の `ABOUT` 欠損確認:

```cypher
MATCH (c:Claim)
WHERE NOT EXISTS { MATCH (c)-[:ABOUT]->(:Entity) }
RETURN count(c) AS claims_without_about;
```

`Insight` の `ABOUT` 欠損確認:

```cypher
MATCH (i:Insight)
WHERE NOT EXISTS { MATCH (i)-[:ABOUT]->(:Entity) }
RETURN count(i) AS insights_without_about;
```

## Related Scripts

- `scripts/normalize_source_chain.py`: Source 系の正規化
- `scripts/backfill_temporal_chain.py`: 時系列リレーション補完
- `scripts/apply_metric_master.py`: `FinancialDataPoint -> Metric` 正規化
