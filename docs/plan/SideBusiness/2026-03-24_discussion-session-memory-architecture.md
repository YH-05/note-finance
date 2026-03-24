# 議論メモ: session-memory 実装計画 ハイブリッドアーキテクチャ設計

**日付**: 2026-03-24
**参加**: ユーザー + AI

## 背景・コンテキスト

Claude Code のセッション間で会話コンテキストが失われる課題を解決するため、長期記憶システム（session-memory）の実装計画を策定。Zenn記事「Claude Codeに長期記憶を持たせたら、壁打ちの質が変わった」の sui-memory アーキテクチャを参考に、本プロジェクトの既存インフラ（Neo4j 3インスタンス、SQLite パターン）に適合させる設計を議論した。

## 議論のサマリー

### 1. DB アーキテクチャ選定（A/B/C案）

3つのアプローチを比較検討:
- **A案**: SQLite 独立DB — SSOT（Neo4j）と乖離するリスク
- **B案**: Neo4j ベクトルインデックス一本化 — 日本語FTS性能が不十分
- **C案（採用）**: ハイブリッド — SQLite を検索エンジン、Neo4j をナレッジリンク層

### 2. 日英混在対応

FTS5 trigram は言語非依存で日英両方に対応。英語での精度劣化はベクトル検索で補完。Ruri v3-310m も英語対応（MTEB ~65）で日英混在コンテンツに十分。

### 3. Neo4j インスタンス分離

research-neo4j（銘柄調査）/ creator-neo4j（クリエイター情報）はリサーチ専用DBとして分離管理。セッションチャンクは note-neo4j のみに投入。

### 4. 時間減衰の問題

当初計画のデフォルト時間減衰（half-life=30日, weight=0.3）では、関連性の高い古い記憶が新しい無関係な記憶に逆転される問題を指摘。SearchMode を導入し、RELEVANCE（減衰なし）をデフォルトに変更。

### 5. SQLite ↔ Neo4j リンキング

chunk_key（session_id + chunk_index の複合キー）で両システムを接続。リレーション生成はルールベース抽出 + Embedding 補完を同一パスで統合実行する方針に合意（段階的ではなく最初から A+B 組み合わせ）。

## 決定事項

1. **C案ハイブリッドアーキテクチャ採用** — SQLite（FTS5+sqlite-vec）を検索エンジン、note-neo4j をナレッジリンク層
2. **FTS5 trigram 採用** — 日英混在コンテンツに言語非依存で対応
3. **note-neo4j のみ使用** — research/creator には一切アクセスしない。graph.py は bolt://localhost:7687 にハードコード
4. **Ruri v3-310m + e5-small 併用** — session_memory は Ruri（長文意味検索）、entity_linker は e5-small（短文マッチ）
5. **SearchMode デフォルト RELEVANCE** — 時間減衰OFF。RECENT/HYBRID は明示指定時のみ
6. **ルールベース + Embedding 統合実行** — 同一パスで実行し重複排除。段階的ではなく初回から組み合わせ

## アクションアイテム

- [ ] session-memory Phase 1-9 の実装開始（優先度: 高）
- [x] note-neo4j SessionChunk ノードスキーマ詳細設計（優先度: 中）→ 2026-03-24 完了

---

## 継続議論 (2026-03-24 Session 2): チャンク設計確定

### 議論のサマリー

#### トピック1: SessionChunk / Session プロパティ定義

1. **assistant_text フル保持**: 先頭200字のsummaryではサマリーにならない → assistant_text を完全保持（4000字切断）。Neo4j に入れても ~37MB で問題なし
2. **Session ノード分離**: first_prompt, git_branch はセッション単位の情報 → Session ノードに集約し SessionChunk-[:BELONGS_TO]->Session でリンク
3. **NEXT リレーション**: チャンク間の時系列順序を [:NEXT] で表現（ユーザー要求）。グラフ探索で前後チャンクを直接辿れるメリット
4. **チャンク粒度**: Q&Aペア（user→assistant）単位。1セッション丸ごと1ノードでは検索精度が低く、文単位では文脈が失われる

#### 確定プロパティ

```
(:Session)
├── session_id: str       # UNIQUE
├── first_prompt: str
├── git_branch: str?
├── session_timestamp: str
├── chunk_count: int
└── created_at: str

(:SessionChunk)
├── chunk_key: str        # "{session_id}_{chunk_index:04d}" — UNIQUE
├── session_id: str
├── chunk_index: int
├── user_text: str
├── assistant_text: str   # フル保持（4000字切断）
├── tags: list[str]       # Neo4jネイティブリスト
├── session_timestamp: str
└── created_at: str
```

#### 確定リレーション

| リレーション | 方向 | 用途 |
|-------------|------|------|
| `BELONGS_TO` | SessionChunk → Session | セッション帰属 |
| `NEXT` | SessionChunk → SessionChunk | セッション内の時系列順序 |
| `MENTIONS` | SessionChunk → Entity | エンティティ言及 |
| `DISCUSSES` | SessionChunk → Topic | トピック議論 |
| `DECIDED` | SessionChunk → Decision | 判断記録（将来） |

### 決定事項（Session 2）

