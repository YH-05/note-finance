---
allowed-tools: Bash
description: PDF→MarkdownをClaudeエージェント（Sonnet）で変換。ClaudeCodeProvider専用パスで実行し、Geminiフォールバックなし。速度・品質検証用。
skill-preload: pdf-convert-claude
---

# PDF変換 — Claude Code エージェント専用

指定された PDF を `ClaudeCodeProvider`（claude_agent_sdk + claude-sonnet-4-6）で直接変換する。
Gemini フォールバックなし。変換結果は `data/processed/` に出力される。

**引数**: PDF ファイルのパス（絶対パスまたはプロジェクトルートからの相対パス）

## 実行

```bash
uv run python -c "
import sys, time
from pathlib import Path
from pdf_pipeline.services.claude_provider import ClaudeCodeProvider

pdf_path = Path('$ARGUMENTS').resolve()
if not pdf_path.exists():
    print(f'Error: PDF not found: {pdf_path}', file=sys.stderr)
    sys.exit(1)

provider = ClaudeCodeProvider()
if not provider.is_available():
    print('Error: claude_agent_sdk not available', file=sys.stderr)
    sys.exit(1)

print(f'Converting: {pdf_path.name}')
print(f'Provider  : ClaudeCodeProvider (claude-sonnet-4-6)')
start = time.time()
result = provider.convert_pdf_to_markdown(str(pdf_path))
elapsed = time.time() - start

print(f'Done: {len(result):,} chars in {elapsed:.1f}s')
print('---')
print(result[:2000])
print('...(truncated)' if len(result) > 2000 else '')
"
```

!`uv run python -c "
import sys, time
from pathlib import Path
from pdf_pipeline.services.claude_provider import ClaudeCodeProvider

pdf_path = Path('$ARGUMENTS').resolve()
if not pdf_path.exists():
    print(f'Error: PDF not found: {pdf_path}', file=sys.stderr)
    sys.exit(1)

provider = ClaudeCodeProvider()
start = time.time()
result = provider.convert_pdf_to_markdown(str(pdf_path))
elapsed = time.time() - start

print(f'[ClaudeCodeProvider] {pdf_path.name}: {len(result):,} chars / {elapsed:.1f}s')
print('---')
print(result[:3000])
print('...(truncated)' if len(result) > 3000 else '')
"`

## パイプライン全体で変換する場合（chunks.json まで生成）

```bash
uv run python -c "
import sys, time
from pathlib import Path
from pdf_pipeline.config.loader import load_config
from pdf_pipeline.core.chunker import MarkdownChunker
from pdf_pipeline.core.markdown_converter import MarkdownConverter
from pdf_pipeline.core.noise_filter import NoiseFilter
from pdf_pipeline.core.pdf_scanner import PdfScanner
from pdf_pipeline.core.pipeline import PdfPipeline
from pdf_pipeline.services.claude_provider import ClaudeCodeProvider
from pdf_pipeline.services.state_manager import StateManager
from data_paths import get_config_dir, get_path

pdf_path = Path('$ARGUMENTS').resolve()
config = load_config(get_config_dir() / 'pdf-pipeline-config.yaml')
provider = ClaudeCodeProvider()
output_dir = get_path('processed')

pipeline = PdfPipeline(
    config=config.model_copy(update={'output_dir': output_dir, 'input_dirs': [pdf_path.parent]}),
    scanner=PdfScanner(input_dir=pdf_path.parent),
    noise_filter=NoiseFilter(config=config.noise_filter),
    markdown_converter=MarkdownConverter(provider=provider),
    chunker=MarkdownChunker(),
    state_manager=StateManager(output_dir / 'state-claude.json'),
)
source_hash = PdfScanner(input_dir=pdf_path.parent).compute_sha256(pdf_path)
start = time.time()
result = pipeline.process_pdf(pdf_path=pdf_path, source_hash=source_hash)
elapsed = time.time() - start
print(f'Status: {result[\"status\"]} | Chunks: {result.get(\"chunk_count\", 0)} | {elapsed:.1f}s')
print(f'Output: {output_dir / source_hash}')
"
```

## 関連

| リソース | パス |
|---------|------|
| スキル（system_prompt） | `.claude/skills/pdf-convert-claude/SKILL.md` |
| プロバイダ実装 | `src/pdf_pipeline/services/claude_provider.py` |
| バッチ並列変換 | `uv run pdf-pipeline batch --parallel 3 <dir>` |
