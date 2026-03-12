# Approach: JP Morgan ISAT レポート PDF -> Knowledge Graph (Neo4j)

## Task

JP Morgan の ISAT レポート PDF を変換し、企業名や数値データを抽出して Neo4j に投入する。

Input: `data/sample_report/JP Morgan ISAT@IJ Indosat Tbk PT ~10% qoq growth in ARPU drove 4Q25 EPS b.pdf`

---

## Complete Multi-Step Workflow

### Overview

```
PDF -> Phase 1-3 (Scan/Filter/LLM Markdown) -> Phase 5 (Chunking) -> chunks.json
  -> KnowledgeExtractor (Entity/Fact/Claim extraction) -> extraction.json
  -> emit_graph_queue.py --command pdf-extraction -> graph-queue JSON
  -> /save-to-graph -> Neo4j
```

This is a 4-stage pipeline with 3 distinct tools/scripts involved.

---

### Step 1: PDF to Markdown + Chunks + Knowledge Extraction

**Command:**

```bash
uv run pdf-pipeline process "data/sample_report/JP Morgan ISAT@IJ Indosat Tbk PT ~10% qoq growth in ARPU drove 4Q25 EPS b.pdf"
```

**What happens internally:**

1. **Phase 1 (Scan):** PdfScanner computes SHA-256 hash of the PDF, checks idempotency via StateManager.
2. **Phase 2 (Filter):** FitzTextExtractor extracts raw text via PyMuPDF; NoiseFilter removes boilerplate (blank lines, page numbers, etc.).
3. **Phase 3 (Convert):** MarkdownConverter sends the PDF to GeminiCLIProvider (Vision-first approach). If Gemini fails, falls back to ClaudeCodeProvider. Produces structured Markdown.
4. **Phase 4 (Tables):** In text_only mode (default), table detection is skipped. If `text_only: false`, TableDetector + TableReconstructor would process tables.
5. **Chunking:** MarkdownChunker splits the Markdown into section-level chunks.
6. **Save:** Writes `data/processed/{sha256_hash}/chunks.json`.
7. **Knowledge Extraction (optional):** If a KnowledgeExtractor is configured, extracts entities/facts/claims from each chunk via LLM and saves `data/processed/{sha256_hash}/extraction.json`.

**Issue identified:** The CLI command (`_build_pipeline_for_dir` in `src/pdf_pipeline/cli/main.py`) does NOT wire up the `knowledge_extractor` parameter. Line 128-137 of the CLI shows `PdfPipeline(...)` is constructed without `knowledge_extractor=...`. This means running `uv run pdf-pipeline process` alone will NOT produce `extraction.json`.

**Workaround:** Use the Python API directly to include KnowledgeExtractor:

```python
from pathlib import Path
from pdf_pipeline.config.loader import load_config
from pdf_pipeline.core.chunker import MarkdownChunker
from pdf_pipeline.core.knowledge_extractor import KnowledgeExtractor
from pdf_pipeline.core.markdown_converter import MarkdownConverter
from pdf_pipeline.core.noise_filter import NoiseFilter
from pdf_pipeline.core.pdf_scanner import PdfScanner
from pdf_pipeline.core.pipeline import PdfPipeline
from pdf_pipeline.services.claude_provider import ClaudeCodeProvider
from pdf_pipeline.services.gemini_provider import GeminiCLIProvider
from pdf_pipeline.services.provider_chain import ProviderChain
from pdf_pipeline.services.state_manager import StateManager

pdf_path = Path("data/sample_report/JP Morgan ISAT@IJ Indosat Tbk PT ~10% qoq growth in ARPU drove 4Q25 EPS b.pdf")
output_dir = Path("data/processed")
config_path = Path("data/config/pdf-pipeline-config.yaml")

config = load_config(config_path)
config = config.model_copy(update={
    "output_dir": output_dir,
    "input_dirs": [pdf_path.parent],
})

provider_chain = ProviderChain([GeminiCLIProvider(), ClaudeCodeProvider()])
knowledge_extractor = KnowledgeExtractor(provider_chain=provider_chain)

pipeline = PdfPipeline(
    config=config,
    scanner=PdfScanner(input_dir=pdf_path.parent),
    noise_filter=NoiseFilter(config=config.noise_filter),
    markdown_converter=MarkdownConverter(provider=provider_chain),
    chunker=MarkdownChunker(),
    state_manager=StateManager(output_dir / "state.json"),
    knowledge_extractor=knowledge_extractor,  # <-- KEY: enables extraction.json
)

source_hash = PdfScanner(input_dir=pdf_path.parent).compute_sha256(pdf_path)
result = pipeline.process_pdf(pdf_path=pdf_path, source_hash=source_hash)
print(f"Status: {result['status']}, Chunks: {result.get('chunk_count', 0)}")
print(f"Extraction saved to: {output_dir / source_hash / 'extraction.json'}")
```

