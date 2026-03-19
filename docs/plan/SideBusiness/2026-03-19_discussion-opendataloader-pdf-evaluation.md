# 議論メモ: opendataloader-pdf リポジトリ調査・評価

**日付**: 2026-03-19
**参加**: ユーザー + AI

## 背景・コンテキスト

TODO タスク「opendataloader-pdf リポジトリ調査」として、本プロジェクトの PDF 変換パイプラインとの比較・活用可能性を調査。

## リポジトリ概要

| 項目 | 内容 |
|------|------|
| リポジトリ | `opendataloader-project/opendataloader-pdf` |
| 開発元 | Hancom（韓国） |
| ライセンス | Apache 2.0（v2.0以降） |
| Star | 4,301 |
| 最終コミット | 2026-03-18（非常にアクティブ） |
| コア技術 | Java（コアエンジン）+ Python/Node.js ラッパー |
| バージョン | v0.1.0（初期リリース） |

## 主要機能

- **ローカルモード**: GPU不要、CPU で 0.05秒/ページ
- **ハイブリッドモード**: docling + EasyOCR で総合スコア 0.90
- **出力形式**: Markdown, HTML, JSON（バウンディングボックス付き）
- **プロンプトインジェクション防止フィルタ**内蔵
- **LangChain統合**パッケージあり
- **バッチ処理**: 20+ ページ/秒のスループット

## ベンチマーク（200個の実世界PDF）

| エンジン | 総合スコア | テーブル精度 | 速度(s/p) |
|---------|-----------|----------|----------|
| **opendataloader [hybrid]** | **0.90** | **0.93** | 0.43 |
| docling | 0.86 | 0.89 | 0.73 |
| marker | 0.83 | 0.81 | 53.93 |
| opendataloader [local] | 0.72 | 0.49 | 0.05 |
| pymupdf4llm | 0.57 | 0.40 | 0.09 |

## 現行パイプラインとの比較

| 観点 | convert-pdf（現行） | llamaparse-convert（現行） | opendataloader-pdf |
|------|---------------------|--------------------------|-------------------|
| 方式 | Claude Code Read（Vision） | LlamaCloud REST API | Java エンジン + docling |
| コスト | 0（Claude Code内蔵） | API クレジット消費 | 0（OSS） |
| テーブル精度 | 中 | 高（agentic tier） | 高（ハイブリッドモード） |
| 速度 | 30p分割で安定 | API依存（タイムアウト300s） | 0.05s/ページ（ローカル） |
| オフライン | 可 | 不可 | 可 |
| 依存 | Claude Code環境 | LLAMA_CLOUD_API_KEY | Java 21+（JARバンドル） |
| Neo4j連携 | pdf-to-knowledge経由 | なし | なし（自前で接続要） |

## 決定事項

1. **即時導入は不要** — 現行パイプライン（convert-pdf + llamaparse）で十分カバーできている
2. **ウォッチリストに追加** — テーブル精度・速度面で有望。v1.0到達後に再評価

## メリット・デメリット

### メリット
- 高速・無料（ローカルで0.05s/ページ、API費用ゼロ）
- テーブル精度が高い（ハイブリッドモードで0.90スコア）
- Java JARバンドル（pip install だけで使える）
- Apache 2.0（商用利用に制約なし）
- 活発な開発（2026年3月時点でほぼ毎日コミット）

### デメリット
- Java 21+ 依存（JVMが必要）
- ハイブリッドモードの追加依存（docling + EasyOCR、重い）
- 既存パイプラインとの統合コスト
- ナレッジグラフ連携なし（pdf-to-knowledge相当の機能なし）
- v0.1.0（初期リリース、まだ安定版ではない）

## アクションアイテム

- [ ] opendataloader-pdf v1.0リリース時に再評価（優先度: 低）
  - llamaparseコスト削減代替として
  - セルサイドレポート処理の高速パスとして

## 参考情報

- リポジトリ: https://github.com/opendataloader-project/opendataloader-pdf
- ホームページ: https://opendataloader.org
- LangChain統合: `pip install langchain-opendataloader-pdf`
- 既存PDF変換パイプライン: `.claude/skills/convert-pdf/`, `.claude/skills/llamaparse-convert/`, `.claude/skills/pdf-to-knowledge/`
