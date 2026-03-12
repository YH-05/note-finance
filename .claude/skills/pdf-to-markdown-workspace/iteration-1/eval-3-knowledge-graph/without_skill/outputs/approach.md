# Approach: JP Morgan ISAT PDF to Neo4j Knowledge Graph

## Task

Convert the JP Morgan ISAT report PDF into structured data (entities, facts, claims, financial data points) and load them into Neo4j.

**Input**: `data/sample_report/JP Morgan ISAT@IJ Indosat Tbk PT ~10% qoq growth in ARPU drove 4Q25 EPS b.pdf`

---

## Complete Multi-Step Workflow

The workflow spans 7 phases, implemented across `src/pdf_pipeline/`. Phases 1-4 are fully implemented. Phase 5 (knowledge extraction) is implemented but disabled by default. Phases 6-7 (entity resolution, graph writing) are **not yet implemented** -- the design doc describes them but `entity_resolver.py`, `datapoint_converter.py`, and `graph_writer.py` do not exist in the codebase.

### Step 1: PDF to Markdown Conversion (Phases 1-4) -- IMPLEMENTED

Run the existing pdf-pipeline CLI to convert the PDF into chunked Markdown + table JSON.

```bash
uv run pdf-pipeline process \
  "data/sample_report/JP Morgan ISAT@IJ Indosat Tbk PT ~10% qoq growth in ARPU drove 4Q25 EPS b.pdf" \
  --output-dir data/processed
```

**What happens internally:**
1. **Phase 1 (Scan)**: `PdfScanner` computes SHA-256 hash of the PDF for idempotency.
2. **Phase 2 (Filter)**: `FitzTextExtractor` extracts raw text via PyMuPDF, `NoiseFilter` removes boilerplate (page numbers, disclaimers) using regex patterns from `data/config/pdf-pipeline-config.yaml`.
3. **Phase 3 (Convert)**: `MarkdownConverter` uses `ProviderChain` (Gemini CLI first, Claude Code fallback) to convert the PDF into structured Markdown with ATX headings preserved.
4. **Phase 4 (Tables)**: `TableDetector` detects table regions, `TableReconstructor` extracts structured table data via LLM. Falls back gracefully if reconstruction fails.
5. **Chunk**: `MarkdownChunker` splits Markdown by section headings into chunks.

**Output**: `data/processed/{sha256}/chunks.json` -- array of chunk objects with `content`, `section_title`, `chunk_index`, and `tables` fields.

### Step 2: Knowledge Extraction (Phase 5) -- IMPLEMENTED, DISABLED BY DEFAULT

The `KnowledgeExtractor` class exists at `src/pdf_pipeline/core/knowledge_extractor.py`. It is wired into the pipeline but only runs if `enable_knowledge_extraction` is `True` in the config. The CLI's `_build_pipeline_for_dir()` function does **not** currently pass a `KnowledgeExtractor` instance to the pipeline, so it must be enabled manually.

**Option A: Modify the CLI to enable it**

Edit `src/pdf_pipeline/cli/main.py` `_build_pipeline_for_dir()` to add:

```python
from pdf_pipeline.core.knowledge_extractor import KnowledgeExtractor

knowledge_extractor = KnowledgeExtractor(provider_chain=provider_chain)

return PdfPipeline(
    ...
    knowledge_extractor=knowledge_extractor,
)
```

Then re-run:
```bash
uv run pdf-pipeline reprocess --hash <sha256_of_jp_morgan_pdf>
```

**Option B: Run extraction separately via Python**

```python
import json
from pathlib import Path
from pdf_pipeline.core.knowledge_extractor import KnowledgeExtractor
from pdf_pipeline.services.gemini_provider import GeminiCLIProvider
from pdf_pipeline.services.claude_provider import ClaudeCodeProvider
from pdf_pipeline.services.provider_chain import ProviderChain

chain = ProviderChain([GeminiCLIProvider(), ClaudeCodeProvider()])
extractor = KnowledgeExtractor(provider_chain=chain)

chunks_path = Path("data/processed/<sha256>/chunks.json")
chunks = json.loads(chunks_path.read_text())
source_hash = chunks_path.parent.name

result = extractor.extract_from_chunks(chunks=chunks, source_hash=source_hash)
extraction_path = chunks_path.parent / "extraction.json"
extraction_path.write_text(result.model_dump_json(indent=2))
```

