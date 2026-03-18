# LlamaIndex / LlamaParse の Claude Code 連携調査

**調査日**: 2026-03-18
**ステータス**: 完了

## 1. LlamaIndex MCP サーバーの調査結果

### 発見された MCP サーバー（6種類）

| パッケージ | 配布先 | 概要 |
|-----------|--------|------|
| `llamacloud-mcp` | [PyPI](https://pypi.org/project/llamacloud-mcp/) / [GitHub](https://github.com/run-llama/llamacloud-mcp) | **Python 公式**。LlamaCloud Index + LlamaExtract（LlamaParse）を MCP 公開 |
| `@llamaindex/mcp-server-llamacloud` | [npm](https://www.npmjs.com/package/@llamaindex/mcp-server-llamacloud) | TypeScript 実装。LlamaCloud インデックスを MCP 公開 (v0.1.3) |
| `@llamaindex/llama-cloud-mcp` | [npm](https://www.npmjs.com/package/@llamaindex/llama-cloud-mcp) | **ホスト型リモート MCP** (v1.8.0)。HTTP で直接接続可能 |
| `mcp-llamaindex-ai` | [GitHub](https://github.com/run-llama/mcp-llamaindex-ai) | Next.js ベース。OAuth 2.1 認証付き MCP サーバー構築 Web UI |
| `llama-index-tools-mcp` | [PyPI](https://pypi.org/project/llama-index-tools-mcp/) | MCP クライアント。任意の MCP サーバーのツールを LlamaIndex エージェントで利用 (v0.4.8) |
| `docling-mcp`（**既設定**） | [PyPI](https://pypi.org/project/docling-mcp/) | **本プロジェクトに設定済み**。LlamaIndex RAG ツール内蔵 |

### llamacloud-mcp（推奨候補 — Python）

- **開発元**: run-llama（LlamaIndex 公式）
- **機能**:
  - LlamaCloud Index をナレッジベースとして Query
  - LlamaExtract Agent による構造化データ抽出
  - LlamaParse による PDF パース（クラウド）
- **認証**: `LLAMA_CLOUD_API_KEY` 環境変数
- **トランスポート**: stdio / streamable-http / SSE
- **導入方法**: `uvx llamacloud-mcp@latest --index "name:description"` で起動

### @llamaindex/llama-cloud-mcp（推奨候補 — ホスト型）

- **最も簡単な導入方法**: HTTP 接続のみで完結
- **Claude Code 連携**: `claude mcp add llamaindex_llama_cloud_mcp_api --header "x-llama-cloud-api-key: API_KEY" --transport http https://llamacloud-prod.stlmcp.com`
- **Code Mode ツールスキーム採用**

## 2. LlamaParse MCP サーバーの調査結果

**LlamaParse は `llamacloud-mcp` に統合されている。** 独立した LlamaParse 専用 MCP サーバーは不要。

- LlamaIndex ブログ: 「**LlamaParse is the document MCP server for your agents**」と明言
- LlamaIndex 公式ドキュメント (developers.llamaindex.ai) のトップに「MCP Server」ボタンがあり、Cursor / Claude への接続 URL をワンクリックでコピー可能
- `llamacloud-mcp` の `--extract-agent` オプションで LlamaExtract（LlamaParse の構造化抽出機能）を MCP ツールとして利用可能

## 3. 既存の docling-mcp との関係

本プロジェクトの `.mcp.json` に既に設定済みの `docling-mcp` は以下のツールセットを提供:

### 現在有効なツール（デフォルト: conversion, generation, manipulation）

| ツール | 機能 |
|--------|------|
| `convert_document_into_docling_document` | PDF/画像をDoclingドキュメントに変換 |
| `convert_directory_files_into_docling_document` | ディレクトリ内の全ファイルを一括変換 |
| `export_docling_document_to_markdown` | DoclingドキュメントをMarkdownにエクスポート |
| `save_docling_document` | ドキュメントをファイルに保存 |
| `page_thumbnail` | ページサムネイル生成 |
| `search_for_text_in_document_anchors` | テキスト検索 |
| `update_text_of_document_item_at_anchor` | テキスト更新 |

### 追加可能なツール（要設定変更）

| ツールセット | 追加ツール | 依存 |
|-------------|-----------|------|
| `llama-index-rag` | `export_docling_document_to_vector_db`, `search_documents` | Milvus, HuggingFace Embedding, OpenAI-like LLM |
| `llama-stack-rag` | `insert_document_to_vectordb` | Llama Stack Server |
| `llama-stack-ie` | `information_extraction` | Llama Stack Server |

### llama-index-rag の設定要件

```bash
# 環境変数
DOCLING_MCP_LI_API_BASE=http://127.0.0.1:1234/v1  # LLM APIエンドポイント
DOCLING_MCP_LI_API_KEY=none
DOCLING_MCP_LI_MODEL_ID=ibm/granite-3.2-8b         # LLMモデル
DOCLING_MCP_LI_EMBEDDING_MODEL=BAAI/bge-base-en-v1.5  # Embedding モデル
```

**注意**: Milvus ベクトルDB（ローカル SQLite モード `./milvus_demo.db`）と HuggingFace Embedding モデルが必要。

## 4. LlamaParse Cloud API 仕様（詳細）

### 基本情報

| 項目 | 内容 |
|------|------|
| API キー取得 | [cloud.llamaindex.ai](https://cloud.llamaindex.ai) でサインアップ |
| API キー形式 | `llx-...`（生成直後に一度だけ表示） |
| 認証ヘッダー | `Authorization: Bearer $LLAMA_CLOUD_API_KEY` |
| ベースURL | `https://api.cloud.llamaindex.ai` |
| 推奨API | **v2**（`/api/v2/parse`） |
| 対応形式 | **130以上**（PDF, DOCX, PPTX, XLSX, HTML, 画像, 音声 等） |

### 主要エンドポイント（API v2）

| 操作 | メソッド | エンドポイント |
|------|---------|---------------|
| ファイルアップロード | POST | `/api/v1/files` |
| パース実行（file_id/URL指定） | POST | `/api/v2/parse` |
| パース実行（ファイル直接） | POST | `/api/v2/parse/upload` |
| ジョブ一覧取得 | GET | `/api/v2/parse?page_size=10&status=COMPLETED` |
| 結果取得 | GET | `/api/v2/parse/{job_id}?expand=markdown` |

### 出力形式（`expand` パラメータ）

| 形式 | 説明 |
|------|------|
| `markdown` | Markdown（表はMarkdown/HTML選択可、ページまたぎ表の自動結合） |
| `text` | プレーンテキスト（空間レイアウト保持オプション） |
| `items` | 構造化JSON（テーブル行データ、画像メタデータ、CSV含む） |
| `metadata` | ページ単位メタデータ（信頼度、スピーカーノート等） |
| `images` | 抽出画像（presigned URLで個別ダウンロード） |

### 料金体系（クレジットベース）

**1,000クレジット = $1.25**

| プラン | 月額 | 含まれるクレジット | 実質ページ数（Agenticティア） |
|--------|------|-------------------|---------------------------|
| **Free** | $0 | 10K | **約1,000ページ/月** |
| Starter | $50 | 40K | 約4,000ページ/月 |
| Pro | $500 | 400K | 約40,000ページ/月 |
| Enterprise | 要見積 | カスタム | カスタム |

**パースティア別クレジット消費（1ページあたり）**:

| ティア | クレジット/ページ | 用途 |
|--------|------------------|------|
| Fast | 1 | AIなしの高速パース |
| Cost-effective | 3 | 基本的な文書 |
| **Agentic** | **10** | **表・チャート混在文書（推奨）** |
| Agentic Plus | 45 | 最高精度 |

### レート制限

| プラン | 制限 |
|--------|------|
| Free | 20リクエスト/分 |
| Starter/Pro | 50リクエスト/5-10秒 |
| Enterprise | 通常の5倍 |

### Python SDK

**新SDK（推奨）**:
```python
from llama_cloud import AsyncLlamaCloud

async def parse_pdf():
    client = AsyncLlamaCloud()  # LLAMA_CLOUD_API_KEY 環境変数を自動読み込み
    file = await client.files.create(file="document.pdf", purpose="parse")
    result = await client.parsing.parse(file_id=file.id, tier="agentic")
    print(result.markdown.pages.markdown)
```

**旧SDK（引き続き動作）**:
```python
from llama_parse import LlamaParse

parser = LlamaParse(
    result_type="markdown",
    extract_charts=True,
    auto_mode=True,
    auto_mode_trigger_on_table_in_page=True,
)
documents = parser.load_data("./report.pdf")
```

## 5. 現在の PDF 変換方式と課題

### 既存実装の概要

| 方式 | 仕組み | 主要ファイル |
|------|--------|-------------|
| `/convert-pdf` | Claude Code Read ツールで直接PDF読み込み → Markdown変換（30p分割） | `.claude/skills/convert-pdf/SKILL.md` |
| `/pdf-to-knowledge` | convert-pdf → Knowledge Extraction → Graph-Queue → Neo4j（4Phase） | `.claude/skills/pdf-to-knowledge/SKILL.md` |
| `/convert-pdf-claude` | ClaudeCodeProvider (Sonnet) で変換 | `src/pdf_pipeline/services/claude_provider.py` |
| `/batch-pdf-claude` | ディレクトリ内の全PDFを並列バッチ変換 | - |
| `docling-mcp` | Docling ライブラリで変換 → Markdown エクスポート | `.mcp.json`（**設定済みだが未活用**） |

### 現在の課題

| 課題 | 詳細 | LlamaParse での改善 |
|------|------|-------------------|
| **画像コンテンツ未対応** | 画像のみの PDF は変換失敗（E005）、チャート・図表スキップ | Vision API + `extract_charts=True` で解決 |
| **複雑な表構造の限界** | 多段ヘッダー、セル結合、行の階層化に弱い | `merge_continued_tables` + `items` 出力で構造保持 |
| **30ページ分割の処理遅延** | 大規模PDF で複数 Read 呼び出し、チャンク境界問題 | PDF 全体を単一処理 |
| **OCR 非対応** | スキャンPDF はテキスト抽出不可 | LlamaParse は OCR 内蔵 |

## 6. 活用シーン比較

| ユースケース | 推奨手段 | 理由 |
|-------------|---------|------|
| **セルサイドレポートPDF変換** | `llamacloud-mcp` (LlamaParse Agentic) | 表・グラフの高精度パース、日本語対応 |
| **決算資料の構造化** | `llamacloud-mcp` (LlamaExtract) | 構造化JSON抽出に特化 |
| **画像・チャート抽出** | `llamacloud-mcp` (LlamaParse) | Vision API + `extract_charts` |
| **大量PDFのバッチ変換** | `docling-mcp` (conversion) | ローカル処理、APIコスト不要 |
| **PDFからのRAG検索** | `docling-mcp` (llama-index-rag) | Milvusベクトル検索、ローカル完結 |
| **簡易PDF変換** | `/convert-pdf`（既存） | 追加設定不要、即利用可能 |

## 7. 導入推奨と優先度

### 優先度1: `llamacloud-mcp` の追加（高ROI）

**方法A: Python (uvx) — ローカル起動**
```jsonc
// .mcp.json に追加
{
  "llamacloud-mcp": {
    "command": "uvx",
    "args": ["llamacloud-mcp@latest"],
    "env": {
      "LLAMA_CLOUD_API_KEY": "${LLAMA_CLOUD_API_KEY}"
    }
  }
}
```

**方法B: ホスト型 — HTTP 接続（最も簡単）**
```bash
claude mcp add llamaindex_llama_cloud_mcp_api \
  --header "x-llama-cloud-api-key: $LLAMA_CLOUD_API_KEY" \
  --transport http \
  https://llamacloud-prod.stlmcp.com
```

**メリット**:
- セルサイドレポート・決算資料の高精度 PDF → Markdown 変換
- 画像・チャート抽出対応（現在の最大の弱点を解消）
- MCP 経由で Claude Code から直接呼び出し可能
- Free プラン: 10K クレジット/月 ≈ **1,000ページ/月（Agentic）**

**コスト**: Free プランで十分。超過時は $1.25/1,000クレジット。

### 優先度2: `docling-mcp` の llama-index-rag 有効化（中ROI）

```jsonc
// .mcp.json のdocling設定を変更
{
  "docling": {
    "command": "uvx",
    "args": [
      "--from=docling-mcp",
      "docling-mcp-server",
      "conversion", "generation", "manipulation", "llama-index-rag"
    ]
  }
}
```

**メリット**: 変換済みPDFのセマンティック検索（ローカル完結）
**課題**: ローカル LLM サーバー（LM Studio 等）と Milvus の追加設定が必要

### 優先度3: `llama-index-tools-mcp` の追加（低ROI）

現状は `llamacloud-mcp` と `docling-mcp` でカバーできるため、追加の必要性は低い。

## 8. CLI ツール設計方針

**結論: MCP サーバーが充実しているため、CLI ツール自作は不要。**

`llamacloud-mcp` と `docling-mcp` の組み合わせで、以下のワークフローが実現可能:

```
PDF → llamacloud-mcp (LlamaParse) → 高精度 Markdown
  → docling-mcp (llama-index-rag) → ベクトル DB 投入 → セマンティック検索
  → pdf-to-knowledge (既存) → Neo4j ナレッジグラフ
```

## 9. 段階的導入プラン

| フェーズ | 内容 | 前提条件 |
|---------|------|---------|
| **Phase 1** | LlamaCloud アカウント作成 & API キー取得 | なし |
| **Phase 2** | `.mcp.json` に `llamacloud-mcp` を追加 | Phase 1 |
| **Phase 3** | セルサイドレポートで `/convert-pdf` vs LlamaParse 比較検証 | Phase 2 |
| **Phase 4** | `/convert-pdf` に LlamaParse フォールバック追加 | Phase 3 の結果次第 |
| **Phase 5** | docling-mcp の llama-index-rag 有効化 | ローカル LLM サーバー構築後 |

## 10. 次のアクション

- [ ] LlamaCloud アカウント作成 & API キー取得（cloud.llamaindex.ai）
- [ ] `.mcp.json` に `llamacloud-mcp` を追加
- [ ] `llamacloud-mcp` での PDF 変換テスト（セルサイドレポートで比較検証）
- [ ] `/convert-pdf` スキルに LlamaParse フォールバック追加を検討
- [ ] docling-mcp の llama-index-rag 有効化は LLM サーバー構築後に検討

## 参考リンク

- [LlamaCloud MCP Documentation](https://developers.llamaindex.ai/python/framework/module_guides/mcp/llamacloud_mcp/)
- [LlamaIndex + MCP Usage](https://developers.llamaindex.ai/python/examples/tools/mcp/)
- [llamacloud-mcp GitHub](https://github.com/run-llama/llamacloud-mcp)
- [LlamaParse API v2 Documentation](https://docs.cloud.llamaindex.ai/llamaparse/getting_started/get_an_api_key)
