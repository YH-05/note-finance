---
name: pdf-to-markdown
description: PDFファイルをマークダウンに変換するスキル。LLM（Gemini/Claude）によるVision-firstアプローチでPDFの構造を保持したMarkdownを生成し、セクション分割チャンクとして出力する。PDFの変換、マークダウン化、テキスト抽出、レポートPDFの読み込み時にプロアクティブに使用。
---

# pdf-to-markdown スキル

PDFファイルをLLM（Gemini CLI → Claude Code のフォールバック付き）で構造化マークダウンに変換するスキル。金融レポートや決算資料など、表・グラフ・複数カラムを含むPDFを高品質にMarkdown化する。

## 前提条件

- **Gemini CLI**: `gemini` コマンドが利用可能であること（`which gemini` で確認）。未インストールの場合は ClaudeCodeProvider にフォールバック
- **uv**: パッケージマネージャ。`uv run` でパイプラインを実行

## アーキテクチャ

```
PDF → Phase 1 (Scan/Hash) → Phase 2 (テキスト抽出+ノイズフィルタ)
    → Phase 3 (LLM Markdown変換) → Phase 4 (テーブル処理, optional)
    → Phase 5 (チャンキング) → chunks.json
```

LLMプロバイダはフォールバックチェーン構成:
1. **GeminiCLIProvider** (高速・低コスト) — `gemini` CLI でPDFをVision入力
2. **ClaudeCodeProvider** (フォールバック) — `claude` CLI でテキストベース変換

## 使い方

### 方法1: CLIコマンド（推奨）

```bash
# 単一PDFを変換
uv run pdf-pipeline process data/raw/pdfs/report.pdf

# 出力ディレクトリを指定
uv run pdf-pipeline process --output-dir /tmp/output report.pdf

# 設定ファイルを指定
uv run pdf-pipeline --config data/config/pdf-pipeline-config.yaml process report.pdf
```

出力先: `data/processed/{sha256_hash}/chunks.json`

### 方法2: Python API（スクリプトから）

```python
from pathlib import Path
from pdf_pipeline.config.loader import load_config
from pdf_pipeline.core.chunker import MarkdownChunker
from pdf_pipeline.core.markdown_converter import MarkdownConverter
from pdf_pipeline.core.noise_filter import NoiseFilter
from pdf_pipeline.core.pdf_scanner import PdfScanner
from pdf_pipeline.core.pipeline import PdfPipeline
from pdf_pipeline.core.text_extractor import FitzTextExtractor
from pdf_pipeline.services.claude_provider import ClaudeCodeProvider
from pdf_pipeline.services.gemini_provider import GeminiCLIProvider
from pdf_pipeline.services.provider_chain import ProviderChain
from pdf_pipeline.services.state_manager import StateManager

pdf_path = Path("data/raw/pdfs/report.pdf")
output_dir = Path("data/processed")
config_path = Path("data/config/pdf-pipeline-config.yaml")

config = load_config(config_path)
config = config.model_copy(update={
    "output_dir": output_dir,
    "input_dirs": [pdf_path.parent],
})

provider_chain = ProviderChain([GeminiCLIProvider(), ClaudeCodeProvider()])

pipeline = PdfPipeline(
    config=config,
    scanner=PdfScanner(input_dir=pdf_path.parent),
    noise_filter=NoiseFilter(config=config.noise_filter),
    markdown_converter=MarkdownConverter(provider=provider_chain),
    chunker=MarkdownChunker(),
    state_manager=StateManager(output_dir / "state.json"),
    # text_only=True がデフォルト → テーブル検出スキップ
)

source_hash = PdfScanner(input_dir=pdf_path.parent).compute_sha256(pdf_path)
result = pipeline.process_pdf(pdf_path=pdf_path, source_hash=source_hash)
print(f"Status: {result['status']}, Chunks: {result.get('chunk_count', 0)}")
```

### 方法3: Markdown変換のみ（パイプライン不要時）

LLMプロバイダを直接使ってPDFをMarkdownに変換する:

```python
from pdf_pipeline.services.gemini_provider import GeminiCLIProvider

provider = GeminiCLIProvider()
markdown = provider.convert_pdf_to_markdown("path/to/report.pdf")
print(markdown)
```