**Expected output files:**
- `data/processed/{sha256_hash}/chunks.json` -- section-level Markdown chunks
- `data/processed/{sha256_hash}/extraction.json` -- entities, facts, claims per chunk

**Expected extraction content for this PDF:**
- Entities: Indosat (ISAT), JP Morgan, possibly competitors (Telkomsel, XL Axiata), Indonesian Rupiah (IDR)
- Facts: ARPU ~10% qoq growth, 4Q25 EPS figures, revenue/EBITDA numbers
- Claims: analyst ratings (Overweight/Buy), target price, growth forecasts

---

### Step 2: extraction.json -> graph-queue JSON

**Command:**

```bash
python3 scripts/emit_graph_queue.py \
  --command pdf-extraction \
  --input data/processed/{sha256_hash}/extraction.json
```

**What happens:**
- `map_pdf_extraction()` function in `emit_graph_queue.py` (lines 530-662) processes the extraction data.
- Creates a Source node for the PDF (using `pdf:{source_hash}` as the URL).
- Deduplicates entities by `name:entity_type` key.
- Converts facts and claims into Claim nodes with `category: "pdf-fact"` and `category: "pdf-claim"` respectively.
- Builds relations: `STATES_FACT` (Source -> Fact/Claim), `MAKES_CLAIM` (Source -> Claim), `RELATES_TO` (Fact -> Entity), `ABOUT` (Claim -> Entity).
- Outputs a graph-queue JSON file to `.tmp/graph-queue/pdf-extraction/gq-{timestamp}-{hash4}.json`.

**Expected graph-queue structure:**
```json
{
  "schema_version": "1.0",
  "queue_id": "gq-20260312...-xxxx",
  "created_at": "2026-03-12T...",
  "command_source": "pdf-extraction",
  "session_id": "",
  "batch_label": "pdf-extraction",
  "sources": [
    {
      "source_id": "uuid5(pdf:{sha256})",
      "url": "pdf:{sha256}",
      "title": "",
      "published": "",
      "source_type": "pdf"
    }
  ],
  "entities": [
    {"entity_id": "...", "name": "Indosat", "entity_type": "company", "ticker": "ISAT"},
    {"entity_id": "...", "name": "JP Morgan", "entity_type": "organization", "ticker": null}
  ],
  "claims": [
    {"claim_id": "...", "content": "ARPU grew ~10% qoq in 4Q25", "source_id": "...", "category": "pdf-fact", ...},
    {"claim_id": "...", "content": "We maintain Overweight rating", "source_id": "...", "category": "pdf-claim", ...}
  ],
  "topics": [],
  "relations": {
    "source_fact": [...],
    "source_claim": [...],
    "fact_entity": [...],
    "claim_entity": [...]
  }
}
```

---

### Step 3: graph-queue JSON -> Neo4j

**Command:**

```bash
/save-to-graph --source pdf-extraction
```

Or, for a specific file:

```bash
/save-to-graph --file .tmp/graph-queue/pdf-extraction/gq-{timestamp}-{hash4}.json
```

**What happens (4 phases):**

1. **Phase 1 (Queue detection):** Connects to Neo4j (`cypher-shell`), validates the graph-queue JSON schema.
2. **Phase 2 (Node MERGE):** Inserts nodes in order: Topic -> Entity -> Source -> Claim. All via MERGE (idempotent).
   - Entity nodes: `MERGE (e:Entity {entity_id: $id}) SET e.name = "Indosat", e.entity_type = "company", e.entity_key = "Indosat::company"`
   - Source node: `MERGE (s:Source {source_id: $id}) SET s.url = "pdf:{hash}", s.source_type = "pdf", ...`
   - Claim nodes: `MERGE (c:Claim {claim_id: $id}) SET c.content = "...", ...`
3. **Phase 3a (Intra-file relations):** Creates TAGGED, MAKES_CLAIM, ABOUT relations within the file.
   - For pdf-extraction: uses the explicit `relations` object (source_fact, source_claim, fact_entity, claim_entity).
4. **Phase 3b (Cross-file relations):** Connects new nodes to existing DB nodes by category/content matching.
   - New Claims ABOUT existing Entities (content CONTAINS name).
   - New Entities ABOUT existing Claims (content CONTAINS name).
5. **Phase 4 (Cleanup):** Deletes or moves processed JSON files; outputs statistics summary.

**Pre-requisites:**
- Neo4j must be running (Docker or local).
- Environment variables set: `NEO4J_URI`, `NEO4J_USER`, `NEO4J_PASSWORD`.
- Initial setup (7 UNIQUE constraints + 4 indexes) must be completed. See `.claude/skills/save-to-graph/guide.md` "Initial Setup" section.

**Verification queries after insertion:**

