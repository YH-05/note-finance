# Approach: HSBC レポートPDF → chunks.json 変換

## 1. 実行するコマンド

```bash
uv run pdf-pipeline \
  --output-dir /Users/yuki/Desktop/note-finance/data/processed \
  process \
  "data/sample_report/HSBC ISAT@IJ Indosat Ooredoo Hutchison (ISAT IJ) Buy 3Q mixed – m.pdf"
```

### 補足: 出力先を変更したい場合

タスクでは「chunks.jsonに出力してほしい」とあるが、CLI の出力パスは `{output-dir}/{sha256_hash}/chunks.json` の構造で固定される。デフォルト設定（`data/processed`）を使うと以下のようなパスに出力される:

```
data/processed/{sha256_hash}/chunks.json
```

`--output-dir` オプションで出力ディレクトリ自体は変更可能だが、`chunks.json` というファイル名やハッシュサブディレクトリ構造はパイプラインにハードコードされている。

## 2. 使用する設定

デフォルトの設定ファイル `data/config/pdf-pipeline-config.yaml` を使用:

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
    - "^\\s*\\d+\\s*$"

input_dirs:
  - "data/raw/pdfs"

output_dir: "data/processed"
batch_size: 10
```

CLIの `process` サブコマンドは `pdf_path.parent`（つまり `data/sample_report/`）を `input_dir` として使用するため、`input_dirs` の設定値はこのケースでは上書きされる。

`text_only` はデフォルト `True` なので、Phase 4（テーブル検出・再構築）はスキップされ、処理時間が短縮される。

## 3. パイプラインの処理フロー

1. **Phase 1 (Scan/Hash)**: `PdfScanner.compute_sha256` でPDFのSHA-256ハッシュを計算
2. **冪等性チェック**: `StateManager` で既に処理済みか確認（初回なのでスキップされない）
3. **Phase 2 (テキスト抽出+ノイズフィルタ)**: `FitzTextExtractor` (PyMuPDF) でテキスト抽出 → `NoiseFilter` で空行・ページ番号等を除去
4. **Phase 3 (LLM Markdown変換)**: `ProviderChain` で変換を試行
   - まず `GeminiCLIProvider` でPDFをVision入力としてMarkdown変換を試行
   - 失敗した場合、`ClaudeCodeProvider` にフォールバック
5. **Phase 4 (テーブル処理)**: `text_only=True` (デフォルト) のためスキップ
6. **Phase 5 (チャンキング)**: `MarkdownChunker` でセクション単位のチャンクに分割
7. **保存**: `data/processed/{sha256_hash}/chunks.json` に書き出し

## 4. 期待される出力

### ファイル構造

```
data/processed/
  {sha256_hash}/
    chunks.json
  state.json
```

### chunks.json の形式

```json
[
  {
    "chunk_index": 0,
    "source_hash": "{sha256_hash}",
    "section_title": "Executive Summary",
    "content": "## Executive Summary\n\nThe report highlights...",
    "tables": []
  },
  {
    "chunk_index": 1,
    "source_hash": "{sha256_hash}",
    "section_title": "3Q Results Overview",
    "content": "## 3Q Results Overview\n\n...",
    "tables": []
  }
]
```

HSBCのISATレポートは金融アナリストレポートであり、以下のようなセクションが予想される:
- Rating / Target Price 情報
- 3Q業績サマリー
- 収益・EBITDA分析
- バリュエーション
- 財務諸表（P/L, B/S, CF）
- Disclaimer / Disclosures

`text_only=True` のため `tables` は常に空リスト `[]` になる。

### CLIの標準出力

```
Processing PDF: HSBC ISAT@IJ Indosat Ooredoo Hutchison (ISAT IJ) Buy 3Q mixed – m.pdf
SHA-256: {64文字の16進ハッシュ}
Completed: HSBC ISAT@IJ Indosat Ooredoo Hutchison (ISAT IJ) Buy 3Q mixed – m.pdf
  Chunks extracted: {N}
  Hash: {sha256_hash}
```

## 5. スキル説明の評価

### 明確で十分なガイダンスが提供されている点

1. **CLIコマンドの使い方が明確**: `uv run pdf-pipeline process <pdf_path>` という基本的な使い方が最初に示されており、すぐに実行方法がわかる
2. **3つの利用方法が段階的に説明**: CLI（推奨）、Python API、Markdown変換のみ、と用途に応じた使い方が明示されている
3. **出力形式がJSON例付きで説明**: `chunks.json` の構造が具体例で示されている
4. **設定ファイルの内容と場所が明示**: デフォルトの設定ファイルパスと内容が記載
5. **アーキテクチャ概要が簡潔**: Phase 1-5 のフローが1行で把握できる
6. **トラブルシューティング表**: よくある問題と対処法がテーブル形式で整理
7. **text_onlyモードの説明**: デフォルト動作の説明があり、テーブル処理のスキップが理解できる
8. **関連ファイル一覧**: コードベースのどこを見ればよいかが明確

### 曖昧な点・改善が望ましい点

1. **出力パスのカスタマイズの限界が不明確**: ユーザーが「chunks.jsonに出力して」と言った場合、特定のパスに直接出力する方法がない。CLIは常に `{output-dir}/{sha256}/chunks.json` のパス構造を使うが、この制約はスキルに明記されていない。ユーザーが特定の場所に `chunks.json` だけ欲しい場合は、後から手動でコピーする必要がある。

2. **`--config` オプションの位置**: スキルの使い方セクションでは `uv run pdf-pipeline --config ... process report.pdf` とグループオプションとして示されているが、初見では `process` サブコマンドのオプションと混同しやすい。

3. **LLM APIのコスト・前提条件が未記載**: パイプラインの実行にはGemini CLIまたはClaude Code CLIが利用可能である必要があるが、前提条件（APIキー設定、CLIインストール等）がスキル内に記載されていない。

4. **`state.json` の冪等性挙動の補足不足**: 同じPDFを2回処理するとスキップされるが、再処理したい場合は `reprocess` コマンドを使う必要がある。この情報はトラブルシューティングに記載があるが、メインの使い方セクションにはない。

5. **バッチ処理の方法が不明**: `process` サブコマンドは1つのPDFのみを受け付ける。複数PDFを一括処理するCLI方法（例: ディレクトリ指定）がスキルに記載されていない。`run()` メソッドはPython APIにあるが、CLIからは呼べない。

6. **Knowledge Extraction の有効化方法が不完全**: オプションとして記載されているが、CLIから有効化する方法（設定ファイルの記述方法等）が示されていない。

### 総合評価

スキルは **このタスクを遂行するのに十分なガイダンスを提供している**。CLIコマンド例、設定ファイル、出力形式がすべて明示されており、HSBC PDFの変換タスクに必要な情報は網羅されている。上記の曖昧な点は主にエッジケースやカスタマイズに関するもので、基本的な変換タスクの実行には影響しない。
