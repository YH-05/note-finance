# Project 11: PDF-to-Claude Conversion (Method B)

## メタ情報

| 項目 | 値 |
|------|-----|
| GitHub Project | [#79](https://github.com/users/YH-05/projects/79) |
| 作成日 | 2026-03-15 |
| ステータス | Planning |
| タイプ | workflow (skill + command + pipeline拡張) |
| Issues | #95 - #106 (12件) |

## 概要

Gemini CLI ベースの PDF 変換パイプラインを Claude Code 一本化し、Method B（メインプロセス直接Read方式）で安定性・精度を向上させる。

## 背景

- Gemini CLI の問題: subprocess 呼び出し失敗、変換精度が低い、大量処理で不安定
- 既存コマンド・スキルが散らかって把握しづらい
- PDF → Markdown → ナレッジグラフの一連のワークフローを整理・再構築

## アーキテクチャ

### Method B: スキル主導の変換

```
User: /convert-pdf <pdf_path>
  │
  ▼
SKILL.md (orchestrator)
  ├── Step 1-5: Python helpers (uv run python -m) → ハッシュ、冪等性、ページ数
  ├── Step 6: Read tool → PDF直接読込 → Markdown変換 (30p分割対応)
  ├── Step 7: Write tool → report.md 出力
  └── Step 8-10: Python helpers → chunks.json, metadata.json, 状態記録
```

### 出力形式γ (3ファイル構成)

| ファイル | 用途 |
|---------|------|
| `report.md` | 人間確認・デバッグ用の生Markdown |
| `chunks.json` | ナレッジグラフ投入用の機械処理入力 |
| `metadata.json` | SHA-256ハッシュ、元PDFパス、変換日時等 |

### 出力パス

```
{DATA_ROOT}/processed/{mirror_subpath}/{stem}_{hash8}/
```

## Wave構成

### Wave 1: Foundation (並列可)

| Issue | タイトル | サイズ |
|-------|---------|--------|
| #95 | compute_sha256_standalone関数追加 | S |
| #96 | page_chunk_sizeパラメータ追加 | S |
| #97 | Method B用Pythonヘルパーモジュール | M |
| #98 | cli/helpers.pyユニットテスト | M |

### Wave 2: Core Skill (順次)

| Issue | タイトル | サイズ |
|-------|---------|--------|
| #99 | **/convert-pdf スキル実装（主要成果物）** | L |
| #100 | /convert-pdf コマンド作成 | S |

**Validation Gate**: 小(5p)・中(20p)・大(150p+) PDFで動作検証

### Wave 3: Integration (並列可)

| Issue | タイトル | サイズ |
|-------|---------|--------|
| #101 | ナレッジ抽出ヘルパー関数追加 | M |
| #102 | /pdf-to-knowledge ワークフロースキル | L |
| #103 | /pdf-to-knowledge コマンド作成 | S |

### Wave 4: Cleanup (並列可)

| Issue | タイトル | サイズ |
|-------|---------|--------|
| #104 | レガシーコマンド・スキル削除 | S |
| #105 | CLAUDE.md・ドキュメント更新 | S |
| #106 | GeminiCLIProvider非推奨化マーキング | S |

## 決定事項

1. Gemini CLI 廃止、Claude Code 一本化
2. ハイブリッド戦略: 方式B先行 → 方式Aでバッチ対応（別プロジェクト）
3. 出力形式γ: report.md + chunks.json + metadata.json
4. 出力パス: ミラー + ファイル名 + 短ハッシュ8文字
5. 分割単位: 30ページ
6. スキル分離: /convert-pdf と /save-to-graph を独立、/pdf-to-knowledge で一括

## リスク

| リスク | 重要度 | 対策 |
|--------|--------|------|
| Read toolのPDF読み取り品質 | HIGH | 既存SKILL.mdで実証済み、Method A がフォールバック |
| 30p境界マージ品質 | MEDIUM | 重複見出し除去ロジック、V1は許容 |
| 出力パス既存パイプラインとの衝突 | MEDIUM | state.json共有で冪等性確保 |

## 関連

- 設計ドキュメント: `docs/project/project-11/original-plan.md`
- 既存パッケージ: `src/pdf_pipeline/`
- 既存スキル: `.claude/skills/pdf-convert-claude/SKILL.md`