**Output**: `data/processed/{sha256}/extraction.json` containing:
- `entities[]`: ExtractedEntity (name, entity_type, ticker, aliases)
- `facts[]`: ExtractedFact (content, fact_type, as_of_date, confidence, about_entities)
- `claims[]`: ExtractedClaim (content, claim_type, sentiment, confidence, about_entities)

The extraction uses a single-pass LLM prompt (the design doc describes a 2-pass approach, but the current implementation uses 1 pass for simplicity).

### Step 3: Entity Name Resolution (Phase 6) -- NOT YET IMPLEMENTED

The design doc (`docs/plan/KnowledgeGraph/2026-03-11_pdf-to-markdown-pipeline.md`) describes `core/entity_resolver.py` with a 3-stage matching process:

1. Alias exact match against `data/config/master-entities.yaml`
2. Ticker match
3. LLM-based fuzzy match

**Problem**: `master-entities.yaml` does not exist yet. `entity_resolver.py` does not exist. This step would need to be implemented from scratch. For a quick workaround, you could skip formal resolution and use the raw entity names from extraction.

### Step 4: ID Generation -- IMPLEMENTED

`src/pdf_pipeline/services/id_generator.py` provides deterministic ID generation:

```python
from pdf_pipeline.services.id_generator import (
    generate_source_id,
    generate_entity_id,
    generate_chunk_id,
    generate_datapoint_id,
    generate_period_id,
)
```

All IDs are deterministic (UUID5 or SHA-256 based), enabling idempotent Neo4j MERGE operations.

### Step 5: Neo4j Constraint Setup -- PARTIALLY IMPLEMENTED

Before writing data, Neo4j constraints need to be applied. Two constraint files exist:

1. **Existing base constraints** (from save-to-graph skill, already applied to the running Neo4j):
   - `unique_source_id`, `unique_entity_id`, `unique_claim_id`, etc.

2. **PDF-pipeline specific constraints** at `data/config/neo4j-pdf-constraints.cypher`:
   - `unique_fact_id`, `unique_claim_id` (for Fact/Claim nodes)

3. **Additional constraints from design doc** (NOT yet in any file):
   - `unique_chunk_id`, `unique_datapoint_id`, `unique_period_id`
   - Indexes on `datapoint_metric`, `datapoint_period`, `period_year`

```bash
# Apply existing constraints
cypher-shell -u neo4j -p finance-neo4j-2026 -a bolt://localhost:7687 \
  < data/config/neo4j-pdf-constraints.cypher

# Apply additional constraints manually
cypher-shell -u neo4j -p finance-neo4j-2026 -a bolt://localhost:7687 << 'CYPHER'
CREATE CONSTRAINT unique_chunk_id IF NOT EXISTS
  FOR (ch:Chunk) REQUIRE ch.chunk_id IS UNIQUE;
CREATE CONSTRAINT unique_datapoint_id IF NOT EXISTS
  FOR (dp:FinancialDataPoint) REQUIRE dp.datapoint_id IS UNIQUE;
CREATE CONSTRAINT unique_period_id IF NOT EXISTS
  FOR (fp:FiscalPeriod) REQUIRE fp.period_id IS UNIQUE;
CYPHER
```

Or use the Neo4j MCP tool (available in `.mcp.json` as `neo4j-cypher`):
```
mcp__neo4j-cypher__note-finance-write_neo4j_cypher
```

### Step 6: Write to Neo4j (Phase 7) -- NOT YET IMPLEMENTED

