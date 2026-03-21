# 議論メモ: LiteParse 技術調査と PDF パイプラインへの応用可能性

**日付**: 2026-03-21
**参加**: ユーザー + AI

## 背景・コンテキスト

本プロジェクトでは PDF → Markdown 変換を多用しており、以下の3つのパイプラインが存在する:

| パイプライン | 変換エンジン | 用途 |
|-------------|-------------|------|
| `convert-pdf` | Claude Code Read ツール | 通常の文書（Method B） |
| `llamaparse-convert` | LlamaParse REST API | セルサイドレポート等の複雑なレイアウト |
| `pdf-to-knowledge` | 上記 + KG 投入 | PDF → MD → extraction → Neo4j の全工程 |

LlamaIndex が LiteParse をオープンソース公開したため、本プロジェクトでの応用可能性を調査した。

**調査対象**: https://www.llamaindex.ai/blog/liteparse-local-document-parsing-for-ai-agents

## LiteParse 技術概要

| 項目 | 内容 |
|------|------|
| 開発元 | LlamaIndex（LlamaParse のオープンソースコア部分） |
| 実装言語 | TypeScript ネイティブ（Python は CLI ラッパー） |
| 実行環境 | 完全ローカル、クラウド不要、Python 依存なし |
| 対応形式 | PDF, DOCX, XLSX, PPTX, 画像（PNG/JPG/TIFF） |
| OCR | Tesseract.js 内蔵 + 外部 OCR サーバー（PaddleOCR/EasyOCR）対応 |
| **出力形式** | **プレーンテキスト（空間レイアウト保持）、スクリーンショット、バウンディングボックス** |
| 設計思想 | 構造検出（表→Markdown変換）ではなく空間レイアウト保持 |
| GitHub | https://github.com/run-llama/liteparse |
| ベンチマーク | PyPDF/PyMuPDF/Markitdown より QA 精度で優位、VLM ベースツールとは比較対象外 |

### コア設計思想

「テーブルを検出して Markdown に変換する」のではなく、テキストの空間的位置関係をそのまま ASCII グリッドに投影するアプローチ。LLM がそのまま理解できるため構造解析は不要、という割り切り。

出力例:
```
Name        Age    City
John        25     NYC
Jane        30     LA
```

### LiteParse vs LlamaParse の公式見解

- **LiteParse**: コーディングエージェントとリアルタイムパイプライン向け。速度・シンプルさ・ローカル実行。
- **LlamaParse**: 複雑なドキュメント処理向け。高精度、構造化出力（Markdown テーブル、JSON スキーマ）、クラウドサービス。

## 議論のサマリー

### 論点1: 直接採用の可否

**結論: 現時点では直接採用は困難**

3つの理由:

1. **出力形式の不一致（致命的）**: LiteParse はプレーンテキスト出力。下流パイプライン（`MarkdownChunker` → `extraction.json` → `graph-queue` → Neo4j）は構造化 Markdown（ATX 見出し・Markdown テーブル）を前提としている。`MarkdownChunker`（`src/pdf_pipeline/core/chunker.py`）は `^(#{1,6})\s+(.+)$` の正規表現で見出しを検出してセクション分割しているため、プレーンテキストでは文書全体が1チャンクになる。

2. **金融レポートの要件との不適合**: セルサイドレポートや決算資料では、表の正確な構造（ヘッダー行、数値列の右寄せ等）が必要。

3. **エコシステムの不一致**: プロジェクトは Python（uv）ベース。LiteParse は TS ネイティブ。

### 論点2: LiteParse → 後処理で Markdown 化 → 下流パイプライン案

**技術的には可能だが、メリットが薄い。**

処理フローの比較:
```
現行:  PDF → [Claude Read] → 構造化 Markdown → chunker → KG
提案:  PDF → [LiteParse] → プレーンテキスト → [LLM後処理] → 構造化 Markdown → chunker → KG
```

LLM 呼び出しが結局必要になり、LiteParse の「高速・ローカル」メリットが相殺される。現行の `convert-pdf` は Claude Read で PDF を直接読みながら Markdown を同時生成しているので、1ステップで済んでいる。

**唯一意味があるケース**: 画像のみ PDF（スキャン文書）。現行パイプラインは E005 エラーで失敗するが、LiteParse の OCR → テキスト抽出 → LLM で Markdown 化、という経路なら救える可能性がある。

### 論点3: TypeScript 対応で解決するか

**言語の問題ではなく、出力形式の問題なので解決しない。**

LiteParse 自体が意図的に Markdown 出力を非サポートとしている。構造化出力が欲しければ LlamaParse を使え、というのが LlamaIndex 側の公式見解。

## 決定事項

1. **LiteParse の直接採用は見送り**: 出力形式がプレーンテキストで、構造化 Markdown が必要な下流パイプラインと不適合
2. **現行パイプラインを維持**: `convert-pdf`（通常文書） + `llamaparse-convert`（複雑レイアウト）の二段構えを継続
3. **限定的活用可能性を認識**: OCR フォールバック層、PDF 事前トリアージとしての活用は将来的に検討可能

### 論点4: LiteParse で表・図を無視して本文テキストだけ取得できるか

**結論: LiteParse 単体ではできない。**

LiteParse の API を詳細調査（GitHub README + API ドキュメント types.ts）した結果:

- 出力に `text`（ページ全体）と `textItems[]`（個別テキスト要素）がある
- 各 `textItem` には座標（x, y, w, h）、`fontName`、`fontSize` が付与される
- **しかし `contentType`（表/本文/図キャプション等）の区別機構は存在しない**
- 設計思想として「構造検出をしない」ことが明示されている

`--format json` の textItem 座標・フォント情報を使えば、後処理スクリプトでヒューリスティクスを組める（等間隔列配置→表、小フォント→脚注、等）が、PDF レイアウトに強く依存し汎用的ではない。

**本文のみ抽出が必要な場合は、現行の Claude Read 方式がマルチモーダル理解で指示に直接従えるため最適。**

## アクションアイテム

- [ ] LiteParse の Markdown 出力モード追加をウォッチする（優先度: 低、期限なし）
- [ ] 画像のみ PDF（E005 エラー）の OCR フォールバックとして LiteParse を検討する（優先度: 低）
- [ ] LiteParse のスクリーンショット機能（`lit screenshot`）を Claude Vision との組み合わせで検証する（優先度: 低）

## 次回の議論トピック

- PDF 変換パイプライン全体の精度ベンチマーク（convert-pdf vs llamaparse-convert vs LiteParse+後処理）
- 画像のみ PDF のハンドリング戦略（現在は E005 エラーで中断）

## 参考情報

- LiteParse ブログ記事: https://www.llamaindex.ai/blog/liteparse-local-document-parsing-for-ai-agents
- LiteParse GitHub: https://github.com/run-llama/liteparse
- LiteParse ベンチマーク: https://huggingface.co/datasets/llamaindex/liteparse_bench_small
- LiteParse エージェントスキル: https://github.com/run-llama/llamaparse-agent-skills
- 本プロジェクトの MarkdownChunker: `src/pdf_pipeline/core/chunker.py`（ATX 見出しベースのセクション分割）
- 本プロジェクトの convert-pdf スキル: `.claude/skills/convert-pdf/SKILL.md`
- 本プロジェクトの llamaparse-convert スキル: `.claude/skills/llamaparse-convert/SKILL.md`
- LiteParse API ドキュメント: https://developers.llamaindex.ai/liteparse/api/
- LiteParse types.ts: https://github.com/run-llama/liteparse/blob/main/src/core/types.ts
