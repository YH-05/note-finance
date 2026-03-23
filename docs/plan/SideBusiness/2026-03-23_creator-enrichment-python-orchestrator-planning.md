# 議論メモ: creator-enrichment Python オーケストレーター計画策定

**日付**: 2026-03-23
**参加**: ユーザー + AI

## 背景・コンテキスト

creator-enrichment は現在プロンプトベースの Claude Code スキルとして実装されている。1つの会話内で全サイクルを実行するため、コンテキスト膨張・LLMドリフトにより `--until` で指定した終了時刻前に停止してしまう問題がある。Python スクリプトで時間管理とサイクルループを決定的に制御するオーケストレーターを実装する計画を策定した。

## 議論のサマリー

### 実行したワークフロー

plan-project スキル（4フェーズ）を実行：

1. **Phase 0（HF0）**: プロジェクトタイプ確認 → package / 置き換え
2. **Phase 1**: project-researcher が8パス（スキル・スクリプト・設定・テンプレート）を調査。7つの情報ギャップを特定
3. **Phase 2（HF2）**: project-planner が11コンポーネント・24ファイルの実装計画を策定
4. **Phase 3（HF3）**: project-decomposer が11タスク・4 Wave に分解
5. **Phase 4**: GitHub Project #96 作成、Issue #226-#236 登録

### 設計判断（HF1 での回答）

| 論点 | 決定 |
|------|------|
| sys.exit(1) 対策 | pipeline.py 側で事前バリデーション（既存コード変更なし） |
| Tavily 検索方式 | claude_agent_sdk 経由で Claude Code を呼び出し、MCP tavily/reddit を使用 |
| cycle_id | Fact/Tip/Story に付与して投入検証に使用 |
| LLM モデル | claude-haiku-4-5-20251001 で統一（コスト優先） |

## 決定事項

1. **プロジェクトタイプ**: `src/creator_enrichment/` パッケージとして実装
2. **検索フェーズ**: claude_agent_sdk → MCP tavily/reddit（httpx フォールバック用意）
3. **sys.exit 対策**: config.py + pipeline.py の二重バリデーション
4. **cycle_id + Haiku 統一**: 投入検証の正確性 + コスト効率

## 成果物

| 成果物 | パス / URL |
|--------|-----------|
| GitHub Project | [#96](https://github.com/users/YH-05/projects/96) |
| 計画書 | `docs/project/project-23/project.md` |
| 元プラン | `docs/project/project-23/original-plan.md` |
| Issue #226-#236 | 11 タスク（4 Wave） |
| Worktree | `feature/prj96` → `/Users/yukihata/Desktop/.worktrees/note-finance/feature-prj96` |
| セッションデータ | `.tmp/plan-project-20260323-185128/` |

## アクションアイテム

- [ ] Wave 1 実装開始: #226 → #227 → #228（worktree feature/prj96 で作業）(優先度: 高)
- [ ] Wave 2 着手前に claude_agent_sdk パッケージの正式名称・API を検証 (優先度: 高)
- [ ] #232 CreatorGraphWriter 実装時に MERGE キー設計を確認 (優先度: 中)

## 次回の議論トピック

- claude_agent_sdk の API 検証結果と search.py の最終設計
- Wave 2 並列開発の進捗確認

## クリティカルパス

`#226` → `#232`（neo4j_writer, 最大規模 350行） → `#233` → `#235` → `#236`