The design doc describes `services/graph_writer.py` but it **does not exist**. The intended approach is MERGE-based Cypher queries via `cypher-shell` or the Neo4j MCP tool (`mcp__neo4j-cypher__note-finance-write_neo4j_cypher`).

**Manual workaround using Neo4j MCP tools:**

After obtaining `extraction.json`, write nodes and relationships manually:

```python
# Pseudocode for what graph_writer.py would do:

import json
from pdf_pipeline.services.id_generator import generate_entity_id, generate_source_id

extraction = json.loads(Path("data/processed/<hash>/extraction.json").read_text())

# 1. Create Source node
source_id = generate_source_id("file:///path/to/jp-morgan-isat.pdf")

# 2. Create Chunk nodes (from chunks.json)
# 3. Create Entity nodes (from extraction.entities)
# 4. Create Fact nodes (from extraction.facts)
# 5. Create Claim nodes (from extraction.claims)
# 6. Create relationships: HAS_CHUNK, STATES_FACT, MAKES_CLAIM, ABOUT, EXTRACTED_FROM
```

**Via Neo4j MCP (the most practical current approach):**

```cypher
-- Create Source node
MERGE (s:Source {source_id: $source_id})
SET s.title = "JP Morgan - Indosat 4Q25",
    s.source_type = "pdf",
    s.publisher = "JP Morgan",
    s.file_path = "data/sample_report/JP Morgan ISAT@IJ..."

-- Create Entity nodes
MERGE (e:Entity {entity_id: $entity_id})
SET e.name = "Indosat Ooredoo Hutchison",
    e.entity_type = "company",
    e.ticker = "ISAT",
    e.entity_key = "Indosat Ooredoo Hutchison::company"

-- Create Fact/Claim nodes
MERGE (f:Fact {fact_id: $fact_id})
SET f.content = "4Q25 ARPU grew ~10% qoq",
    f.fact_type = "statistic",
    f.confidence = 0.9

-- Create relationships
MATCH (s:Source {source_id: $source_id})
MATCH (f:Fact {fact_id: $fact_id})
MERGE (s)-[:STATES_FACT]->(f)

MATCH (f:Fact {fact_id: $fact_id})
MATCH (e:Entity {entity_id: $entity_id})
MERGE (f)-[:RELATES_TO]->(e)
```

---

## Summary of Implementation Gaps

| Component | Status | File |
|-----------|--------|------|
| PDF scanning + hashing | Implemented | `core/pdf_scanner.py` |
| Text extraction (PyMuPDF) | Implemented | `core/text_extractor.py` |
| Noise filtering | Implemented | `core/noise_filter.py` |
| Markdown conversion (LLM) | Implemented | `core/markdown_converter.py` |
| Table detection | Implemented | `core/table_detector.py` |
| Table reconstruction (LLM) | Implemented | `core/table_reconstructor.py` |
| Chunking | Implemented | `core/chunker.py` |
| Pipeline orchestrator (Ph 1-4) | Implemented | `core/pipeline.py` |
| CLI | Implemented | `cli/main.py` |
| Knowledge extraction (Ph 5A) | Implemented (disabled) | `core/knowledge_extractor.py` |
| Extraction schemas | Implemented | `schemas/extraction.py` |
| ID generation | Implemented | `services/id_generator.py` |
| LLM providers (Gemini/Claude) | Implemented | `services/gemini_provider.py`, `services/claude_provider.py` |
| Provider chain (fallback) | Implemented | `services/provider_chain.py` |
| State management | Implemented | `services/state_manager.py` |
| FinancialDataPoint converter (5B) | **NOT IMPLEMENTED** | `core/datapoint_converter.py` (planned) |
| FiscalPeriod generation (5C) | **NOT IMPLEMENTED** | (no file) |
| Entity relation extraction (5D) | **NOT IMPLEMENTED** | (no file) |
| Entity name resolution (Ph 6) | **NOT IMPLEMENTED** | `core/entity_resolver.py` (planned) |
| Master entities YAML | **NOT CREATED** | `data/config/master-entities.yaml` (planned) |
| Graph writer (Ph 7) | **NOT IMPLEMENTED** | `services/graph_writer.py` (planned) |
| Neo4j PDF constraints | Partially done | `data/config/neo4j-pdf-constraints.cypher` |

