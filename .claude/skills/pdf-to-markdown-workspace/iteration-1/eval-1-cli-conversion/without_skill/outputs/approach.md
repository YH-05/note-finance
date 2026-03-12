# PDF to Markdown Conversion Approach (Without Skill Guidance)

## Exact Command

```bash
cd /Users/yuki/Desktop/note-finance

uv run pdf-pipeline process "data/sample_report/HSBC ISAT@IJ Indosat Ooredoo Hutchison (ISAT IJ) Buy 3Q mixed – m.pdf"
```

This uses the `pdf-pipeline` CLI entry point registered in `pyproject.toml` (`pdf_pipeline.cli.main:cli`), which exposes a `process` subcommand that accepts a PDF file path.

### Output Directory Override (if needed)

To write chunks.json to a specific location instead of the default `data/processed/`:

```bash
uv run pdf-pipeline \
  --output-dir /Users/yuki/Desktop/note-finance/.claude/skills/pdf-to-markdown-workspace/iteration-1/eval-1-cli-conversion/without_skill/outputs \
  process "data/sample_report/HSBC ISAT@IJ Indosat Ooredoo Hutchison (ISAT IJ) Buy 3Q mixed – m.pdf"
```

## Configuration

The pipeline uses `data/config/pdf-pipeline-config.yaml` by default (can be overridden with `--config`).

Current configuration:

| Parameter | Value |
|-----------|-------|
| LLM provider | `anthropic` |
| LLM model | `claude-opus-4-5` |
| Max tokens | `4096` |
| Temperature | `0.0` |
| Noise filter min_chunk_chars | `50` |
| Noise filter skip_patterns | blank lines, page numbers, isolated numbers |
| text_only | `True` (default; skips table detection/reconstruction) |
| Output dir | `data/processed` |

**Note on `text_only` default**: The `PipelineConfig` model defaults `text_only=True`, which means table detection (Phase 4) is skipped. The YAML config file does not explicitly set this field, so the default applies. To enable table detection, add `text_only: false` to the YAML config or modify it.

### LLM Provider Chain

The CLI wires up a `ProviderChain` with fallback order:
1. **GeminiCLIProvider** -- invokes the `gemini` CLI binary via subprocess (requires `gemini` CLI installed)
2. **ClaudeCodeProvider** -- fallback if Gemini is unavailable

The Markdown conversion (Phase 3) sends the full PDF to the LLM with a prompt instructing it to output structured Markdown with ATX headings and Markdown tables.

## Expected Output

Output is written to `{output_dir}/{sha256_of_pdf}/chunks.json`.

The `chunks.json` file contains a JSON array where each element is a chunk object:

```json
[
  {
    "source_hash": "<sha256>",
    "chunk_index": 0,
    "section_title": null,
    "content": "Text content of the section...",
    "tables": [
      {
        "page_number": 1,
        "bbox": [x0, y0, x1, y1],
        "cells": [...],
        "headers": [...],
        "row_count": null,
        "col_count": null,
        "image_path": ".tmp/table_images/table_p1_t0_xxxx.png"
      }
    ]
  },
  {
    "source_hash": "<sha256>",
    "chunk_index": 1,
    "section_title": "Section Title",
    "content": "## Section Title\n| Column1 | Column2 |\n...",
    "tables": [...]
  }
]
```

## Pipeline Phases

The `process_pdf` method executes the following phases in order:

1. **Idempotency check** -- StateManager checks if the PDF hash is already "completed"; if so, it is skipped.
2. **Phase 2: Text extraction + Noise filtering** -- PyMuPDF (`FitzTextExtractor`) extracts raw text; `NoiseFilter` removes boilerplate using regex patterns and min character thresholds.
3. **Phase 3: PDF to Markdown conversion** -- `MarkdownConverter` sends the PDF file to the LLM provider (Gemini CLI or Claude) to produce structured Markdown. This is the LLM-dependent step.
4. **Phase 4: Table detection/reconstruction** -- `TableDetector` + `TableReconstructor` (skipped when `text_only=True`).
5. **Chunking** -- `MarkdownChunker` splits the Markdown into section-level chunks.
6. **Save** -- Writes `{output_dir}/{source_hash}/chunks.json`.

## How Long It Took to Find the Right Approach

Approximately 2-3 minutes of exploration:
1. Listed the `src/pdf_pipeline/` directory structure (~10 seconds)
2. Read `cli/main.py` to find the CLI entry point and `process` subcommand (~30 seconds)
3. Read `core/pipeline.py` to understand the pipeline phases and output format (~30 seconds)
4. Read `config/loader.py` and `types.py` to understand the configuration model (~30 seconds)
5. Checked `data/config/pdf-pipeline-config.yaml` for the actual config (~10 seconds)
6. Checked `pyproject.toml` for the CLI entry point name (`pdf-pipeline`) (~10 seconds)
7. Read an existing `chunks.json` to confirm the output format (~10 seconds)

## Confusion or Dead Ends

None significant. The codebase is well-organized:

- The CLI is in a standard Click-based structure under `src/pdf_pipeline/cli/main.py`.
- The entry point is clearly registered in `pyproject.toml` as `pdf-pipeline`.
- The `process` subcommand directly accepts a PDF path and handles everything automatically.
- The only consideration is the `text_only` default: since the YAML config does not set `text_only`, the Pydantic default of `True` applies, meaning table detection (Phase 4) is skipped. This is a subtle detail that could be missed -- a user wanting full table extraction would need to add `text_only: false` to the YAML config. However, even with `text_only=True`, the LLM-generated Markdown may still contain table syntax if the LLM converts tables in the PDF to Markdown table format during Phase 3.

One minor observation: the existing processed output in `data/processed/` shows a different PDF (JP Morgan's, based on "4Q25" and "IOH" content in the chunks), confirming the pipeline has been successfully run before.