```cypher
-- Check entities from this PDF
MATCH (s:Source {source_type: "pdf"})-[:MAKES_CLAIM]->(c:Claim)-[:ABOUT]->(e:Entity)
RETURN e.name, e.entity_type, e.ticker, count(c) AS claim_count
ORDER BY claim_count DESC

-- Check all facts/claims for Indosat
MATCH (c:Claim)-[:ABOUT]->(e:Entity {name: "Indosat"})
RETURN c.content, c.claim_type, c.confidence
ORDER BY c.confidence DESC
```

---

## Skill Evaluation: Does the Skill Clearly Guide Through the Full Knowledge Graph Workflow?

### What works well

1. **Step 1 (PDF -> Markdown -> chunks.json) is clearly documented.** The SKILL.md provides both CLI and Python API examples. The 5-phase architecture is well explained.

2. **Step 2 (extraction.json -> graph-queue) is documented.** The "Knowledge Extraction (optional)" section at lines 136-150 gives the 3-step recipe with exact commands.

3. **Step 3 (graph-queue -> Neo4j) is covered via cross-reference.** The skill references `/save-to-graph` and `scripts/emit_graph_queue.py`, and the save-to-graph skill/guide provides exhaustive detail on Cypher templates, phases, and verification.

4. **The `pdf-extraction` command is fully implemented** in `emit_graph_queue.py` (lines 530-662) with proper entity deduplication, fact/claim separation, and relation building.

5. **The extraction schema** (`src/pdf_pipeline/schemas/extraction.py`) is well-defined with Pydantic models for Entity, Fact, and Claim.

### Issues and Ambiguities

1. **Critical gap: CLI does not enable KnowledgeExtractor.** The `_build_pipeline_for_dir()` function in `cli/main.py` does not pass `knowledge_extractor` to `PdfPipeline`. Running `uv run pdf-pipeline process` will produce `chunks.json` but NOT `extraction.json`. The user must either:
   - Use the Python API directly (as shown above), or
   - Modify the CLI to add a `--extract` flag that wires up KnowledgeExtractor.
   The SKILL.md does not mention this limitation.

2. **The 3-step recipe is brief and buried.** The "Knowledge Extraction" section (lines 136-150) is only 14 lines and labeled "optional." It provides the commands but doesn't explain:
   - How to verify extraction.json was produced.
   - What the `{hash}` placeholder refers to (SHA-256 hash from Step 1 output).
   - How to handle the case where extraction fails (graceful degradation).

3. **No explicit mention of `pdf-extraction` as a command source in save-to-graph SKILL.md.** The save-to-graph skill's "Supported command sources" table (lines 383-391) lists 6 commands but does NOT include `pdf-extraction`. While `emit_graph_queue.py` supports it (line 718), the save-to-graph documentation creates an impression that PDF extraction is not a supported flow.

4. **Relation handling for pdf-extraction is different from other commands.** The `map_pdf_extraction` function outputs explicit `relations` with keys like `source_fact`, `source_claim`, `fact_entity`, `claim_entity`. However, the save-to-graph skill only documents `relations.tagged`, `MAKES_CLAIM` (via source_id), and `ABOUT` (via content matching). The save-to-graph skill does not document how it handles the pdf-extraction-specific relation types (`STATES_FACT`, `RELATES_TO`). This means Phase 3a might not process these relations correctly unless the save-to-graph implementation explicitly handles the `relations` object from pdf-extraction.

5. **The `extract_knowledge` method on ProviderChain is not documented.** The KnowledgeExtractor calls `self.provider_chain.extract_knowledge(prompt)` but the SKILL.md only documents `convert_pdf_to_markdown` as a provider method. The user needs to verify that the ProviderChain implementation supports `extract_knowledge`.

6. **No guidance on `text_only` mode vs table extraction.** For financial reports with critical tabular data (P&L, balance sheet, financial metrics), the default `text_only: true` skips table detection. The SKILL.md mentions this (lines 132-134) but does not advise when to turn it off, which is particularly relevant for this use case (JP Morgan analyst report with financial tables).

7. **Source node for PDF has empty title/published.** The `map_pdf_extraction` function (lines 548-558) creates a Source node with `title: ""` and `published: ""`, losing the PDF filename and report date. This makes it harder to identify the source in Neo4j queries.

### Summary Assessment

The skill provides a **workable but incomplete** guide for the full knowledge graph workflow. An experienced user familiar with the codebase can piece together the 3-step workflow from the SKILL.md. However, the critical gap (CLI not wiring KnowledgeExtractor) would block a user who only follows the documented CLI approach. The cross-referencing between pdf-to-markdown and save-to-graph skills works but lacks explicit documentation for the `pdf-extraction` command path end-to-end.

**Confidence level:** With the Python API workaround and awareness of the relation-handling gap, this workflow would successfully extract entities (Indosat, JP Morgan, etc.) and financial data points from the PDF and insert them into Neo4j. The primary risk is in Step 3 where pdf-extraction-specific relation types may not be handled by the save-to-graph implementation as documented.
