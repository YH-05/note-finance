# 議論メモ: investment-research Phase 5 自動化（PostToolUse フック実装）

**日付**: 2026-03-29
**参加**: ユーザー + AI

## 背景・コンテキスト

`/investment-research` スキルは Phase 0〜5 の6フェーズで構成されている。
Phase 5 は KG永続化（Neo4j投入）を担うが、プロンプトベースのスキルのため
LLM が Phase 5 をスキップしても強制する仕組みがなかった。

## 議論のサマリー

### 問題の発生

Indonesia Telecom セクターのリサーチ実行後、Neo4j への自動投入が行われなかった。
調査の結果、investment-research はプロンプト指示のみで Phase 5 の実行を促しており、
LLM の判断でスキップされることが根本原因と特定。

### 解決策の検討

プロンプト強化だけでは再発を防止できないため、
Claude Code の PostToolUse フック機能を活用した自動化を検討。

**採用案**: `Write` ツールの PostToolUse フックで `.tmp/research-input/*.json` への
書き込みを検出 → emit → ingest パイプラインを自動実行。

**PostToolUse の動作**: Write ツール完了後（ファイル書き込み完了後）にフック発火。
JSON は完全に書き込まれた状態でフックが動作するため、競合状態は発生しない。

### 実装内容

#### `.claude/hooks/auto-kg-ingest.py`（新規作成）

- `stdin` から PostToolUse イベントを受信
- `tool_input.file_path` が `.tmp/research-input/*.json` に一致するか判定
- JSON に必須キー (`session_id`, `sources`, `facts`, `entities`, `topics`) が揃っているか検証
- `emit_research_queue.py --command web-research --input {path}` を subprocess 実行
- 生成された `gq-*.json` を特定し `ingest_graph_queue.py --file {gq}` を実行
- 全ステップのログを `.tmp/auto-kg-ingest.log` に記録

#### `.claude/settings.json`（修正）

`PostToolUse` セクションに `Write` マッチャーを追加:
```json
{
  "matcher": "Write",
  "hooks": [
    {
      "type": "command",
      "command": "uv run python $CLAUDE_PROJECT_DIR/.claude/hooks/auto-kg-ingest.py"
    }
  ]
}
```

#### `.claude/skills/investment-research/SKILL.md`（修正）

- Phase 5 の見出しを「KG永続化（フック自動実行）」に変更
- Step 5-1 のみ LLM が実行、Step 5-2/5-3 はフック自動実行であることを明記

### 動作確認

テスト用 research-input JSON を `.tmp/research-input/` に Write → フックが発火し、
emit（gq-20260329020409-b91e7ffb.json 生成）→ ingest（24ノード、58リレーション）が
自動実行されることを確認。

Neo4j Cypher クエリで Bank Indonesia 関連の Fact ノードが存在することも確認済み。

### 残存課題

`ingest_graph_queue.py` の検証ロジックで `relationships_created=0` を誤って
エラーと判定する false positive がある（同データの再投入時に発生）。
フック実装とは独立した既存の問題であり、今回の対応範囲外。

## 決定事項

1. **PostToolUse(Write) フック方式を採用**: `.tmp/research-input/*.json` への書き込みを
   トリガーとして KG 永続化パイプラインを自動実行する
2. **Phase 5 における LLM の責任範囲を Step 5-1 のみに縮小**: 入力 JSON の構築・Write のみ。
   emit/ingest はフックに委任する

## アクションアイテム

- [x] auto-kg-ingest.py フック実装・動作確認 (2026-03-29 完了)
- [ ] Indonesia Telecom 記事 review → publish 3本 (優先度: 高)
- [ ] Claude Code 再起動で Tavily カスタム MCP サーバーを有効化 (優先度: 中)

## 次回の議論トピック

- `ingest_graph_queue.py` の verification false positive 修正（relationships_created=0 を
  エラーとみなさないようにする）

## 参考情報

- フック実装: `.claude/hooks/auto-kg-ingest.py`
- ログ確認: `.tmp/auto-kg-ingest.log`
- パイプライン: `scripts/emit_research_queue.py` → `scripts/ingest_graph_queue.py`
- KG: research-neo4j (bolt://localhost:7688)
