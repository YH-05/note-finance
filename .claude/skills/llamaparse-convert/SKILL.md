---
name: llamaparse-convert
description: LlamaParse REST API で PDF を高精度 Markdown に変換するスキル。セルサイドレポート・決算資料・リサーチペーパーなど複雑なレイアウトの PDF に最適。Parse のみ（Index 不要）でクレジット消費を最小化。「LlamaParse で変換」「高精度 PDF 変換」「セルサイドレポートを Markdown に」「PDF を LlamaParse で」と言われたら必ずこのスキルを使うこと。既存の /convert-pdf（Claude Read 方式）で品質が不十分な場合のアップグレードパスとしても使用。
---

# llamaparse-convert

LlamaParse REST API を使って PDF を高精度な Markdown に変換する。

セルサイドレポートや決算プレゼンテーションは表・グラフ・マルチカラムレイアウトが多く、通常の OCR では崩れやすい。LlamaParse の Agentic tier はこうした複雑なドキュメントを忠実に Markdown 化できる。

## クレジット消費

Parse のみ実行し、Index・Extract・Split は使わない。消費は以下のみ:

| Tier | クレジット/ページ | コスト/ページ | 用途 |
|------|-------------------|---------------|------|
| fast | 1 | $0.00125 | テキスト中心のシンプルな文書 |
| cost_effective | 3 | $0.00375 | 日常的な文書処理 |
| **agentic** | **10** | **$0.0125** | **複雑なレイアウト（推奨）** |
| agentic_plus | 45 | $0.05625 | 最高精度が必要な場合 |

Free プランは月 10K クレジット（Agentic で約 1,000 ページ分）。

## 30 ページ超の PDF に関する承認ルール

**30 ページを超える PDF を変換する場合、必ずユーザーの承認を得てから実行すること。**

ページ数取得（Step 3）後、30p 超であれば以下を提示して確認する:

```
この PDF は {PAGE_COUNT} ページあります。
Agentic tier で変換すると約 {PAGE_COUNT * 10} クレジット（${PAGE_COUNT * 0.0125:.2f}）を消費します。
変換を実行しますか？ (y/n)
```

ユーザーが承認した場合のみ Step 4 に進む。承認なしに実行してはならない。

この制約はクレジットの意図しない大量消費を防ぐためにある。月 10K クレジット（Free）の場合、30p 超の PDF 1 本で 3% 以上を消費するため、事前確認が重要になる。

## 使用方法

```bash
# 単一 PDF（Agentic tier）
uv run python .claude/skills/llamaparse-convert/scripts/llamaparse_convert.py /path/to/report.pdf

# Tier 指定
uv run python .claude/skills/llamaparse-convert/scripts/llamaparse_convert.py --tier cost_effective /path/to/report.pdf

# 出力先指定
uv run python .claude/skills/llamaparse-convert/scripts/llamaparse_convert.py -o /output/dir /path/to/report.pdf

# 複数 PDF
uv run python .claude/skills/llamaparse-convert/scripts/llamaparse_convert.py *.pdf
```

## 処理フロー

```
Step 1: PDF 検証（存在・拡張子・サイズ）
Step 2: SHA-256 ハッシュ計算
Step 3: ページ数取得（PyMuPDF）
Step 4: LlamaParse にアップロード (POST /api/parsing/upload)
Step 5: ジョブ完了をポーリング (GET /api/parsing/job/{id})
Step 6: Markdown 結果取得 (GET /api/parsing/job/{id}/result/markdown)
Step 7: report.md + metadata.json を保存
```

## 実行手順（スキルとして使う場合）

### Step 1: 前提確認

```bash
# API キーが .env に設定されていることを確認
grep LLAMA_CLOUD_API_KEY .env
```

### Step 2: スクリプト実行

```bash
uv run python .claude/skills/llamaparse-convert/scripts/llamaparse_convert.py \
  --tier agentic \
  "{PDF_PATH}"
```

### Step 3: 結果確認

スクリプトが以下を出力する:
- `{output_dir}/report.md` — Markdown 変換結果
- `{output_dir}/metadata.json` — 処理メタデータ（SHA-256, ページ数, クレジット見積もり等）

### Step 4: 後処理（任意）

必要に応じて既存の pdf_pipeline インフラと連携:

```bash
# チャンク分割
uv run python -m pdf_pipeline.cli.helpers chunk_and_save "{output_dir}/report.md" "{SHA256}" "{output_dir}"

# ナレッジ抽出 → Neo4j 投入
/pdf-to-knowledge {PDF_PATH}
```

## 出力

### report.md

LlamaParse が生成した Markdown。見出し・表・箇条書き・数値が忠実に保持される。

### metadata.json

```json
{
  "sha256": "a1b2c3d4...",
  "pdf_path": "/absolute/path/to/report.pdf",
  "pdf_name": "report.pdf",
  "pages": 15,
  "converter": "llamaparse",
  "tier": "agentic",
  "credits_per_page": 10,
  "estimated_credits": 150,
  "job_id": "8208cd81-...",
  "processed_at": "2026-03-18T04:00:00+00:00"
}
```

## convert-pdf（Claude Read 方式）との使い分け

| 観点 | convert-pdf | llamaparse-convert |
|------|-------------|-------------------|
| 変換エンジン | Claude Code Read ツール | LlamaParse REST API |
| 外部依存 | なし | LlamaCloud API キー |
| コスト | Claude Code の利用料に含まれる | 10 credits/page（Agentic） |
| 表の精度 | 良好 | 非常に高い |
| 複雑なレイアウト | 30p 分割で対応 | ネイティブ対応 |
| オフライン | 可能 | 不可（API 依存） |
| 推奨用途 | 通常の文書 | セルサイドレポート・複雑な表 |

## 前提条件

1. **LLAMA_CLOUD_API_KEY**: `.env` に設定済み
2. **requests**: HTTP クライアント（`uv add requests` で追加）
3. **PyMuPDF (fitz)**: ページ数取得用（任意、なくても動作する）

## エラーハンドリング

| エラー | 原因 | 対処 |
|--------|------|------|
| `LLAMA_CLOUD_API_KEY が見つかりません` | API キー未設定 | `.env` に `LLAMA_CLOUD_API_KEY=llx-...` を追加 |
| `LlamaParse job failed` | パース失敗 | PDF が破損していないか確認。tier を変更して再試行 |
| `LlamaParse job timed out` | 300 秒超過 | 大きな PDF は分割して実行 |
| `LlamaParse returned empty markdown` | 結果が空 | 画像のみ PDF の可能性。agentic_plus tier で再試行 |
