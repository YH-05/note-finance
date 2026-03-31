# 議論メモ: ISAT sellside PDF一括変換 & convert-pdfパイプライン改善

**日付**: 2026-03-31
**参加**: ユーザー + AI

## 背景・コンテキスト

バイサイドアナリストとして ISAT_IJ (Indosat Ooredoo Hutchison) の Initial Report 執筆に向け、
sellside リサーチレポートを research-neo4j に格納するパイプラインを整備。
その準備として convert-pdf auto パイプラインの2つのバグを修正し、31本PDFの一括変換を実施した。

## 議論のサマリー

### 課題1: PyMuPDF stdout汚染

`prescan_pdf.py` の `find_tables()` が Python warnings システム経由ではなく、
直接 stdout に以下のプロモメッセージを出力していた:

```
Consider using the pymupdf_layout package for a greatly improved page layout analysis.
```

この出力が `convert_auto prepare` の JSON 出力と混在し、`json.loads()` がパース失敗していた。

**調査した対策（不成功）**:
- `warnings.filterwarnings("ignore", message=".*pymupdf_layout.*")` → Python warning ではないため効果なし
- `os.environ.setdefault("PYMUPDF_QUIET", "1")` → この環境変数は当該メッセージを抑制しない

**採用した対策**:
```python
with contextlib.redirect_stdout(io.StringIO()):
    tables = page.find_tables()
```
修正ファイル: `src/pdf_pipeline/cli/prescan_pdf.py`

### 課題2: Haiku disclaimer分類の API 認証エラー

最初の実装が `anthropic.Anthropic()` を直接インスタンス化していたため、
環境変数 `ANTHROPIC_API_KEY` が未設定の環境でエラーが発生。

**採用した対策**: `Agent(model="haiku")` ツールを使用。
Claude Code 内蔵認証を利用するため API キー設定不要。
6並列の Haiku サブエージェントで31本PDFのdisclaimer判定を実施。

### 課題3: PDF path traceability

Neo4j の Source ノードから元 PDF ファイルへ逆引きできる仕組みが必要。

**実装方針**: 最小変更・関心分離を維持
1. `helpers.py`: `extraction.json` 生成時、`metadata.json` から `pdf_path` を読み込んで JSON レベルで付加（`DocumentExtractionResult` Pydantic モデルは変更しない）
2. `pdf_extraction.py`: `_make_source(**extra)` に `file_path=pdf_path` を渡す

`knowledge-graph-schema.yaml` には `file_path` プロパティが既に定義済みだったため、
Neo4j loader 側の変更は不要。

## 決定事項

1. **PyMuPDF stdout suppression**: `contextlib.redirect_stdout(io.StringIO())` で `find_tables()` をラップ（恒久修正）
2. **Haiku classifier**: `Agent(model="haiku")` ツールを使用（直接 API クライアントは使わない）
3. **PDF path traceability**: `extraction.json` JSON レベルエンリッチメント + `pdf_extraction.py` mapper 経由で実装（Pydantic モデル変更なし）
4. **ISAT PDF変換完了**: 31本 / 268コンテンツページ / 517チャンク

## 修正ファイル一覧

| ファイル | 変更内容 |
|---------|---------|
| `src/pdf_pipeline/cli/prescan_pdf.py` | `find_tables()` を `contextlib.redirect_stdout` でラップ |
| `src/pdf_pipeline/cli/helpers.py` | `extraction.json` に `pdf_path` を JSON レベルで付加 |
| `scripts/mappers/pdf_extraction.py` | `_make_source()` に `file_path=pdf_path` を渡す |

## 変換結果サマリー

| 指標 | 値 |
|-----|-----|
| 対象PDF数 | 31本 |
| 総ページ数 | 405ページ |
| disclaimer判定 | 137ページ |
| コンテンツページ | 268ページ |
| 生成チャンク数 | 517チャンク |
| 前回比（disclaimer除去なし） | 632 → 517（-115チャンク） |
| 出力先 | `/Volumes/NeoData/note-finance-data/processed/` |

## アクションアイテム

- [ ] **[高] pdf-to-knowledge Phase 2-4 で ISAT 31本を research-neo4j に投入**
  - 各 chunks.json を入力として knowledge extraction → graph-queue → Neo4j ingestion
- [ ] **[中] Source ノードの file_path 格納を検証**
  - `MATCH (s:Source) WHERE s.file_path IS NOT NULL RETURN s LIMIT 5`

## 次回の議論トピック

- research-neo4j への ISAT PDFs 投入後の KG 品質確認
- ISAT Initial Report 執筆着手（データ充足度確認）

## 参考情報

- 変換済み PDF マニフェスト: `/tmp/isat_manifest.json`
- 出力ディレクトリ: `/Volumes/NeoData/note-finance-data/processed/`
- 関連ブランチ: `feature/issues-295-298`
