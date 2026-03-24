# KG Quality Report

**Timestamp**: 2026-03-24T06:03:16.944451+00:00
**Overall Score**: 61.4 / 100.0
**Rating**: B

## Categories

| Category | Score | Rating |
|----------|------:|--------|
| structural | 80.0 | A |
| completeness | 50.0 | C |
| consistency | 50.0 | C |
| accuracy | 50.0 | C |
| timeliness | 66.7 | B |
| finance_specific | 66.7 | B |
| discoverability | 66.7 | B |

### structural

| Metric | Value | Unit | Status |
|--------|------:|------|--------|
| Edge Density | 0.000949 | ratio | red |
| Avg Degree | 15.01 | count | green |
| Connected Ratio | 0.9986 | ratio | green |
| Orphan Ratio | 0.0014 | ratio | green |
| Orphan Entity Count | 0.0 | count | green |

### completeness

| Metric | Value | Unit | Status |
|--------|------:|------|--------|
| Required Property Coverage | 0.8537 | ratio | yellow |

### consistency

| Metric | Value | Unit | Status |
|--------|------:|------|--------|
| Type Consistency | 0.8904 | ratio | yellow |
| Dedup Score | 0.973 | ratio | green |
| Constraint Violations | 34.0 | count | red |

### accuracy

| Metric | Value | Unit | Status |
|--------|------:|------|--------|
| Factual Correctness | 0.5 | ratio | yellow |
| Source Grounding | 0.5 | ratio | yellow |
| Temporal Validity | 0.5 | ratio | yellow |

### timeliness

| Metric | Value | Unit | Status |
|--------|------:|------|--------|
| Avg Freshness (days) | 119.1 | days | red |
| Recent Sources (30d) | 117.0 | count | green |
| Coverage Span (days) | 3661 | days | green |

### finance_specific

| Metric | Value | Unit | Status |
|--------|------:|------|--------|
| Sector Coverage | 1.0 | ratio | green |
| Metrics/Company | 2.07 | count | red |
| Entity-Entity Density | 4.1925 | ratio | green |

### discoverability

| Metric | Value | Unit | Status |
|--------|------:|------|--------|
| Avg Path Length | 3.89 | hops | green |
| Path Diversity | 0.035 | ratio | red |
| Bridge Rate | 1.0 | ratio | green |

## CheckRules

| Rule | Pass Rate | Violations |
|------|----------:|-----------:|
| subject_reference | 98.40% | 8 |
| entity_length | 92.89% | 72 |
| schema_compliance | 89.04% | 111 |
| relationship_compliance | 66.67% | 19 |

**subject_reference violations** (sample):
- `This is a comparison of Wednesday's Federal Open Market Committee statement with`
- `These are some of the stocks posting the largest moves midday.`
- `This week's meeting offers little suspense and probably not much action, even as`
- `These are the stocks posting the largest moves in extended trading.`
- `These are the stocks posting the largest moves before the bell.`

**entity_length violations** (sample):
- `TOPIX連動型上場投資信託`
- `日経高配当株50 ETF`
- `Fidelity MSCI Real Estate Index ETF`
- `First Trust Global Tactical Commodity Strategy Fund`
- `Ministry of Internal Affairs and Communications`

**schema_compliance violations** (sample):
- `article_proposal`
- `article_proposal`
- `article_proposal`
- `article_proposal`
- `article_proposal`

**relationship_compliance violations** (sample):
- `FROM_DOMAIN`
- `INGESTED_VIA`
- `RATED_AS`
- `IS_SOURCE_TYPE`
- `IN_LANGUAGE`

## Entropy / Semantic Diversity

| Axis | Value |
|------|------:|
| entity_type_entropy | 0.6671 |
| topic_category_entropy | 0.8186 |
| relationship_type_entropy | 0.6673 |
| semantic_diversity | 0.7177 |

## 総合評価

総合スコア **61.4** / 100.0 — レーティング **B**

> 良好: 改善の余地はありますが、実用レベルです。
