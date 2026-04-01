# 議論メモ: extract_knowledge SDK移行 — Gemini CLI撤廃・ClaudeCodeProvider全面書き換え

**日付**: 2026-03-31
**参加**: ユーザー + AI

## 背景・コンテキスト

ISAT sellside PDF パイプライン Phase 2（知識抽出）が動作していなかった。
前セッションがクラッシュした状態から再開し、原因を調査した結果、
以下の2つのプロバイダーが両方とも機能不全だったことが判明：

1. **GeminiCLIProvider**: 外側の `{` なしで `"entities": [...], ...}` という不正JSON を返していた。
   また修正後も Extra data エラーが発生し続けた。
2. **ClaudeCodeProvider**: `claude_agent_sdk.extract_knowledge()` という存在しないメソッドを呼び出していた。

ユーザーの判断：Gemini CLI は撤廃し、claude_agent_sdk.query() ベースで ClaudeCodeProvider を書き直す。

## 議論のサマリー

### 主要な論点

1. **どの処理で Gemini を使用しているか** → `_build_default_provider_chain()` で `GeminiCLIProvider` が先頭プロバイダーとして使用されていた
2. **extract_knowledge の詳細フロー** → `KnowledgeExtractor._extract_single()` → `ProviderChain.extract_knowledge()` → `provider.extract_knowledge()` の呼び出しチェーン
3. **claude_agent_sdk の使い方** → `sdk.query(prompt, options)` で非同期ジェネレーターを consume し、`AssistantMessage.TextBlock` を結合

### 技術的な問題と解決策

| 問題 | 解決策 |
|------|--------|
| GeminiCLIProvider の不正JSON出力 | 廃止（trash/ 移動） |
| ClaudeCodeProvider が存在しないSDKメソッドを呼出 | `sdk.query()` を直接使用するよう全面書き換え |
| nested session エラー（CLAUDECODE=1 検出） | `env={'CLAUDECODE': '', 'CLAUDE_CODE_ENTRYPOINT': 'sdk-py'}` でオーバーライド |
| asyncio cleanup エラー（GeneratorExit） | フルイテレーター消費（break なし）で解消 |
| project context の混入（KGノード名等が抽出に混入） | 抽出プロンプトを system prompt に移動、`setting_sources=[]` で分離 |
| JSON Extra data エラー | `_parse_json_robust()` でブレース深度カウントによるトリム |

## 決定事項

### dec-2026-03-31-gemini-removal
GeminiCLIProvider をコードベースから完全撤廃し、ClaudeCodeProvider のみのプロバイダー構成に変更する。
- **Why**: 不正JSON出力・Extra dataエラー・subprocess管理の複雑さが累積。claude_agent_sdk が利用可能でありGemini不要。
- **変更ファイル**: `gemini_provider.py` → `trash/`、`cli/helpers.py`、`cli/main.py`

### dec-2026-03-31-sdk-nested-session
`claude_agent_sdk.query()` 呼び出し時に `env={'CLAUDECODE': '', 'CLAUDE_CODE_ENTRYPOINT': 'sdk-py'}` を渡して nested session 検出を回避する。
- **Why**: Claude Code 実行中（CLAUDECODE=1）に sdk.query() を呼ぶと nested session 検出エラーが発生する。
- **実装箇所**: `ClaudeCodeProvider._async_query()` の `ClaudeAgentOptions`

### dec-2026-03-31-content-only-extraction
KnowledgeExtractor は LLM に content text のみを渡し、抽出プロンプト（`_EXTRACTION_PROMPT`）は ClaudeCodeProvider の system prompt に移動する。
- **Why**: `_EXTRACTION_PROMPT + content` を user message として渡すと project CLAUDE.md コンテキストが混入し、neo4j_entity_mapping 等の project-specific な内容が抽出に影響していた。
- **実装箇所**: `_KNOWLEDGE_EXTRACTION_SYSTEM_PROMPT` として `claude_provider.py` に移動

## 変更ファイル一覧

| ファイル | 変更内容 |
|---------|---------|
| `src/pdf_pipeline/services/claude_provider.py` | `claude_agent_sdk.query()` ベースに全面書き換え。`_KNOWLEDGE_EXTRACTION_SYSTEM_PROMPT` 追加 |
| `src/pdf_pipeline/services/gemini_provider.py` | `trash/gemini_provider.py` に移動（廃止） |
| `src/pdf_pipeline/cli/helpers.py` | GeminiCLIProvider → ClaudeCodeProvider に切り替え |
| `src/pdf_pipeline/cli/main.py` | GeminiCLIProvider import 削除 |
| `src/pdf_pipeline/core/knowledge_extractor.py` | `_parse_json_robust()` 追加、content-only 渡しに変更 |
| `tests/pdf_pipeline/unit/test_llm_providers.py` | Gemini テスト全削除、ClaudeCodeProvider 新 I/F 対応（49件全通過） |
| `.tmp/isat_pipeline.sh` | Phase 4b を `run_neo4j_loader.py` wrapper 対応 |

## アクションアイテム

- [x] Gemini CLI 撤廃 (priority: high) → **完了（本セッション）**
- [x] ClaudeCodeProvider 書き換え (priority: high) → **完了（本セッション）**
- [x] テスト更新・49件全通過確認 (priority: high) → **完了（本セッション）**
- [ ] `_EXTRACTION_PROMPT` dead code 削除 `act-2026-03-31-sdk-003` (priority: low)
- [ ] 31本 ISAT sellside PDF を Phase 2-4 で処理 `act-2026-03-31-isat-001` (priority: high)
- [ ] Neo4j への投入後、`file_path` プロパティ格納確認 `act-2026-03-31-isat-002` (priority: medium)

## 次回の議論トピック

- ISAT sellside 31本の Phase 2 実行結果確認（抽出品質・コスト検証）
- `_EXTRACTION_PROMPT` dead code 除去（knowledge_extractor.py）
- KG 孤立 Fact 577件の修復計画（act-2026-03-31-kg-004）

## 参考情報

- Haiku モデル: `~$0.003/chunk`、`~3秒/chunk`（HSBC ISAT PDF chunk[2] 実測）
- ISAT 31本 PDF: 517チャンク（disclaimer除去後）、`/Volumes/NeoData/note-finance-data/processed/` に出力済み
- nested session 解決策は `dec-2026-03-30-008` および `dec-2026-03-30-009` と同じ設計方針