---

## Exact Commands to Run (End-to-End)

### 1. Convert PDF to chunks

```bash
cd /Users/yuki/Desktop/note-finance

uv run pdf-pipeline process \
  "data/sample_report/JP Morgan ISAT@IJ Indosat Tbk PT ~10% qoq growth in ARPU drove 4Q25 EPS b.pdf"
```

### 2. Run knowledge extraction (requires code change or scripting)

```bash
# Option: Quick Python script
uv run python -c "
import json
from pathlib import Path
from pdf_pipeline.core.knowledge_extractor import KnowledgeExtractor
from pdf_pipeline.services.gemini_provider import GeminiCLIProvider
from pdf_pipeline.services.claude_provider import ClaudeCodeProvider
from pdf_pipeline.services.provider_chain import ProviderChain

chain = ProviderChain([GeminiCLIProvider(), ClaudeCodeProvider()])
extractor = KnowledgeExtractor(provider_chain=chain)

# Find the output directory (most recent hash)
processed = Path('data/processed')
hash_dirs = [d for d in processed.iterdir() if d.is_dir() and len(d.name) == 64]
latest = sorted(hash_dirs, key=lambda d: d.stat().st_mtime)[-1]

chunks = json.loads((latest / 'chunks.json').read_text())
result = extractor.extract_from_chunks(chunks=chunks, source_hash=latest.name)
(latest / 'extraction.json').write_text(result.model_dump_json(indent=2))
print(f'Extracted: {sum(len(c.entities) for c in result.chunks)} entities, '
      f'{sum(len(c.facts) for c in result.chunks)} facts, '
      f'{sum(len(c.claims) for c in result.chunks)} claims')
"
```

### 3. Apply Neo4j constraints

```bash
# Ensure Neo4j is running
docker compose up -d neo4j

# Apply constraints
cypher-shell -u neo4j -p finance-neo4j-2026 -a bolt://localhost:7687 << 'CYPHER'
CREATE CONSTRAINT unique_fact_id IF NOT EXISTS FOR (f:Fact) REQUIRE f.fact_id IS UNIQUE;
CREATE CONSTRAINT unique_chunk_id IF NOT EXISTS FOR (ch:Chunk) REQUIRE ch.chunk_id IS UNIQUE;
CYPHER
```

### 4. Load into Neo4j (manual -- graph_writer.py not implemented)

Use the Neo4j MCP tool `mcp__neo4j-cypher__note-finance-write_neo4j_cypher` or write a script that reads `extraction.json` and generates MERGE Cypher queries using the ID generator functions, following the patterns established in `.claude/skills/save-to-graph/guide.md`.

