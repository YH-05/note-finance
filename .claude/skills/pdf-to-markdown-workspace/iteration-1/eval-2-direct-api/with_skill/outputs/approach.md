# Approach: PDF to Markdown (Direct Conversion Only)

## Task

Convert `data/sample_report/Jefferies ISAT@IJ ISAT IJ 4Q25 Results Strong Earnings Beat.pdf` to Markdown text. No pipeline, no chunking, no knowledge extraction -- just the conversion.

## Does the Skill Clearly Guide to the Lightweight Approach?

**Yes.** The skill (`SKILL.md`) explicitly documents three methods, and **Method 3** is labeled "Markdown変換のみ（パイプライン不要時）" (Markdown conversion only, when pipeline is not needed). This directly matches the user's request for "変換だけでいい" (just the conversion is fine).

The skill presents it with a concise 4-line code snippet, making it immediately clear that this is the right approach for a conversion-only use case. No ambiguity -- the user does not need to read through Method 1 or Method 2 to find this; it is clearly separated and titled.

## Exact Code/Command I Would Use

```python
from pdf_pipeline.services.gemini_provider import GeminiCLIProvider

provider = GeminiCLIProvider()
markdown = provider.convert_pdf_to_markdown(
    "data/sample_report/Jefferies ISAT@IJ ISAT IJ 4Q25 Results Strong Earnings Beat.pdf"
)

# Save to output file
from pathlib import Path

output_path = Path(
    "/Users/yuki/Desktop/note-finance/.claude/skills/pdf-to-markdown-workspace"
    "/iteration-1/eval-2-direct-api/with_skill/outputs/jefferies_isat_4q25.md"
)
output_path.write_text(markdown, encoding="utf-8")
print(f"Saved {len(markdown)} characters to {output_path}")
```

Alternatively, as a one-liner in the shell:

```bash
cd /Users/yuki/Desktop/note-finance && uv run python -c "
from pdf_pipeline.services.gemini_provider import GeminiCLIProvider
from pathlib import Path
provider = GeminiCLIProvider()
md = provider.convert_pdf_to_markdown('data/sample_report/Jefferies ISAT@IJ ISAT IJ 4Q25 Results Strong Earnings Beat.pdf')
Path('.claude/skills/pdf-to-markdown-workspace/iteration-1/eval-2-direct-api/with_skill/outputs/jefferies_isat_4q25.md').write_text(md, encoding='utf-8')
print(f'Done: {len(md)} chars')
"
```

## What Happens Under the Hood

1. `GeminiCLIProvider.convert_pdf_to_markdown()` resolves the PDF path to an absolute path.
2. It constructs a prompt (`_PDF_TO_MARKDOWN_PROMPT`) instructing the LLM to convert the PDF to structured Markdown while preserving tables, headings, and numerical values.
3. It invokes the `gemini` CLI via `subprocess.run` with flags `-p <prompt> -y` (non-interactive, auto-approve tool calls), embedding the file path in the prompt for Gemini to read.
4. The raw output is sanitized by `_sanitize_output()` which strips MCP warnings, reasoning traces, and code fence wrappers.
5. A validation check ensures the output contains at least one Markdown heading (`# ...`). If not, it raises `LLMProviderError`.
6. The cleaned Markdown string is returned.

If `gemini` CLI is unavailable, the fallback is `ClaudeCodeProvider` (which uses `claude_agent_sdk`). To use the fallback chain automatically, one could use `ProviderChain`:

```python
from pdf_pipeline.services.provider_chain import ProviderChain
from pdf_pipeline.services.gemini_provider import GeminiCLIProvider
from pdf_pipeline.services.claude_provider import ClaudeCodeProvider

chain = ProviderChain([GeminiCLIProvider(), ClaudeCodeProvider()])
markdown = chain.convert_pdf_to_markdown("path/to/report.pdf")
```

But for this task, using `GeminiCLIProvider` directly (as shown in the skill's Method 3) is the simplest approach.

## Expected Output

A Markdown string containing:

- ATX headings (`#`, `##`, `###`) preserving the report's section structure (e.g., "Rating", "Price Target", "Key Takeaways", financial tables)
- Markdown tables for financial data (revenue, EBITDA, subscriber metrics, etc.)
- All numerical values preserved exactly as they appear in the PDF
- Headers, footers, page numbers, disclaimers, and legal boilerplate removed

Typical output length for a sell-side equity research report: 3,000-10,000 characters.

## Issues or Ambiguities in the Skill Instructions

1. **No issues for this use case.** Method 3 is clear, concise, and directly applicable. The skill navigates the user to the lightweight approach without friction.

2. **Minor note on error handling**: The skill's Method 3 snippet does not show error handling (e.g., what to do if `gemini` CLI is not installed). A user unfamiliar with the codebase might not know that `LLMProviderError` is raised on failure, or that `ClaudeCodeProvider` exists as a fallback. However, for a developer following the skill, this is a minor detail -- the `ProviderChain` approach is documented in Method 2, and the troubleshooting section mentions the fallback behavior.

3. **No output path guidance**: Method 3 shows `print(markdown)` but does not suggest saving to a file. For a real task, the user would need to decide where to save the output. This is a trivial gap.

4. **Skill proactively matches this use case**: The skill's `description` field in the frontmatter lists "PDFの変換、マークダウン化、テキスト抽出、レポートPDFの読み込み時にプロアクティブに使用" which means it should be proactively invoked when a user asks for PDF text extraction or Markdown conversion. This is well-designed for discoverability.
