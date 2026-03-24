# 議論メモ: creator-enrichment Python オーケストレーター完成・本番運用開始

**日付**: 2026-03-24
**参加**: ユーザー + AI

## 背景・コンテキスト

creator-enrichment はプロンプトベースの Claude Code スキルとして実装されていたが、コンテキスト膨張・LLMドリフトにより `--until` 指定時刻前に停止する問題があった。前セッション(3/23)でPython オーケストレーター（Project #96, Issue #226-#236）の計画を策定。本セッションで実装完了・本番運用開始に至った。

## 議論のサマリー

### Phase 1: claude_agent_sdk API 検証

- claude-agent-sdk 0.1.48 の実API（`query()`, `ClaudeAgentOptions`, メッセージ型）を検証
- 旧実装の問題6点を修正: max_turns=1→20, permission_mode追加, model指定, system_prompt二重設定解消, ResultMessage.result優先, ネストセッション回避
- E2E検証: 47件の検索結果を正常取得

### Phase 2: ブートストラップ + SDK統一

- `runner.py` に全フェーズの実クラスをワイヤリング（Neo4j Driver/Client, GapAnalyzer, ClaudeCodeSearcher, ContentExtractor, CrossEntityEnricher）
- `llm_client.py` を新設し、extract.py / cross_entity.py を `anthropic.Anthropic()` → `SdkLLMClient` に移行
- ANTHROPIC_API_KEY 不要化を達成

### Phase 3: 本番運用（8サイクル実行）

- 12:00まで自動ローテーション（career → beauty-romance → spiritual）で実行
- 8サイクル中5サイクル成功: 1,023 nodes + 1,017 relations 投入
- 検索成功率50%問題を発見: SDKサブプロセスのコールドスタート問題

### Phase 4: DirectSearcher リファクタ

ユーザーの指摘: 「SDKで検索させるのが問題なら、直接APIを叩けばいい」
→ クエリ生成（LLM）と検索実行（API）を分離する設計に合意

- Step 2a: Sonnet でクエリ生成（ギャップ補充7本 + 探索5本）
- Step 2b: Tavily REST API で検索実行（httpx直接）
- モデル: Haiku → Sonnet に統一

E2E結果:
- 検索時間: 60-80秒 → **14秒**
- 成功率: 50% → **100%**
- 投入: 295 nodes + 272 relations（1サイクル）

## 決定事項

1. **SDK統一**: 全LLM呼び出しをclaude_agent_sdk経由に統一し、ANTHROPIC_API_KEY不要化
2. **DirectSearcher**: 検索フェーズをTavily REST API直接呼び出しに置換（TAVILY_API_KEY必要）
3. **Sonnet統一**: 全LLMモデルをclaude-sonnet-4-6に統一（品質優先）

## Before → After

| 指標 | Before（SDK + Haiku） | After（DirectSearcher + Sonnet） |
|------|----------------------|--------------------------------|
| 検索成功率 | 50% | 100% |
| 検索時間 | 60-80秒 | 14秒 |
| ANTHROPIC_API_KEY | 不要 | 不要 |
| TAVILY_API_KEY | 不要 | 必要 |
| モデル | Haiku | Sonnet |
| 新領域発見 | Haiku自律判断 | Sonnetクエリ設計（gap + explore） |

## コミット履歴

| コミット | 内容 |
|---------|------|
| `82a8949` | fix: claude_agent_sdk API接続修正 |
| `05e975b` | feat: ランナーのブートストラップ実装と検索フェーズ堅牢化 |
| `047e7ec` | refactor: claude_agent_sdk に全LLM呼び出しを統一 |
| `eb51054` | fix: Lucene特殊文字のエスケープを追加 |
| `fd53345` | refactor: 検索をDirectSearcherに置換、Sonnetに統一 |

## アクションアイテム

- [x] claude_agent_sdk API検証 + search.py接続 (優先度: 高)
- [x] runner.py ブートストラップ実装 (優先度: 高)
- [x] SDK統一（ANTHROPIC_API_KEY不要化）(優先度: 高)
- [x] DirectSearcher実装（Tavily REST API）(優先度: 高)
- [x] 空レスポンス問題の根本解決 → DirectSearcherで解消 (優先度: 低)
- [x] spiritual ジャンルの検索偏り → DirectSearcherで解消 (優先度: 中)
- [ ] ランナーのstdout/stderr無出力問題の調査 (優先度: 低)

## Phase 5: Tavily キーローテーション + 本番運用（13:17-14:37）

### 問題と対応

1. **Tavily 432エラー**: 無料プランの使用量上限に到達
2. **`.env` 未ロード**: `uv run python -c "..."` では `.env` が自動読み込みされない
3. **SDK フォールバック失敗**: `SdkLLMClient`（max_turns=1）では WebSearch ツールにアクセス不可

### 追加実装

- `TavilyKeyPool`: 連番環境変数（`TAVILY_API_KEY_1`, `_2`, ...）でキーローテーション
- 432 エラー → `mark_exhausted()` → 次のキーでリトライ → 全枯渇 → SDK フォールバック
- `python-dotenv` で `.env` 自動ロード
- SDK フォールバックを `max_turns=10` に修正

### 本番運用結果（4キー）

| Cycle | ジャンル | 検索 | Nodes | Rels |
|-------|---------|------|-------|------|
| 1 | spiritual | 59 | 393 | 389 |
| 2 | beauty-romance | 60 | 373 | 376 |
| 3 | spiritual | 54 | 384 | 362 |
| 4 | beauty-romance | 60 | 423 | 410 |
| 5 | spiritual | 53 | 298 | 332 |
| 6 | career | 59 | 375 | 367 |
| **合計** | - | **345** | **2,246** | **2,236** |

### 本日セッション累計

| 実行 | サイクル | Nodes | Rels |
|------|---------|-------|------|
| 11:00 SDK方式 | 5/8 | 1,023 | 1,017 |
| 12:29 DirectSearcher E2E | 1 | 295 | 272 |
| 13:17 Tavily 4キー本番 | 6 | 2,246 | 2,236 |
| **累計** | **12成功** | **3,564** | **3,525** |

### 追加コミット

| コミット | 内容 |
|---------|------|
| `7d13da9` | fix: Tavily 432エラー対応、SDK WebSearchフォールバック追加 |
| `d964a47` | feat: Tavily APIキーローテーション（TavilyKeyPool） |
| `d2cea97` | refactor: カンマ区切り→連番方式に変更 |
| `06b3309` | fix: .envロード追加 + SDKフォールバックをmax_turns=10に修正 |

## 次回の議論トピック

- creator-neo4j の品質チェック（大量投入後のデータ品質検証）
- enrichment 自動スケジューリング（cron or schedule スキル）
- neo4j-lifecycle (Project #94) の着手タイミング
