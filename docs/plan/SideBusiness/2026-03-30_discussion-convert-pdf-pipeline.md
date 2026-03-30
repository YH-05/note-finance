# 議論メモ: /convert-pdf パイプライン再設計

**日付**: 2026-03-30
**参加**: ユーザー + AI

## 背景・コンテキスト

- `/convert-pdf`（Claudeによる直接Vision変換）と `/llamaparse-convert`（LlamaCloud API）が独立スキルとして並立し、出力スキーマが不一致だった
- llamaparse 側は `chunks.json` が生成されず、`metadata.json` のフィールドも異なっていた
- より高速・低コストな第3の変換方式として LiteParse（ローカルNode.jsベース）を検討

## 議論のサマリー

### llamaparse の /convert-pdf への統合

llamaparse を `/convert-pdf --method llamaparse` として統合し、独立スキル `.claude/skills/llamaparse-convert/` を廃止することを決定。スクリプトを `scripts/llamaparse_convert.py` に移動し、`chunks.json` 生成と統一 `metadata.json` スキーマを追加実装した。

### LiteParse 第3方式の設計

LiteParse（MIT、pip install liteparse==1.2.1）を追加。Node.js 18+ が必要。高速ローカルテキスト抽出 → Claude による Markdown 構造化という2段階パイプラインを採用。

### auto メソッドのマルチステージパイプライン設計

```
A) PyMuPDF prescan（画像/表/ページ密度を検出）
B) prescan 結果で liteparse / claude を自動選択
C) Haiku によるディスクレーマーページ分類
D) 大画像ページのみ Claude Vision 読み取り（精度優先）
E) Claude による Markdown 構造化
```

### 表が画像として埋め込まれているケースの対処

PyMuPDF `find_tables()` では画像埋め込み表を検出できないため、`get_images()` + サイズフィルタで大画像候補を検出し、Vision で精読する方式を採用。

### ディスクレーマーページの扱い

セルサイドレポートに付属するディスクレーマーページは Neo4j KG に投入しない。Haiku によるセマンティック分類（MAX_PREVIEW_CHARS=2000）でページ番号を特定し、後続ステップで除外する。

## 決定事項

1. **llamaparse 統合**: `/convert-pdf --method llamaparse` として統合、独立スキル廃止 (`trash/llamaparse-convert/`)
2. **LiteParse 追加**: `scripts/liteparse_convert.py` として実装。page_texts.json を出力
3. **auto パイプライン**: prescan → liteparse/claude 判定 → Haiku disclaimer → Vision → Claude Markdown
4. **Haiku 固定**: `classify_disclaimers.py` で `MODEL = "claude-haiku-4-5-20251001"` をハードコード（設定変更不可）
5. **閾値設定**: 大画像判定 = `width_ratio >= 0.4` AND `area_ratio >= 0.1`、`MAX_PREVIEW_CHARS = 2000`
6. **metadata 統一スキーマ**:
   - 共通フィールド: `sha256`, `pdf_path`, `pages`, `chunks`, `converter`, `processed_at`, `prescan`
   - llamaparse 固有: `pdf_name`, `tier`, `job_id`, `credits_per_page`, `estimated_credits`（他 method では `null`）

## 実装済みファイル

| ファイル | 内容 |
|---------|------|
| `src/pdf_pipeline/cli/prescan_pdf.py` | PyMuPDF prescan（大画像・表検出） |
| `src/pdf_pipeline/cli/classify_disclaimers.py` | Haiku固定 disclaimer分類 |
| `scripts/liteparse_convert.py` | LiteParse テキスト抽出ラッパー |
| `scripts/llamaparse_convert.py` | chunks.json・prescan:null 追加 |
| `src/pdf_pipeline/cli/helpers.py` | metadata 統一スキーマ（converter="claude"） |
| `.claude/skills/convert-pdf/SKILL.md` | 3方式パイプライン設計書 |
| `trash/llamaparse-convert/` | 廃止スキル |

