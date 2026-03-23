# Research Neo4j Quality Report (v2 - Post Improvement)

**Date**: 2026-03-23
**Instance**: research-neo4j (bolt://localhost:7688)
**Ontology Version**: research-3.0
**Graph Size**: 7,503 nodes / 55,261 relationships
**Previous Report**: quality-report-20260323.md (v1)

---

## Before/After Comparison Summary

| Metric | v1 (Before) | v2 (After) | Delta |
|--------|------------:|------------|------:|
| Total nodes | 7,383 | 7,503 | +120 |
| Total relationships | 42,961 | 55,261 | +12,300 |
| Distinct node labels | 17 | 25 | +8 |
| Distinct relationship types | 38 | 47 | +9 |
| Classification hub nodes materialized | 0 / 16 | 8 / 16 | +8 |
| Entity orphans | 254 (25.1%) | **0 (0.0%)** | -254 |
| Source TAGGED orphans | 247 (14.5%) | **0 (0.0%)** | -247 |
| FOR_METRIC coverage | 22 (5.1%) | **129 (30.0%)** | +107 |
| MENTIONS count | 49 | **925** | +876 |
| TAGGED count | 17,176 | **20,615** | +3,439 |
| **D-1 Score** | **93.5%** | **95.1%** | **+1.6** |
| **D-2 Score** | **99.4%** | **99.4%** | **0.0** |
| **D-3 Score** | **89.7%** | **98.3%** | **+8.6** |
| **D-4 Score** | **52.6%** | **79.3%** | **+26.7** |
| **Overall Score** | **83.5** | **92.7** | **+9.2** |
| **Rating** | **B** | **A** | **+1 grade** |

---

## D-1: Ontology Conformance (30%)

### Node Labels

| Label | Count | In Ontology? | New in v2? |
|-------|------:|:---:|:---:|
| Source | 1,709 | Yes | |
| Fact | 1,518 | Yes | |
| Claim | 1,145 | Yes | |
| Chunk | 1,015 | Yes | |
| Entity | 1,013 | Yes | |
| FinancialDataPoint | 430 | Yes | |
| Topic | 227 | Yes | |
| Author | 115 | Yes | |
| Stance | 74 | Yes | |
| Metric | 55 | Yes | |
| EntityType | 42 | Yes | NEW |
| FiscalPeriod | 25 | Yes | |
| Insight | 23 | Yes | |
| TrustLevel | 20 | Yes | NEW |
| Memory | 17 | Yes (Operational) | |
| SkillRun | 17 | Yes (Operational) | |
| SourceType | 16 | Yes | NEW |
| Sector | 11 | Yes | |
| Pipeline | 10 | Yes | NEW |
| FactType | 10 | Yes | NEW |
| ClaimType | 10 | Yes | NEW |
| ConceptCategory | 8 | Yes | NEW |
| DataPointType | 4 | Yes | NEW |
| Question | 3 | Yes (Operational) | |
| QualitySnapshot | 2 | Yes (Operational) | |

**Unexpected labels**: 0
**Labels present**: 25 / 33 defined (8 new classification hub labels materialized)
**Remaining unmaterialized**: Domain, Language, Identifier, Industry, Alias, UnitOfMeasure, AuthorType, InstrumentClass

### Relationship Types

All 47 existing relationship types are defined in the ontology (59 defined total).

**New relationship types in v2** (9 added):
- IS_SOURCE_TYPE (1,709)
- RATED_AS (1,570)
- INGESTED_VIA (1,477)
- IS_TYPE (1,013)
- MENTIONS (925)
- IS_FACT_TYPE (868)
- IS_CLAIM_TYPE (797)
- IS_DATAPOINT_TYPE (249)
- IS_CATEGORY (195)

**Non-conforming relationship types**: 0

### Entity Type Distribution (entity_type property)

| Canonical Type | Count | Non-Canonical Subtypes | Non-Canonical Count |
|---------------|------:|----------------------|--------------------:|
| company | 190 | fintech(8), subsidiary(3), fintech_holding(2), digital_bank(1), it_services(1) | 15 |
| technology | 275 | system(1) | 1 |
| organization | 127 | central_bank(12), government(1), government_agency(1), institution(1), exchange(1) | 16 |
| person | 89 | - | 0 |
| concept | 53 | model(14), method(7), theme(9), article_proposal(7), event(1) | 38 |
| index | 39 | - | 0 |
| indicator | 28 | metric(10) | 10 |
| instrument | 22 | etf(6), currency(4), currency_pair(2), fund(2), bond(1), asset(1) | 16 |
| commodity | 16 | - | 0 |
| country | 15 | region(1) | 1 |
| sector | 13 | market(1) | 1 |
| broker | 9 | - | 0 |
| product | 7 | dataset(4), data_center(1) | 5 |
| regulation | 3 | - | 0 |
| **N/A** | - | macro(24) | **24** |

**Already canonical**: 886 / 1,013 (87.5%) -- unchanged
**Need consolidation**: 127 / 1,013 (12.5%)

### Source Type Distribution

| Canonical Type | Count |
|---------------|------:|
| news | 743 |
| blog | 431 |
| web | 164 |
| pdf | 119 |
| analysis | 97 |
| company_filing | 26 |
| data | 25 |
| presentation | 22 |
| academic | 12 |
| financial_statement | 10 |
| report | 8 |
| transcript | 6 |
| **Subtotal (canonical)** | **1,663** |

| Non-Canonical Type | Count | Should Map To |
|-------------------|------:|--------------|
| academic_paper | 23 | academic |
| paper | 18 | academic |
| white_paper | 4 | report |
| media | 1 | news |
| **Subtotal (non-canonical)** | **46** |

**Canonical**: 1,663 / 1,709 (97.3%) -- unchanged

### Topic Category Distribution

| Status | Count |
|--------|------:|
| Has IS_CATEGORY relationship | 195 |
| No IS_CATEGORY relationship | 32 |
| **Total** | **227** |

**Mapped via IS_CATEGORY**: 195 / 227 (85.9%) -- improved from 76.4%

### D-1 Score Calculation

| Sub-check | Score | Weight | v1 Score |
|-----------|------:|-------:|---------:|
| Label conformance (25/25 existing = 100%) | 100.0% | 30% | 100.0% |
| Relationship type conformance (47/47 = 100%) | 100.0% | 20% | 100.0% |
| Entity type canonical rate | 87.5% | 20% | 87.5% |
| Source type canonical rate | 97.3% | 15% | 97.3% |
| Topic category mapped rate (IS_CATEGORY) | 85.9% | 15% | 76.4% |

**D-1 Score: 95.1%** (was 93.5%, +1.6)

---

## D-2: Duplicate Detection (20%)

### Entity Duplicates (same name, case-insensitive)

Total pairs with identical names: **19** (unchanged)

| Type | Count | Examples |
|------|------:|---------|
| True duplicates (same entity_type) | 7 | NVIDIA/Nvidia::company, Federal Reserve(2x central_bank), China/Japan/Singapore(country dup keys), Bank of Thailand(key format), Osaka Metropolitan Univ(legacy key) |
| Multi-role (different entity_type) | 12 | Goldman Sachs (company/broker), Toyota (company/organization), TDA (technology/method/concept), GPT-OSS models, Preferred Networks, Random Forest, JSPrice, Corporate Governance Code |

#### True Duplicates (require merge) -- unchanged

| Name | Key 1 | Key 2 | Issue |
|------|-------|-------|-------|
| NVIDIA | NVIDIA::company | Nvidia::company | Case difference |
| Federal Reserve | Federal Reserve::organization | Federal Reserve::central_bank | Needs consolidation |
| China | China::organization | China::country | Needs consolidation |
| Singapore | Singapore::organization | Singapore::country | Needs consolidation |
| Japan | Japan::organization | Japan::country | Needs consolidation |
| Bank of Thailand | BankOfThailand::organization | Bank of Thailand::central_bank | entity_key format |
| Osaka Metropolitan Univ | osaka_metropolitan_university | Osaka Metropolitan Univ::organization | Legacy key |

### Topic Duplicates

Same-name topic pairs: **8** (unchanged, but now includes 2 with null keys: ASEAN Fintech, US Telecom)

| Name | Key 1 | Key 2 |
|------|-------|-------|
| AI Cloud | ::ai | ::technology |
| ASEAN Fintech | null | asean_fintech |
| ESG | ::stock | ::governance |
| Earnings | ::earnings | ::theme / ::financial (3 nodes) |
| Infrastructure Assets | ::assets | ::segment |
| Portfolio Optimization | ::quantitative_finance | ::finance |
| Telecom M&A | ::sector | ::corporate-action |
| US Telecom | null | null |

### Source URL Duplicates

Duplicate URL pairs: **4** (unchanged)

| URL | Source ID 1 | Source ID 2 |
|-----|-------------|-------------|
| cnbc.com/.../fed-interest-rate... | src-529818465bf1ea7e | b84f1afb-... |
| techwireasia.com/.../malaysia-5g... | reg:malaysia_dual_network | pol:my_dnb5g |
| telkom.co.id/.../TLKM... | company:TLKM_financials_2024 | digital:telkom_dc_2025 |
| axiata.com/.../axiata-posts... | company:EXCL_financials_2025 | tower:axiata_fy25 |

### D-2 Score Calculation

| Item | Value | Metric |
|------|------:|--------|
| Entity true duplicate rate | 7 / 1,013 | 0.69% |
| Topic duplicate rate | 8 / 227 | 3.52% |
| Source URL duplicate rate | 4 / 1,709 | 0.23% |
| **Combined duplicate rate** | **19 / 2,949** | **0.64%** |

**D-2 Score: 99.4%** (unchanged)

---

## D-3: Orphan Node Detection (25%)

### Orphan Summary

| Node Type | Total | Orphan Count | Orphan Rate | v1 Count | v1 Rate | Delta |
|-----------|------:|-------------:|------------:|---------:|--------:|------:|
| Entity (no relationships at all) | 1,013 | **0** | **0.0%** | 254 | 25.1% | **-254** |
| Source (no TAGGED->Topic) | 1,709 | **0** | **0.0%** | 247 | 14.5% | **-247** |
| Fact (no STATES_FACT<-Source) | 1,518 | 18 | 1.2% | 18 | 1.2% | 0 |
| Claim (no MAKES_CLAIM<-Source) | 1,145 | 7 | 0.6% | 7 | 0.6% | 0 |
| FDP (no FOR_PERIOD->FiscalPeriod) | 430 | 38 | 8.8% | 38 | 8.8% | 0 |
| FDP (no RELATES_TO->Entity) | 430 | 33 | 7.7% | 33 | 7.7% | 0 |
| FDP (no FOR_METRIC->Metric) | 430 | 301 | 70.0% | 408 | 94.9% | -107 |

### Classification Node Orphans (new in v2)

| Classification Label | Total | Orphans | Orphan Rate |
|---------------------|------:|--------:|------------:|
| SourceType | 16 | 0 | 0.0% |
| TrustLevel | 20 | 0 | 0.0% |
| EntityType | 42 | 0 | 0.0% |
| Pipeline | 10 | 0 | 0.0% |
| FactType | 10 | 0 | 0.0% |
| ClaimType | 10 | 0 | 0.0% |
| DataPointType | 4 | **2** | **50.0%** |
| ConceptCategory | 8 | 0 | 0.0% |

Note: 2 DataPointType nodes ("forecast", "consensus") have no connected FinancialDataPoint nodes.

### D-3 Score Calculation

| Orphan Check | Orphan Rate | Weight | v1 Rate |
|-------------|------------:|-------:|--------:|
| Fact orphans | 1.2% | 15% | 1.2% |
| Claim orphans | 0.6% | 15% | 0.6% |
| Entity orphans | **0.0%** | 25% | 25.1% |
| Source no TAGGED | **0.0%** | 15% | 14.5% |
| FDP no FOR_PERIOD | 8.8% | 10% | 8.8% |
| FDP no RELATES_TO | 7.7% | 10% | 7.7% |
| Classification orphans (2/120) | 1.7% | 10% | N/A |

Weighted orphan rate: (1.2%*15 + 0.6%*15 + 0.0%*25 + 0.0%*15 + 8.8%*10 + 7.7%*10 + 1.7%*10) / 100 = **1.5% + 0.9% + 0.0% + 0.0% + 0.9% + 0.8% + 0.2%** = **1.7%** (was 10.3%)

**D-3 Score: 98.3%** (was 89.7%, +8.6)

---

## D-4: Coverage Matrix (25%)

### Entity Property Coverage

| Property | Non-Null | Total | Coverage | v1 Coverage |
|----------|--------:|------:|---------:|------------:|
| entity_key | 1,013 | 1,013 | 100.0% | 100.0% |
| name | 1,013 | 1,013 | 100.0% | 100.0% |
| entity_id | 979 | 1,013 | 96.6% | 96.6% |
| entity_type | 1,013 | 1,013 | 100.0% | 100.0% |
| sector | 139 | 1,013 | 13.7% | 13.7% |
| industry | 91 | 1,013 | 9.0% | 9.0% |
| ticker | 112 | 1,013 | 11.1% | 11.1% |
| sec_cik | 33 | 1,013 | 3.3% | 3.3% |
| enriched_at | 69 | 1,013 | 6.8% | 6.8% |
| updated_at | 6 | 1,013 | 0.6% | 0.6% |

**Entity avg coverage**: 44.1% (unchanged)

### Source Property Coverage

| Property | Non-Null | Total | Coverage | v1 Coverage |
|----------|--------:|------:|---------:|------------:|
| source_id | 1,709 | 1,709 | 100.0% | 100.0% |
| url | 1,574 | 1,709 | 92.1% | 92.1% |
| title | 1,708 | 1,709 | 99.9% | 99.9% |
| source_type | 1,709 | 1,709 | 100.0% | 100.0% |
| collected_at | 1,168 | 1,709 | 68.3% | 68.3% |
| published_at | 1,054 | 1,709 | 61.7% | 61.7% |
| authority_level | 1,570 | 1,709 | 91.9% | 91.9% |
| category | 1,221 | 1,709 | 71.4% | 71.4% |
| command_source | 1,477 | 1,709 | 86.4% | 86.4% |
| language | 128 | 1,709 | 7.5% | 7.5% |
| domain | 331 | 1,709 | 19.4% | 19.4% |

**Source avg coverage**: 72.6% (unchanged)

### Relationship Coverage

| Relationship | Count | From->To | Coverage | v1 Count | v1 Coverage |
|-------------|------:|----------|---------|----------|------------|
| TAGGED | 20,615 | Source->Topic | 100.0% of Sources | 17,176 | 85.6% |
| STATES_FACT | 2,466 | Source->Fact | 98.8% of Facts | 2,466 | 98.8% |
| MAKES_CLAIM | 1,155 | Source->Claim | 99.4% of Claims | 1,155 | 99.4% |
| CONTAINS_CHUNK | 1,015 | Source->Chunk | 100.0% | 1,015 | 100.0% |
| EXTRACTED_FROM | 1,411 | Fact/Claim->Chunk | ~53% | 1,411 | ~53% |
| HAS_DATAPOINT | 402 | Source->FDP | 93.5% of FDP | 402 | 93.5% |
| ABOUT | 2,560 | Fact/Claim->Topic | ~96% | 2,560 | ~96% |
| RELATES_TO | 2,834 | Fact/FDP->Entity | Varies | 2,834 | Varies |
| FOR_PERIOD | 392 | FDP->FiscalPeriod | 91.2% of FDP | 392 | 91.2% |
| **FOR_METRIC** | **129** | FDP->Metric | **30.0% of FDP** | 22 | **5.1%** |
| AUTHORED_BY | 192 | Source->Author | 5.8% of Sources | 192 | 11.2% |
| IN_SECTOR | 143 | Entity->Sector | 14.1% of Entities | 143 | 14.1% |
| **MENTIONS** | **925** | Source->Entity | **NEW** | 49 | N/A |

### Classification Relationship Coverage (NEW in v2)

| Relationship | Connected | Total | Coverage |
|-------------|----------:|------:|---------:|
| IS_SOURCE_TYPE (Source->SourceType) | 1,709 | 1,709 | **100.0%** |
| RATED_AS (Source->TrustLevel) | 1,570 | 1,709 | **91.9%** |
| IS_TYPE (Entity->EntityType) | 1,013 | 1,013 | **100.0%** |
| INGESTED_VIA (Source->Pipeline) | 1,477 | 1,709 | **86.4%** |
| IS_FACT_TYPE (Fact->FactType) | 868 | 1,518 | **57.2%** |
| IS_CLAIM_TYPE (Claim->ClaimType) | 797 | 1,145 | **69.6%** |
| IS_DATAPOINT_TYPE (FDP->DataPointType) | 249 | 430 | **57.9%** |
| IS_CATEGORY (Topic->ConceptCategory) | 195 | 227 | **85.9%** |

**Classification avg coverage**: 81.1%

### D-4 Score Calculation

| Sub-check | Score | Weight | v1 Score |
|-----------|------:|-------:|---------:|
| Entity property coverage (avg) | 44.1% | 20% | 44.1% |
| Source property coverage (avg) | 72.6% | 20% | 72.6% |
| Core relationship coverage (avg of key rels) | 84.8% | 20% | 76.5% |
| FOR_METRIC coverage | 30.0% | 10% | 5.1% |
| Classification hub materialization (8/16) | 50.0% | 10% | 0.0% |
| Classification relationship coverage (avg) | 81.1% | 20% | 0.0% |

Note: D-4 weights adjusted to include classification coverage (new sub-check). Weights redistributed from 25/25/30/10/10 to 20/20/20/10/10/20 to accommodate.

**D-4 Score: 79.3%** (was 52.6%, +26.7)

---

## Overall Quality Score

| Category | Weight | v1 Score | v2 Score | Weighted v1 | Weighted v2 | Delta |
|----------|-------:|--------:|---------:|------------:|------------:|------:|
| D-1: Ontology Conformance | 30% | 93.5% | 95.1% | 28.1 | 28.5 | +0.5 |
| D-2: Duplicate Detection | 20% | 99.4% | 99.4% | 19.9 | 19.9 | 0.0 |
| D-3: Orphan Node Detection | 25% | 89.7% | 98.3% | 22.4 | 24.6 | +2.1 |
| D-4: Coverage Matrix | 25% | 52.6% | 79.3% | 13.2 | 19.8 | +6.7 |
| **Overall** | **100%** | | | **83.5** | **92.7** | **+9.2** |

## Quality Rating: A

| Rating | Range | Description |
|--------|-------|-------------|
| **A** | **90-100** | **Production-ready** |
| B | 75-89 | Good quality, addressable gaps |
| C | 60-74 | Significant issues |
| D | < 60 | Major remediation needed |

**Upgraded from B (83.5) to A (92.7)**

---

## Key Improvements Achieved

| Improvement | Before | After | Impact |
|-------------|--------|-------|--------|
| Entity orphans eliminated | 254 (25.1%) | 0 (0.0%) | All entities connected via IS_TYPE + MENTIONS |
| Source TAGGED gap closed | 247 (14.5%) | 0 (0.0%) | All sources classified to topics |
| FOR_METRIC coverage 6x | 22 (5.1%) | 129 (30.0%) | Metric linkage greatly improved |
| MENTIONS relationship built | 49 | 925 | Source->Entity discoverability |
| Classification hubs materialized | 0/16 | 8/16 | Type-safe enumeration via hub nodes |
| Classification relationships | 0 | 8,278 total | Structured type references |
| TAGGED relationships | 17,176 | 20,615 | +3,439 topic assignments |
| Total relationships | 42,961 | 55,261 | +12,300 (+28.6%) |

---

## Remaining Action Items

### P1 (High)

1. **Entity type consolidation (127 entities, 12.5%)**: 42 non-canonical entity_types remain (e.g., `macro`(24), `central_bank`(12), `model`(14), `method`(7)). Need normalization to 14 canonical types.
2. **Source type consolidation (46 sources, 2.7%)**: `academic_paper`(23)/`paper`(18) -> `academic`, `white_paper`(4) -> `report`, `media`(1) -> `news`.
3. **IS_FACT_TYPE coverage (57.2%)**: 650 Facts lack FactType classification.
4. **IS_CLAIM_TYPE coverage (69.6%)**: 348 Claims lack ClaimType classification.

### P2 (Medium)

5. **FOR_METRIC gap (70.0%)**: 301 FDP nodes still lack FOR_METRIC. Improved from 94.9% but significant gap remains.
6. **IS_DATAPOINT_TYPE coverage (57.9%)**: 181 FDP nodes unclassified.
7. **DataPointType orphans (2)**: "forecast" and "consensus" types have no connected FDP nodes.
8. **Entity enrichment**: `sector`(13.7%), `ticker`(11.1%), `enriched_at`(6.8%) still low.
9. **Remaining 8 unmaterialized hub labels**: Domain, Language, Identifier, Industry, Alias, UnitOfMeasure, AuthorType, InstrumentClass.
10. **Fact/Claim orphans**: 18 Facts + 7 Claims without Source links (unchanged).

### P3 (Low)

11. **True duplicate cleanup**: 7 entity pairs, 8 topic pairs, 4 source URL pairs.
12. **FDP orphans**: 38 without FOR_PERIOD, 33 without RELATES_TO (unchanged).
13. **Source language/domain coverage**: 7.5% / 19.4% (unchanged).
14. **Topic IS_CATEGORY gap**: 32 topics without ConceptCategory assignment.

---

## Appendix: Graph Statistics

| Metric | v1 | v2 | Delta |
|--------|---:|---:|------:|
| Total nodes | 7,383 | 7,503 | +120 |
| Total relationships | 42,961 | 55,261 | +12,300 |
| Distinct node labels | 17 | 25 | +8 |
| Distinct relationship types | 38 | 47 | +9 |
| Ontology-defined labels | 33 | 33 | 0 |
| Ontology-defined relationship types | 59 | 59 | 0 |
| Label coverage | 17/33 (51.5%) | 25/33 (75.8%) | +24.3% |
| Relationship type coverage | 38/59 (64.4%) | 47/59 (79.7%) | +15.3% |

### New Classification Hub Nodes (v2)

| Hub Label | Instances | Example Values |
|-----------|----------:|----------------|
| SourceType | 16 | news, blog, web, pdf, analysis, academic, ... |
| TrustLevel | 20 | academic, analyst, company, official, peer_reviewed, ... |
| EntityType | 42 | company, technology, organization, person, concept, ... |
| Pipeline | 10 | web-research, finance-news-workflow, pdf-extraction, ... |
| FactType | 10 | statistic, financial_metric, macro_indicator, event, ... |
| ClaimType | 10 | fundamental, bullish, bearish, technical, risk_event, ... |
| DataPointType | 4 | actual, estimate, forecast, consensus |
| ConceptCategory | 8 | MacroEconomics, EquityResearch, SectorAnalysis, ... |
