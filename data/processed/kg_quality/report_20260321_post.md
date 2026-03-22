# KG Quality Report

**Timestamp**: 2026-03-21T12:03:34.613554+00:00
**Overall Score**: 51.8 / 100.0
**Rating**: C

## Categories

| Category | Score | Rating |
|----------|------:|--------|
| structural | 62.5 | B |
| completeness | 50.0 | C |
| consistency | 33.3 | D |
| accuracy | 50.0 | C |
| timeliness | 66.7 | B |
| finance_specific | 66.7 | B |
| discoverability | 33.3 | D |

### structural

| Metric | Value | Unit | Status |
|--------|------:|------|--------|
| Edge Density | 0.000765 | ratio | red |
| Avg Degree | 11.31 | count | green |
| Connected Ratio | 0.7482 | ratio | yellow |
| Orphan Ratio | 0.0476 | ratio | green |

### completeness

| Metric | Value | Unit | Status |
|--------|------:|------|--------|
| Required Property Coverage | 0.8386 | ratio | yellow |

### consistency

| Metric | Value | Unit | Status |
|--------|------:|------|--------|
| Type Consistency | 0.8839 | ratio | yellow |
| Dedup Score | 0.9339 | ratio | yellow |
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
| Avg Freshness (days) | 1.9 | days | green |
| Recent Sources (30d) | 24.0 | count | green |
| Coverage Span (days) | 5 | days | red |

### finance_specific

| Metric | Value | Unit | Status |
|--------|------:|------|--------|
| Sector Coverage | 1.0 | ratio | green |
| Metrics/Company | 1.97 | count | red |
| Entity-Entity Density | 4.1112 | ratio | green |

### discoverability

| Metric | Value | Unit | Status |
|--------|------:|------|--------|
| Avg Path Length | 3.56 | hops | yellow |
| Path Diversity | 0.0642 | ratio | red |
| Bridge Rate | 0.545 | ratio | yellow |

## CheckRules

| Rule | Pass Rate | Violations |
|------|----------:|-----------:|
| subject_reference | 98.40% | 8 |
| entity_length | 93.04% | 72 |
| schema_compliance | 88.39% | 120 |
| relationship_compliance | 97.44% | 1 |

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
- `COAUTHORED_WITH`

## Entropy / Semantic Diversity

| Axis | Value |
|------|------:|
| entity_type_entropy | 0.6725 |
| topic_category_entropy | 0.8186 |
| relationship_type_entropy | 0.6007 |
| semantic_diversity | 0.6973 |

## 総合評価

総合スコア **51.8** / 100.0 — レーティング **C**

> 要改善: いくつかのカテゴリで改善が必要です。