No single command exists for this step today. You would need to either:
- Implement `graph_writer.py` following the design doc patterns
- Use the existing `/save-to-graph` skill by first converting `extraction.json` to graph-queue format via `scripts/emit_graph_queue.py` (but this script doesn't handle PDF pipeline output format)
- Write MERGE queries manually via the Neo4j MCP tools

---

## How Long It Took to Piece Together the Full Workflow

**Total exploration time**: Approximately 8-10 minutes of codebase exploration across ~20 files.

### Files explored (in order):
1. `src/pdf_pipeline/` directory listing -- identified all modules
2. `docs/plan/KnowledgeGraph/2026-03-11_pdf-to-markdown-pipeline.md` -- the master design doc (992 lines), provided the full 7-phase architecture
3. `data/config/neo4j-pdf-constraints.cypher` -- Neo4j constraint definitions
4. `docs/obsidian/knowledge-graph/_overview.md` -- current graph stats and schema
5. `src/pdf_pipeline/core/pipeline.py` -- the pipeline orchestrator
6. `src/pdf_pipeline/cli/main.py` -- the CLI entry point and wiring
7. `src/pdf_pipeline/core/knowledge_extractor.py` -- Phase 5 extraction
8. `src/pdf_pipeline/schemas/extraction.py` -- Pydantic schemas for entities/facts/claims
9. `src/pdf_pipeline/services/id_generator.py` -- deterministic ID generation
10. `.claude/skills/save-to-graph/guide.md` -- Neo4j MERGE patterns and Cypher templates
11. `data/config/pdf-pipeline-config.yaml` -- pipeline configuration
12. `data/config/knowledge-graph-schema.yaml` -- full graph schema definition
13. `docker-compose.yml` -- Neo4j service configuration
14. `.mcp.json` -- MCP server configs including Neo4j connection details
15. `src/pdf_pipeline/types.py` -- type definitions and config models
16. `data/processed/` -- existing pipeline output
17. `pyproject.toml` -- entry point registration

---

## Confusion, Dead Ends, and Missing Links

### 1. Knowledge Extraction is Implemented but Not Wired in the CLI

The `KnowledgeExtractor` class exists and is fully functional, but the CLI's `_build_pipeline_for_dir()` function does not instantiate or pass it to `PdfPipeline`. The pipeline's `process_pdf()` method checks for `self.knowledge_extractor is not None` before running extraction. This means the CLI will silently skip Phase 5 unless you modify the wiring code or run extraction separately.

**Confusion level**: Medium. I had to read both `cli/main.py` and `pipeline.py` carefully to understand that the extractor was optional and not wired.

### 2. Three Key Modules Referenced in Design Doc Don't Exist

The design doc lists `graph_writer.py`, `entity_resolver.py`, and `datapoint_converter.py` in the file tree, but none of these files exist. The design doc's roadmap shows them as Step 5 and Step 6 (future work). This creates a significant gap between "convert PDF" and "load into Neo4j."

**Confusion level**: High. The design doc presents a complete architecture but the implementation stops at Phase 5A. The gap is documented in the design doc's "Status" line at the top ("Phase 2-4 ... Phase 5 onwards is subsequent"), but this is easy to miss.

### 3. Two Different Neo4j Writing Approaches

There are two different paradigms for writing to Neo4j:
- The existing `save-to-graph` skill uses `graph-queue` JSON files + `emit_graph_queue.py` + manual/slash-command Cypher execution
- The PDF pipeline design doc describes a Python `graph_writer.py` that writes directly

These are not connected. You cannot feed PDF pipeline output into the existing `save-to-graph` workflow without format conversion. And `graph_writer.py` does not exist.

**Confusion level**: High. I had to read both the save-to-graph guide and the PDF pipeline design doc to understand they are parallel systems.

### 4. Config Schema Mismatch

The `pdf-pipeline-config.yaml` has `llm.provider: "anthropic"` and `llm.model: "claude-opus-4-5"`, but the actual pipeline uses `ProviderChain([GeminiCLIProvider(), ClaudeCodeProvider()])` -- the config's LLM section appears unused by the actual provider chain wiring. The provider chain ordering is hardcoded in `_build_pipeline_for_dir()`.

**Confusion level**: Low. This is a minor inconsistency.

### 5. MCP Neo4j Tools Available but Relationship to Pipeline Unclear

The `.mcp.json` configures `neo4j-cypher` MCP tools, and the available deferred tools include `mcp__neo4j-cypher__note-finance-write_neo4j_cypher`. These could be used for Step 4 (writing to Neo4j), but there is no documented connection between the PDF pipeline and these MCP tools.

**Confusion level**: Medium. The MCP tools are the most practical way to write to Neo4j right now, but discovering this requires knowing to check `.mcp.json` and the available deferred tools list.

### 6. text_only Default is True

`PipelineConfig.text_only` defaults to `True`, which means table detection/reconstruction is skipped by default. The config YAML file does not set this field. For full financial data extraction from the JP Morgan report (which contains important tables), you would need to explicitly set `text_only: false` in the config or modify the code.

**Confusion level**: Low, but important for getting complete data from financial reports.
