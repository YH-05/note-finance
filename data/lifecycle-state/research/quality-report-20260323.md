# Research Neo4j Quality Report

**Date**: 2026-03-23
**Instance**: research-neo4j (bolt://localhost:7688)
**Ontology Version**: research-3.0
**Graph Size**: 7,383 nodes / 42,961 relationships

---

## D-1: Ontology Conformance (30%)

### Node Labels

| Label | Count | In Ontology? |
|-------|------:|:---:|
| Source | 1,709 | Yes |
| Fact | 1,518 | Yes |
| Claim | 1,145 | Yes |
| Chunk | 1,015 | Yes |
| Entity | 1,013 | Yes |
| FinancialDataPoint | 430 | Yes |
| Topic | 227 | Yes |
| Author | 115 | Yes |
| Stance | 74 | Yes |
| Metric | 55 | Yes |
| FiscalPeriod | 25 | Yes |
| Insight | 23 | Yes |
| Memory | 17 | Yes (Operational) |
| SkillRun | 17 | Yes (Operational) |
| Sector | 11 | Yes |
| Question | 3 | Yes (Operational) |
| QualitySnapshot | 2 | Yes (Operational) |

**Unexpected labels**: 0
**Labels present**: 17 / 33 defined (16 new v3.0 classification hub labels not yet materialized)

### Relationship Types

All 38 existing relationship types are defined in the ontology (59 defined total).
**Non-conforming relationship types**: 0

### Entity Type Distribution (entity_type property)

| Canonical Type | Count | Consolidates From | Non-Canonical Count |
|---------------|------:|-------------------|--------------------:|
| company | 190 | fintech(8), subsidiary(3), fintech_holding(2), digital_bank(1), it_services(1) | 15 |
| technology | 275 | system(1) | 1 |
| organization | 127 | central_bank(12), government(1), government_agency(1), institution(1), exchange(1) | 16 |
| person | 89 | - | 0 |
| index | 39 | - | 0 |
| indicator | 28 | metric(10) | 10 |
| instrument | 22 | etf(6), currency(4), currency_pair(2), fund(2), bond(1), asset(1) | 16 |
| commodity | 16 | - | 0 |
| country | 15 | region(1) | 1 |
| sector | 13 | market(1) | 1 |
| concept | 53 | model(14), method(7), theme(9), article_proposal(7), event(1) | 38 |
| regulation | 3 | - | 0 |
| broker | 9 | - | 0 |
| product | 7 | dataset(4), data_center(1) | 5 |
| **N/A** | - | macro(24) | **24** |

**Already canonical**: 886 / 1,013 (87.5%)
**Need consolidation**: 127 / 1,013 (12.5%)
- 103 entities map to a canonical type via `consolidates` rules
- 24 entities have `macro` type (not in canonical 14, needs mapping to `indicator` or `concept`)

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
| academic | 12 |
| presentation | 22 |
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

**Canonical**: 1,663 / 1,709 (97.3%)
**Need consolidation**: 46 / 1,709 (2.7%)

### Topic Category Distribution

| Status | Count |
|--------|------:|
| Maps to 8 ConceptCategories | 152 |
| Unmapped (non-null) | 47 |
| Null category | 28 |
| **Total** | **227** |

Unmapped categories: `finance`(33), `methodology`(4), `segment`(3), `market`(2), `business_model`(1), `financial`(1), `market_trend`(1), `regional_market`(1), `risk_analysis`(1)

**Mapped**: 152 / 199 non-null (76.4%)

### D-1 Score Calculation

| Sub-check | Score | Weight |
|-----------|------:|-------:|
| Label conformance (17/17 existing = 100%) | 100.0% | 30% |
| Relationship type conformance (38/38 = 100%) | 100.0% | 20% |
| Entity type canonical rate | 87.5% | 20% |
| Source type canonical rate | 97.3% | 15% |
| Topic category mapped rate | 76.4% | 15% |

**D-1 Score: 93.5%**

---

## D-2: Duplicate Detection (20%)

### Entity Duplicates (same name, case-insensitive)

Total pairs with identical names: **19**

| Type | Count | Examples |
|------|------:|---------|
| True duplicates (same entity_type) | 7 | NVIDIA/Nvidia::company, Federal Reserve (central_bank vs organization), China/Japan/Singapore (country vs organization) |
| Multi-role (different entity_type) | 12 | Goldman Sachs (broker vs company), Toyota (company vs organization), TDA (concept vs method vs technology) |

#### True Duplicates (require merge)

| Name | Key 1 | Key 2 | Issue |
|------|-------|-------|-------|
| NVIDIA | NVIDIA::company | Nvidia::company | Case difference |
| Federal Reserve | Federal Reserve::central_bank | Federal Reserve::organization | Needs consolidation to `organization` |
| China | China::country | China::organization | Needs consolidation to `country` |
| Singapore | Singapore::country | Singapore::organization | Needs consolidation to `country` |
| Japan | Japan::country | Japan::organization | Needs consolidation to `country` |
| Bank of Thailand | Bank of Thailand::central_bank | BankOfThailand::organization | entity_key format + consolidation |
| Osaka Metropolitan Univ | osaka_metropolitan_university | Osaka Metropolitan Univ::organization | Legacy key format |

### Topic Duplicates

Same-name topic pairs: **8**

| Name | Key 1 | Key 2 |
|------|-------|-------|
| Telecom M&A | ::corporate-action | ::sector |
| ESG | ::governance | ::stock |
| Earnings | ::earnings, ::financial | ::theme |
| Infrastructure Assets | ::assets | ::segment |
| AI Cloud | ::ai | ::technology |
| Portfolio Optimization | ::finance | ::quantitative_finance |

### Source URL Duplicates

Duplicate URL pairs: **4**

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

**D-2 Score: 99.4%** (inverse of duplicate rate)

---

## D-3: Orphan Node Detection (25%)

### Orphan Summary

| Node Type | Total | Orphan Count | Orphan Rate |
|-----------|------:|-------------:|------------:|
| Fact (no STATES_FACT<-Source) | 1,518 | 18 | 1.2% |
| Claim (no MAKES_CLAIM<-Source) | 1,145 | 7 | 0.6% |
| Entity (no relationships at all) | 1,013 | 254 | 25.1% |
| Source (no TAGGED->Topic) | 1,709 | 247 | 14.5% |
| FDP (no FOR_PERIOD->FiscalPeriod) | 430 | 38 | 8.8% |
| FDP (no RELATES_TO->Entity) | 430 | 33 | 7.7% |

### Critical Issues

- **Entity orphans (254)**: 25.1% of all entities have zero relationships. These are completely isolated nodes with no connections to any Source, Fact, Claim, or other Entity.
- **Source without TAGGED (247)**: 14.5% of sources have no topic classification.

### D-3 Score Calculation

| Orphan Check | Orphan Rate | Weight |
|-------------|------------:|-------:|
| Fact orphans | 1.2% | 20% |
| Claim orphans | 0.6% | 20% |
| Entity orphans | 25.1% | 25% |
| Source no TAGGED | 14.5% | 20% |
| FDP no FOR_PERIOD | 8.8% | 7.5% |
| FDP no RELATES_TO | 7.7% | 7.5% |

Weighted orphan rate: (1.2%*20 + 0.6%*20 + 25.1%*25 + 14.5%*20 + 8.8%*7.5 + 7.7%*7.5) / 100 = **10.3%**

**D-3 Score: 89.7%** (100% - 10.3%)

---

## D-4: Coverage Matrix (25%)

### Entity Property Coverage

| Property | Non-Null | Total | Coverage |
|----------|--------:|------:|---------:|
| entity_key | 1,013 | 1,013 | 100.0% |
| name | 1,013 | 1,013 | 100.0% |
| entity_id | 979 | 1,013 | 96.6% |
| entity_type | 1,013 | 1,013 | 100.0% |
| sector | 139 | 1,013 | 13.7% |
| industry | 91 | 1,013 | 9.0% |
| ticker | 112 | 1,013 | 11.1% |
| sec_cik | 33 | 1,013 | 3.3% |
| enriched_at | 69 | 1,013 | 6.8% |
| updated_at | 6 | 1,013 | 0.6% |

**Entity avg coverage**: 44.1% (core props: entity_key, name, entity_type at 100%; enrichment props much lower)

### Source Property Coverage

| Property | Non-Null | Total | Coverage |
|----------|--------:|------:|---------:|
| source_id | 1,709 | 1,709 | 100.0% |
| url | 1,574 | 1,709 | 92.1% |
| title | 1,708 | 1,709 | 99.9% |
| source_type | 1,709 | 1,709 | 100.0% |
| collected_at | 1,168 | 1,709 | 68.3% |
| published_at | 1,054 | 1,709 | 61.7% |
| authority_level | 1,570 | 1,709 | 91.9% |
| category | 1,221 | 1,709 | 71.4% |
| command_source | 1,477 | 1,709 | 86.4% |
| language | 128 | 1,709 | 7.5% |
| domain | 331 | 1,709 | 19.4% |

**Source avg coverage**: 72.6%

### Relationship Coverage

| Relationship | Count | Expected From | Coverage Notes |
|-------------|------:|---------------|---------------|
| TAGGED | 17,176 | Source->Topic | 85.6% of Sources have at least 1 |
| STATES_FACT | 2,466 | Source->Fact | 98.8% of Facts linked |
| MAKES_CLAIM | 1,155 | Source->Claim | 99.4% of Claims linked |
| CONTAINS_CHUNK | 1,015 | Source->Chunk | 100% (1:1 with Chunks) |
| EXTRACTED_FROM | 1,411 | Fact/Claim->Chunk | ~53% of Fact+Claim linked |
| HAS_DATAPOINT | 402 | Source->FDP | 93.5% of FDP linked |
| ABOUT | 2,560 | Fact/Claim->Topic | ~96% of Facts+Claims |
| RELATES_TO | 2,834 | Fact/FDP->Entity | Varies |
| FOR_PERIOD | 392 | FDP->FiscalPeriod | 91.2% of FDP |
| FOR_METRIC | 22 | FDP->Metric | **5.1% of FDP** |
| AUTHORED_BY | 192 | Source->Author | 11.2% of Sources |
| IN_SECTOR | 143 | Entity->Sector | 14.1% of Entities |

### v3.0 Classification Hub Node Coverage

| Hub Label | Instances | Status |
|-----------|----------:|--------|
| SourceType | 0 | Not materialized |
| Domain | 0 | Not materialized |
| TrustLevel | 0 | Not materialized |
| Language | 0 | Not materialized |
| Pipeline | 0 | Not materialized |
| EntityType | 0 | Not materialized |
| Identifier | 0 | Not materialized |
| Industry | 0 | Not materialized |
| Alias | 0 | Not materialized |
| FactType | 0 | Not materialized |
| ClaimType | 0 | Not materialized |
| UnitOfMeasure | 0 | Not materialized |
| DataPointType | 0 | Not materialized |
| ConceptCategory | 0 | Not materialized |
| AuthorType | 0 | Not materialized |
| InstrumentClass | 0 | Not materialized |

**v3.0 hub nodes**: 0 / 16 materialized (Phase B migration not yet executed)

### D-4 Score Calculation

| Sub-check | Score | Weight |
|-----------|------:|-------:|
| Entity property coverage (avg) | 44.1% | 25% |
| Source property coverage (avg) | 72.6% | 25% |
| Core relationship coverage (avg of key rels) | 76.5% | 30% |
| FOR_METRIC coverage | 5.1% | 10% |
| v3.0 hub materialization | 0.0% | 10% |

**D-4 Score: 52.6%**

---

## Overall Quality Score

| Category | Weight | Score | Weighted |
|----------|-------:|------:|---------:|
| D-1: Ontology Conformance | 30% | 93.5% | 28.1 |
| D-2: Duplicate Detection | 20% | 99.4% | 19.9 |
| D-3: Orphan Node Detection | 25% | 89.7% | 22.4 |
| D-4: Coverage Matrix | 25% | 52.6% | 13.2 |
| **Overall** | **100%** | | **83.5** |

## Quality Rating: B

| Rating | Range | Description |
|--------|-------|-------------|
| A | 90-100 | Production-ready |
| **B** | **75-89** | **Good quality, addressable gaps** |
| C | 60-74 | Significant issues |
| D | < 60 | Major remediation needed |

---

## Priority Action Items

### P0 (Critical)

1. **Entity orphans (254 nodes, 25.1%)**: Run entity-linker to connect isolated entities to Facts/Claims/Sources. This is the largest quality gap.
2. **FOR_METRIC coverage (5.1%)**: Only 22 of 430 FDP nodes have a FOR_METRIC relationship. Need systematic Metric assignment.

### P1 (High)

3. **Source TAGGED gap (247 sources, 14.5%)**: Run topic-discovery or manual TAGGED relationship creation for unclassified sources.
4. **Entity type consolidation (127 entities)**: Normalize 42 legacy entity_types to 14 canonical types (e.g., `macro`->?, `central_bank`->`organization`, `model`->`concept`).
5. **Source type consolidation (46 sources)**: Normalize `academic_paper`/`paper`->`academic`, `white_paper`->`report`, `media`->`news`.

### P2 (Medium)

6. **Entity enrichment**: `sector`(13.7%), `ticker`(11.1%), `enriched_at`(6.8%) coverage is low. Run enrichment pipeline for company/index entities.
7. **Source language/domain**: `language`(7.5%), `domain`(19.4%) coverage needs improvement.
8. **v3.0 hub node materialization**: 16 classification hub labels not yet created. Blocked on Phase B migration.
9. **Topic category mapping**: 47 topics with non-standard categories + 28 with null category.

### P3 (Low)

10. **True duplicate cleanup**: 7 entity pairs, 8 topic pairs, 4 source URL pairs need merge.
11. **Orphan Facts (18) / Claims (7)**: Small number, link back to Sources.
12. **FDP orphans**: 38 without FOR_PERIOD, 33 without RELATES_TO.

---

## Appendix: Graph Statistics

| Metric | Value |
|--------|------:|
| Total nodes | 7,383 |
| Total relationships | 42,961 |
| Distinct node labels | 17 |
| Distinct relationship types | 38 |
| Ontology-defined labels | 33 |
| Ontology-defined relationship types | 59 |
| Label coverage | 17 / 33 (51.5%) |
| Relationship type coverage | 38 / 59 (64.4%) |
