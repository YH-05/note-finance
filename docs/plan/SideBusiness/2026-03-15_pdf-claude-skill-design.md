# 議論メモ: PDF変換Claude専用スキル・ワークフロー設計

**日付**: 2026-03-15
**参加**: ユーザー + AI

## 背景・コンテキスト

- Gemini CLI ベースのPDF変換パイプラインが不安定（subprocess失敗、精度低、大量変換で時間がかかり失敗）
- 既存のコマンド・スキルが散らかって把握しづらくなっている
- PDF→Markdown→ナレッジグラフの一連のワークフローを整理・再構築したい

## 議論のサマリー

### 1. Gemini → Claude 一本化
- Gemini CLI の問題: subprocess呼び出し失敗、変換精度が低い、大量処理で不安定
- Claude Code ベースに完全移行する方針を決定

### 2. ハイブリッド戦略
- **方式B**（メインプロセスで直接 Read ツールでPDF読み込み→変換）を先に実装・安定性確認
- その後 **方式A**（claude_agent_sdk でサブエージェントをスポーンしてバッチ対応）を実装
- 理由: 段階的にリスクを低減

### 3. 出力形式 γ（3ファイル構成）
- `report.md` — 人間確認・デバッグ用の生Markdown
- `chunks.json` — スキル2（ナレッジグラフ投入）への機械処理用入力
- `metadata.json` — SHA-256フルハッシュ、元PDFパス、変換日時等

### 4. 出力パス: ミラー + ファイル名 + 短ハッシュ8文字
- 例: `processed/TLKM_IJ/company_docs/Corporate_Presentation/TLKM_1Q25_a1b2c3d4/`
- 元PDFのディレクトリ構造をミラーリング
- ファイル名で直感的に対応がわかる
- 短ハッシュ（SHA-256先頭8文字）で衝突を完全回避

### 5. ページ分割: 30ページ単位
- Sonnet: 入力200Kトークン、出力64Kトークン
- 金融PDF: 1ページ ≈ 1,500-2,000入力トークン、500-1,000出力トークン
- 理論上は60-100ページまで可能だが、安全策として30ページを採用
- 30p以下 → そのまま変換、30p超 → 30p単位で Read → 変換 → マージ
- 対象データの分布:
  - sellside/memo/プレゼン（3-43p）: 分割不要（大多数）
  - Financial Report（149-183p）: 5-6分割
  - Annual Report（450-472p）: 15-16分割

### 6. コマンド体系（スキル分離 + ワークフロー統合）
- `/convert-pdf` — スキル1: 単一PDF → Markdown変換（方式B）
- `/convert-pdf-batch` — スキル1拡張: バッチ変換（方式A、後で実装）
- `/save-to-graph` — スキル2: 既存スキル（chunks.json → Neo4j）
- `/pdf-to-knowledge` — ワークフロー: スキル1 → スキル2 一括実行
- デバッグのためスキル1とスキル2は独立して呼び出し可能

## 決定事項

1. Gemini CLI 廃止、Claude Code 一本化
2. ハイブリッド戦略: 方式B先行 → 方式Aでバッチ対応
3. 出力形式γ: report.md + chunks.json + metadata.json
4. 出力パス: ミラー + ファイル名 + 短ハッシュ8文字
5. 分割単位: 30ページ
6. スキル分離: /convert-pdf と /save-to-graph を独立、/pdf-to-knowledge で一括

## アクションアイテム

- [ ] スキル1 `/convert-pdf` の設計・実装（方式B: メインプロセス直接） (優先度: 高)
- [ ] 既存コマンド・スキルの棚卸し・整理 (優先度: 高)
- [ ] ワークフロー `/pdf-to-knowledge` の設計・実装 (優先度: 中)
- [ ] スキル1拡張 `/convert-pdf-batch` の実装（方式A: サブエージェント） (優先度: 中)
- [ ] 既存 GeminiCLIProvider の段階的廃止計画 (優先度: 低)

## 次回の議論トピック

- 方式Bで実際にPDF変換を実行し、品質・安定性を検証
- 30ページ分割のマージ品質（セクション境界での整合性）
- Knowledge Extraction（スキル2）のインプット仕様

## 参考情報

- 既存インフラ: `src/pdf_pipeline/` パッケージ（Phase 1-5）
- 既存スキル: `pdf-to-markdown`, `pdf-convert-claude`
- 既存コマンド: `/convert-pdf-claude`, `/batch-pdf-claude`
- PDFデータ: `/Volumes/NeoData/note-finance-data/raw/pdfs/`（4カテゴリ、100+ファイル）
- Neo4j: Discussion `disc-2026-03-15-pdf-claude-skill`, Decision `dec-2026-03-15-001` ~ `005`