## 設定ファイル

`data/config/pdf-pipeline-config.yaml`:

```yaml
llm:
  provider: "anthropic"
  model: "claude-opus-4-5"
  max_tokens: 4096
  temperature: 0.0

noise_filter:
  min_chunk_chars: 50
  skip_patterns:
    - "^\\s*$"
    - "^\\d+\\s*$"

input_dirs:
  - "data/raw/pdfs"

output_dir: "data/processed"
batch_size: 10
```

## 出力形式

`chunks.json` の各チャンク:

```json
{
  "chunk_index": 0,
  "source_hash": "abc123...",
  "section_title": "Executive Summary",
  "content": "## Executive Summary\n\nThe report highlights...",
  "tables": []
}
```

## text_only モード（デフォルト）

`PipelineConfig.text_only = True`（デフォルト）では Phase 4 のテーブル検出・再構築をスキップし、処理時間を大幅に短縮する。テーブル処理が必要な場合は設定で `text_only: false` にする。

## Knowledge Extraction → Neo4j 投入

チャンクから Entity/Fact/Claim を LLM で抽出し、Neo4j ナレッジグラフに投入するワークフロー。

**注意**: 現在の CLI (`uv run pdf-pipeline process`) は `KnowledgeExtractor` を配線していないため、`extraction.json` は生成されない。Python API を使う必要がある。

### Step 1: PDF → chunks.json + extraction.json（Python API）

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

pdf_path = Path("data/sample_report/report.pdf")
output_dir = Path("data/processed")
config = load_config(Path("data/config/pdf-pipeline-config.yaml"))
config = config.model_copy(update={"output_dir": output_dir, "input_dirs": [pdf_path.parent]})

provider_chain = ProviderChain([GeminiCLIProvider(), ClaudeCodeProvider()])

pipeline = PdfPipeline(
    config=config,
    scanner=PdfScanner(input_dir=pdf_path.parent),
    noise_filter=NoiseFilter(config=config.noise_filter),
    markdown_converter=MarkdownConverter(provider=provider_chain),
    chunker=MarkdownChunker(),
    state_manager=StateManager(output_dir / "state.json"),
    knowledge_extractor=KnowledgeExtractor(provider_chain=provider_chain),  # これが必要
)

source_hash = PdfScanner(input_dir=pdf_path.parent).compute_sha256(pdf_path)
result = pipeline.process_pdf(pdf_path=pdf_path, source_hash=source_hash)
# → data/processed/{hash}/chunks.json + extraction.json が生成される
```

### Step 2: extraction.json → graph-queue JSON

```bash
python3 scripts/emit_graph_queue.py --command pdf-extraction \
  --input data/processed/{hash}/extraction.json
```

### Step 3: Neo4j 投入

```bash
# /save-to-graph で .tmp/graph-queue/ 内の JSON を投入
```

## トラブルシューティング

| 問題 | 対処 |
|------|------|
| `gemini` CLI が見つからない | `which gemini` で確認。ClaudeCodeProvider にフォールバックする |
| 処理がスキップされる | 既に処理済み。`pdf-pipeline reprocess --hash <hash>` で再処理 |
| 変換品質が低い | ノイズフィルタ設定を調整（`min_chunk_chars` を下げる等） |
| 大きなPDFで失敗 | LLMのトークン上限。`max_tokens` を増やすか、PDFを分割 |

## 関連ファイル

| ファイル | 説明 |
|---------|------|
| `src/pdf_pipeline/cli/main.py` | CLIエントリポイント |
| `src/pdf_pipeline/core/pipeline.py` | パイプラインオーケストレーター |
| `src/pdf_pipeline/core/markdown_converter.py` | Markdown変換コア |
| `src/pdf_pipeline/services/gemini_provider.py` | Gemini CLIプロバイダ |
| `src/pdf_pipeline/services/claude_provider.py` | Claude Codeプロバイダ |
| `src/pdf_pipeline/services/provider_chain.py` | フォールバックチェーン |
| `data/config/pdf-pipeline-config.yaml` | 設定ファイル |