## 閾値キャリブレーション結果（7件実測）

| PDF | table_ratio | large_image_ratio | 推奨method |
|-----|------------|-------------------|-----------|
| HSBC ISAT Sell-side | 0.54 | 0.01 | claude（テキスト表） |
| HSBC TLKM Sell-side | 0.54 | 0.00 | claude |
| Earnings Call Transcript | 0.00 | 0.00 | liteparse |
| TLKM Corporate Presentation | 0.43 | 0.33 | claude + Vision |

現在の閾値は適切と判断。

## アクションアイテム

- [x] auto 方式の orchestration スクリプト実装（convert_auto.py: prepare + build_plan 2コマンド設計）(優先度: 高)
- [x] /convert-pdf CLI エントリーポイントに `--method auto` をデフォルト動作として実装 (優先度: 高)
- [x] /pdf-to-knowledge パイプラインとの統合テスト（disclaimer_pages 除外の動作確認） (優先度: 中)

---

## 追加: アーキテクチャ修正（同日）

### 問題

`classify_disclaimers.py` が `Anthropic()` SDK を直接呼び出す実装になっており、`ANTHROPIC_API_KEY` 環境変数が必要だった。しかし本プロジェクトは Claude Code 自身の Auth（claude_agent_sdk）を使う設計であり、外部 API キーは不要。また Python サブプロセスから `claude_agent_sdk.query()` を呼ぶと CLAUDECODE 環境変数を継承しネストセッションエラーが発生する制約がある。

### 修正内容

**`classify_disclaimers.py` を prompt-only モジュールに再設計**

- Anthropic SDK の依存を完全排除
- `SYSTEM_PROMPT` 定数・`format_prompt()`・`parse_response()` のみ提供
- LLM 呼び出しなし（純粋なユーティリティモジュール）

**disclaimer 分類をスキルレベルの `Agent(model="haiku")` に移動**

- SKILL.md の Step B' で `Agent(model="haiku")` を spawn
- `classify_disclaimers.SYSTEM_PROMPT` と `page_texts.json` の内容を prompt として渡す
- 結果の JSON 配列を `build_plan` に渡す

**`convert_auto.py` を 2 コマンド設計に分割**

```
prepare <pdf> <out> [--no-ocr] [--dpi N]
  → Stage A+B: prescan + LiteParse（API 呼び出しなし）
  → 出力: prescan.json, page_texts.json

build_plan <out> '[5,6,7]'
  → Stage C: gap detection + content text
  → disclaimer_pages はスキルから受け取る
  → 出力: content_text.txt, plan.json
```

スキルの呼び出し順: `prepare` → `Agent("haiku")` → `build_plan`

### 追加決定事項

7. **classify_disclaimers.py prompt-only 化**: Anthropic SDK 依存を排除。`format_prompt()` + `parse_response()` のみ提供。
8. **disclaimer 分類はスキルレベル Agent**: ネストセッション制約により Python サブプロセスから LLM 呼び出し不可。スキル（Claude Code）レベルで `Agent(model="haiku")` を使用。
9. **convert_auto.py 2コマンド設計**: `prepare`（API なし）と `build_plan`（disclaimer_pages 受け取り）に分割。スキルが間に Haiku 呼び出しを挟める設計。

### E2E テスト結果

| PDF | prepare | build_plan |
|-----|---------|------------|
| Nomura Quick Note（10ページ） | ✅ | ✅ |
| TLKM Earnings Transcript | ✅ | ✅ |

## 次回の議論トピック

- disclaimer_pages を Neo4j 投入時にどう除外するか（メタデータで管理 or フィルタリング）
- SKILL.md の Stage B' Agent(model="haiku") 呼び出しの実装詳細確認

## Neo4j ノード

- Discussion: `disc-2026-03-30-convert-pdf-pipeline`
- Decisions: `dec-2026-03-30-001` 〜 `dec-2026-03-30-009`
- ActionItems: `act-2026-03-30-001` 〜 `act-2026-03-30-003`（全完了）
