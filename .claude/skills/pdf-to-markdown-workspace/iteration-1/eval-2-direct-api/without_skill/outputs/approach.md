# Approach: Lightweight PDF-to-Markdown Conversion (Without Skill Guidance)

## What I Found

The codebase has a `pdf_pipeline` package (`src/pdf_pipeline/`) with a full 5-phase pipeline
(scan -> noise filter -> LLM markdown conversion -> table detection -> chunking).
The Markdown conversion step (`MarkdownConverter` in `src/pdf_pipeline/core/markdown_converter.py`)
**requires an LLM provider** (Gemini CLI or Claude) — it is not a local text extraction.

For **text-only extraction without LLM calls**, the relevant component is:

- `FitzTextExtractor` in `src/pdf_pipeline/core/text_extractor.py`

This uses PyMuPDF (`fitz`) to extract raw text page-by-page. It is purely local and does not call any LLM API.

However, `FitzTextExtractor.extract()` returns **plain text**, not Markdown. There is no
intermediate component in the codebase that converts raw extracted text into Markdown without
an LLM. The `MarkdownConverter.convert()` always delegates to `provider.convert_pdf_to_markdown()`.

`pymupdf4llm` (which provides `pymupdf4llm.to_markdown()` for local PDF-to-Markdown) is **not installed**.

## Exact Code/Command I Would Use

### Option A: Raw Text Extraction Only (No LLM, Already Available)

```python
from pathlib import Path
from pdf_pipeline.core.text_extractor import FitzTextExtractor

extractor = FitzTextExtractor()
text = extractor.extract(Path("data/sample_report/Jefferies ISAT@IJ ISAT IJ 4Q25 Results Strong Earnings Beat.pdf"))

output_path = Path("outputs/jefferies_isat_4q25.md")
output_path.write_text(text, encoding="utf-8")
```

One-liner via `uv run`:

```bash
uv run python -c "
from pathlib import Path
from pdf_pipeline.core.text_extractor import FitzTextExtractor

text = FitzTextExtractor().extract(Path('data/sample_report/Jefferies ISAT@IJ ISAT IJ 4Q25 Results Strong Earnings Beat.pdf'))
Path('outputs/jefferies_isat_4q25.md').parent.mkdir(parents=True, exist_ok=True)
Path('outputs/jefferies_isat_4q25.md').write_text(text, encoding='utf-8')
print(f'Extracted {len(text)} chars')
"
```

This gives plain text (not structured Markdown with headings/tables). It is lightweight
and does not require any LLM.

### Option B: Proper Markdown via LLM (Pipeline's Built-in Approach)

The pipeline's `MarkdownConverter` uses `GeminiCLIProvider` (or `ClaudeCodeProvider` as fallback)
to convert the PDF visually into structured Markdown. This is the only way the codebase
produces actual Markdown with headings and table formatting. The CLI command would be:

```bash
uv run pdf-pipeline process "data/sample_report/Jefferies ISAT@IJ ISAT IJ 4Q25 Results Strong Earnings Beat.pdf"
```

But this runs the **full pipeline** (noise filter, table detection, chunking, state management),
not just the conversion.

### Option C: Minimal LLM-Only Conversion (Bypass Pipeline Boilerplate)

To do **just the Markdown conversion** without the rest of the pipeline:

```python
from pathlib import Path
from pdf_pipeline.services.gemini_provider import GeminiCLIProvider

provider = GeminiCLIProvider()
if provider.is_available():
    md = provider.convert_pdf_to_markdown(
        "data/sample_report/Jefferies ISAT@IJ ISAT IJ 4Q25 Results Strong Earnings Beat.pdf"
    )
    Path("outputs/jefferies_isat_4q25.md").write_text(md, encoding="utf-8")
```

This calls the Gemini CLI once and returns structured Markdown. No noise filter, no table
detection, no chunking, no state management. This is the most "lightweight" way to get
real Markdown from the existing codebase.

### Option D: Install pymupdf4llm (Not Currently Available)

```bash
uv add pymupdf4llm
uv run python -c "
import pymupdf4llm
md = pymupdf4llm.to_markdown('data/sample_report/Jefferies ISAT@IJ ISAT IJ 4Q25 Results Strong Earnings Beat.pdf')
from pathlib import Path
Path('outputs/jefferies_isat_4q25.md').write_text(md, encoding='utf-8')
"
```

This would be fully local (no LLM) and produce proper Markdown with headings/tables.
However, `pymupdf4llm` is not currently installed in the project.

## Was the Lightweight Approach Easy to Find?

**Partially.** The codebase is well-structured with clear separation of concerns, so finding
`FitzTextExtractor` for raw text extraction was straightforward. However, the codebase
conflates "Markdown conversion" with "LLM-assisted conversion" — there is **no purely local
PDF-to-Markdown path** built into the pipeline. This means:

1. **If "just text" is acceptable**: `FitzTextExtractor` is easy to find and use directly.
2. **If "real Markdown with structure" is needed without LLM**: No built-in path exists.
   You would need to install `pymupdf4llm` or similar.
3. **If "real Markdown via LLM but without full pipeline" is needed**: You can call
   `GeminiCLIProvider.convert_pdf_to_markdown()` directly, but this is not obvious
   from the CLI — the CLI only exposes the full pipeline (`pdf-pipeline process`).

The lack of a `pdf-pipeline convert-only` subcommand or a simple `pdf-to-markdown` utility
script makes the lightweight approach less discoverable than it could be.

## Expected Output

- **Option A**: Plain text dump of the PDF. No heading markers, no table formatting.
  Just raw text from each page concatenated with newlines. Usable but not structured.
- **Option B**: Full pipeline output in `data/processed/<sha256>/chunks.json` — JSON array
  of chunks, not a single Markdown file.
- **Option C**: A single `.md` file with ATX headings (`# H1`, `## H2`) and Markdown
  tables. Structured and human-readable. Requires LLM API call (~5 minutes via Gemini CLI).
- **Option D**: Local Markdown conversion via pymupdf4llm. Headings inferred from font size,
  tables converted to Markdown. Quality depends on PDF structure; no LLM required.

## Recommended Approach

For the user's stated need ("テキストだけマークダウンとして取り出したい" — "I just want to
extract the text as Markdown"):

**Option C** (direct `GeminiCLIProvider.convert_pdf_to_markdown()` call) is the best fit
if LLM usage is acceptable. It produces proper Markdown with minimal code and no pipeline
boilerplate.

**Option A** (raw `FitzTextExtractor`) is the best fit if no LLM usage is desired, though
the output will be unformatted plain text, not structured Markdown.

## Time Spent and Confusion

**Time**: ~3-5 minutes of exploration.

**Confusion points**:
1. The name `MarkdownConverter` suggests a local conversion utility, but it actually wraps
   an LLM call. The real local extraction is `FitzTextExtractor`, which does not produce
   Markdown.
2. The CLI (`pdf-pipeline`) only exposes the full pipeline. There is no `convert` or
   `extract-text` subcommand for a single-step operation.
3. `pymupdf4llm` (the natural local PDF-to-Markdown tool for PyMuPDF users) is not installed,
   even though `pymupdf` is. This gap is not documented anywhere.