7. **assistant_text フル保持** — summary フィールド廃止。必要時は Cypher で substring
8. **Session/SessionChunk ノード分離** — セッション単位メタデータは Session ノードに集約
9. **NEXT リレーション** — チャンク間順序をグラフネイティブに表現

#### トピック2: MENTIONS/DISCUSSES/DECIDED 生成ルール

**確定: 3ステップ統合パイプライン**

```
Step 1: ルールベース検出
    ファイルパス、import文、コマンド名、パッケージ名 → 候補リスト

Step 2: Sonnet tool_use 構造化抽出（1回の呼び出しで3種同時）
    ChunkExtraction Pydanticモデル:
    - entities: list[ExtractedEntity]  (name, entity_type, confidence)
    - topics: list[ExtractedTopic]     (name, confidence)
    - decisions: list[ExtractedDecision] (content, context, confidence)
    tool_choice 強制 → パース失敗リスクゼロ

Step 3: entity_linker 4層照合（research/creator-neo4j の実績パターン再利用）
    Layer 1: entity_key exact match ({name}::{type})
    Layer 2: Full-text search + Levenshtein similarity (> 0.8)
    Layer 3: Alias ノード → ALIAS_OF トラバーサル
    Layer 4: e5-small embedding cosine similarity

Step 4: フィルタ → リレーション生成
    confidence >= 0.7 → 自動リンク
    confidence < 0.7  → Embedding 追加検証
    confidence < 0.3  → 棄却
```

10. **3ステップ統合抽出** — ルールベース → Sonnet構造化抽出 → entity_linker 4層照合
11. **構造化出力必須** — Sonnet tool_use + ChunkExtraction Pydanticスキーマ + tool_choice強制
12. **DECIDED も LLM 抽出** — バルクインポート・新規Hook 両方で Sonnet 抽出（ルールベースでは誤検出多い）
13. **Embedding 補完は e5-small** — 短文エンティティ名照合用。Ruri はSQLite側ベクトル検索専用
14. **Entity/Topic はシード+動的生成** — 主要技術のシードリスト（50-100件）+ alias辞書で正規化、新出は動的追加
15. **閾値は設定可能** — `SESSION_MEMORY_SIM_THRESHOLD` 環境変数、バルク後にサンプリング校正

#### トピック3: バルクインポート実行計画

**対象**: 4プロジェクト 1,237セッション（~12,370チャンク）

| プロジェクト | セッション | 推定チャンク |
|-------------|-----------|------------|
| note-finance (+worktrees) | 826 | ~8,260 |
| finance (+worktrees) | 301 | ~3,010 |
| quants (+worktrees) | 87 | ~870 |
| notebooklm-mcp | 23 | ~230 |

- Session ノードに `project` プロパティで区別（worktree は親プロジェクトに統合）
- SQLite chunks テーブルにも `project` カラム追加
- 10並列 Sonnet API、rate limit 時は5並列にフォールバック
- プロジェクト単位で順次処理（note-finance → finance → quants → notebooklm-mcp）
- 中断・再開: `import_log`（セッション単位）+ `extraction_log`（チャンク単位）の2段管理

16. **対象4プロジェクト** — note-finance, finance, quants, notebooklm-mcp（合計1,237セッション）
17. **project プロパティで区別** — Session ノード + SQLite chunks に project カラム
18. **10並列→5並列フォールバック** — rate limit 時に自動減速
19. **2段階の中断・再開** — import_log + extraction_log

#### トピック4: SessionEnd Hook 実装詳細

**確定: 2層構成**

```
プロジェクト設定（.claude/settings.json）← git でポータブル
  note-finance: uv run python scripts/memory_session_end.py（相対パス）

グローバル設定（~/.claude/settings.json）← マシン固有
  finance/quants/notebooklm-mcp: 絶対パスで note-finance のスクリプトを呼ぶ
```

- stdin JSON の `cwd` からプロジェクト判定
- 対象4プロジェクト以外は早期スキップ
- `&` でバックグラウンド実行（~30-60秒で完了）
- バルクインポートと同一パイプラインを再利用

20. **Hook 2層構成** — プロジェクト設定（ポータブル）+ グローバル設定（他プロジェクトカバー）

### アクションアイテム（Session 2）

- [x] MENTIONS/DISCUSSES/DECIDED の生成ルール詳細設計 → 2026-03-24 完了
- [x] バルクインポートの実行計画 → 2026-03-24 完了
- [x] SessionEnd Hook の実装詳細 → 2026-03-24 完了

### 次のステップ

- [ ] 計画書 `docs/plan/2026-03-24_session-memory-implementation-plan.md` をこの議論結果で更新
- [ ] Phase 1 実装開始: types.py + db.py + テスト

## 参考情報

- 計画書: `docs/plan/2026-03-24_session-memory-implementation-plan.md`
- Ruri v3-310m: JMTEB 77.24（日本語SOTA）、768次元、Apache 2.0
- 既存パターン: `src/rss/storage/scrape_state_db.py`（SQLite）、`scripts/entity_linker.py:828-900`（embedding遅延ロード）
- entity_linker 4層マッチング: `scripts/entity_linker.py`（exact → full-text → alias → embedding）
- fuzzy matching 設計: `docs/plan/SideBusiness/2026-03-22_fuzzy-matching-design.md`
