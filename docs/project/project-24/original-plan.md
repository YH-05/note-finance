# Claude Code 長期記憶システム（session-memory）実装計画

## Context

Claude Code のセッション間で会話コンテキストが失われる課題を解決する。Zenn記事「Claude Codeに長期記憶を持たせたら、壁打ちの質が変わった」の **sui-memory** アーキテクチャを、本プロジェクトの規約・パターンに適合させて実装する。

**現在の記憶システム**: ファイルベース Markdown（18ファイル、手動管理）
**目標**: セッション終了時に自動保存、検索時に過去の議論・判断理由・失敗事例を即座に取得

### 対象プロジェクト

| プロジェクト | セッション数 | 推定チャンク数 | 内容 |
|-------------|-------------|--------------|------|
| note-finance (+worktrees) | 826 | ~8,260 | 本プロジェクトの開発全履歴 |
| finance (+worktrees) | 301 | ~3,010 | 金融ニュース追跡リポジトリ |
| quants (+worktrees) | 87 | ~870 | クオンツ計算リポジトリ |
| notebooklm-mcp | 23 | ~230 | NotebookLM MCP 開発 |
| **合計** | **1,237** | **~12,370** | |

---

## アーキテクチャ（C案: ハイブリッド）

SQLiteを高速検索エンジン、Neo4jをナレッジリンク層として使い分ける。

```
[Session transcript]
       │
       ▼
   chunker.py → Q&A チャンク（user→assistant ペア）
       │
       ├──→ SQLite (FTS5 + sqlite-vec) ← 高速検索用
       │       keyword search + vector search + RRF
       │
       ├──→ Sonnet tool_use 構造化抽出 ← メタデータ抽出
       │       entities + topics + decisions 同時抽出
       │
       └──→ note-neo4j (port 7687)     ← 知識接続用
               (:Session) ← [:BELONGS_TO] ← (:SessionChunk)
               (:SessionChunk) -[:NEXT]-> (:SessionChunk)
               (:SessionChunk) -[:MENTIONS]-> (:Entity)
               (:SessionChunk) -[:DISCUSSES]-> (:Topic)
               (:SessionChunk) -[:DECIDED]-> (:Decision)
```

### 設計判断の根拠

| 判断 | 理由 |
|------|------|
| SQLite を検索インデックスとして併用 | Neo4j が SSOT、SQLite は検索高速化層。役割が明確に分離 |
| FTS5 trigram を採用 | 日英混在コンテンツで言語非依存の trigram が最適。Lucene CJK analyzer より安定 |
| note-neo4j にセッションチャンクを投入 | research-neo4j / creator-neo4j はリサーチ専用DB。プロジェクトメモリとは分離管理 |
| Ruri v3-310m と e5-small を併用 | session_memory は長文意味検索（Ruri, JMTEB 77.24）、entity_linker は短文マッチ（e5-small）。用途が異なる |
| Session / SessionChunk を分離 | セッション単位メタデータ（first_prompt, git_branch）を Session に集約し冗長性を排除 |
| assistant_text をフル保持 | 先頭200字ではサマリーにならない。~37MB は Neo4j として許容範囲。グラフ探索で直接内容を読める |
| NEXT リレーション | チャンク間の時系列順序をグラフネイティブに表現。前後チャンクを直接辿れる |
| 構造化抽出に Sonnet tool_use | tool_choice 強制でパース失敗リスクゼロ。confidence フィールドで自動/手動の判断を機械化 |
| DECIDED も LLM 抽出 | ルールベースでは「〜に決定」等のパターンマッチは誤検出が多い。バルク・Hook 両方で Sonnet 抽出 |

### 検索フロー

1. SQLite で高速にトップN件を取得（FTS5 + vector + RRF + 時間減衰）
2. ヒットした chunk の ID で note-neo4j を引き、関連 Entity/Topic を展開
3. グラフコンテキスト付きの検索結果を返却

### Neo4j インスタンス分離

| インスタンス | ポート | 用途 | セッションチャンク |
|-------------|--------|------|-------------------|
| note-neo4j | 7687 | プロジェクトメモリ、議論・判断の知識グラフ | **投入先** |
| research-neo4j | 7688 | 銘柄・マクロ調査専用 | 投入しない |
| creator-neo4j | 7689 | クリエイター情報専用 | 投入しない |

---

## Neo4j グラフスキーマ

### ノード定義

```
(:Session)
├── session_id: str       # UNIQUE
├── project: str          # "note-finance" | "finance" | "quants" | "notebooklm-mcp"
├── first_prompt: str     # セッション最初のプロンプト
├── git_branch: str?      # 作業ブランチ
├── session_timestamp: str # ISO 8601
├── chunk_count: int
└── created_at: str

(:SessionChunk)
├── chunk_key: str        # "{session_id}_{chunk_index:04d}" — UNIQUE
├── session_id: str
├── chunk_index: int
├── user_text: str        # ユーザー発話
├── assistant_text: str   # Claude 応答テキスト（フル保持、4000字切断）
├── tags: list[str]       # Neo4j ネイティブリスト
├── session_timestamp: str
└── created_at: str
```

### リレーション定義

| リレーション | 方向 | 用途 | 生成手法 |
|-------------|------|------|---------|
| `BELONGS_TO` | SessionChunk → Session | セッション帰属 | チャンキング時に自動 |
| `NEXT` | SessionChunk → SessionChunk | セッション内の時系列順序 | チャンキング時に自動 |
| `MENTIONS` | SessionChunk → Entity | エンティティ言及 | ルールベース + Sonnet + entity_linker |
| `DISCUSSES` | SessionChunk → Topic | トピック議論 | ルールベース + Sonnet + entity_linker |
| `DECIDED` | SessionChunk → Decision | 判断記録 | Sonnet 構造化抽出 |

### 制約

```cypher
CREATE CONSTRAINT session_id_unique IF NOT EXISTS
FOR (s:Session) REQUIRE s.session_id IS UNIQUE;

CREATE CONSTRAINT chunk_key_unique IF NOT EXISTS
FOR (c:SessionChunk) REQUIRE c.chunk_key IS UNIQUE;
```

### プロジェクト識別

ディレクトリ名から自動判定。worktree は親プロジェクトに統合:

```python
def resolve_project(dir_name: str) -> str:
    if "--worktrees-" in dir_name:
        parent = dir_name.split("--worktrees-")[1]
        for prefix in ("feature-", "fix-", "refactor-", "docs-", "test-"):
            if f"-{prefix}" in parent:
                parent = parent.split(f"-{prefix}")[0]
                break
        return parent.lower()
    return dir_name.rsplit("-", 1)[-1].lower() if "-Desktop-" in dir_name else dir_name
```

---

## パッケージ構成

```
src/session_memory/
├── __init__.py              # Public API: SessionMemoryDB, search, save
├── _logging.py              # get_logger ラッパー（rss/_logging.py 踏襲）
├── types.py                 # Chunk, SearchResult, SearchMode, ChunkExtraction 等の型定義
├── db.py                    # SessionMemoryDB（SQLite + FTS5 + sqlite-vec）
├── chunker.py               # transcript.jsonl → Q&Aチャンク変換
├── embedder.py              # Ruri v3-310m ラッパー（lazy load + fallback）
├── extractor.py             # Sonnet tool_use 構造化抽出（entities/topics/decisions）
├── searcher.py              # ハイブリッド検索（FTS5 + vector + RRF + 時間減衰）
├── linker.py                # entity_linker 4層照合（exact → full-text → alias → embedding）
├── graph.py                 # note-neo4j 連携（Session/SessionChunk ノード投入・リレーション作成）
├── hook.py                  # SessionEnd Hook エントリポイント
└── cli/
    ├── __init__.py
    └── main.py              # Click CLI: save / search / bulk-import / stats

scripts/
└── memory_session_end.py    # Hook から呼ばれる薄いラッパー

tests/session_memory/
├── conftest.py              # fixtures: tmp_db, mock_embedder, sample_jsonl
├── unit/
│   ├── test_db.py           # SessionMemoryDB CRUD, スキーマ, WAL
│   ├── test_chunker.py      # JSONL解析, ターン抽出, テキスト清掃
│   ├── test_extractor.py    # Sonnet 構造化抽出, Pydantic バリデーション
│   └── test_searcher.py     # FTS5, vector, RRF, 時間減衰
├── property/
│   ├── test_chunker_prop.py # Hypothesis: 任意JSONL入力でクラッシュしない
│   └── test_searcher_prop.py# Hypothesis: RRFスコア単調減少, 減衰 ∈ (0,1]
└── integration/
    └── test_save_search.py  # E2E: parse → chunk → embed → extract → save → search
```

---

## データベーススキーマ

保存先: `data/cache/session_memory.db`

```sql
PRAGMA journal_mode=WAL;

-- メインテーブル
CREATE TABLE IF NOT EXISTS chunks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL,
    chunk_index INTEGER NOT NULL,
    project TEXT NOT NULL,                     -- プロジェクト識別
    user_text TEXT NOT NULL,
    assistant_text TEXT NOT NULL,              -- フル保持（4000字切断）
    session_timestamp TEXT NOT NULL,           -- 元セッションのタイムスタンプ
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    git_branch TEXT,
    first_prompt TEXT,
    tags TEXT,                                 -- カンマ区切り自動タグ
    UNIQUE(session_id, chunk_index)
);

-- FTS5 trigram（日英混在全文検索）
CREATE VIRTUAL TABLE IF NOT EXISTS chunks_fts USING fts5(
    user_text, assistant_text, tags,
    content='chunks', content_rowid='id',
    tokenize='trigram'
);
-- INSERT/DELETE/UPDATE トリガーで同期

-- sqlite-vec ベクトルテーブル（768次元 = Ruri v3-310m）
CREATE VIRTUAL TABLE IF NOT EXISTS chunks_vec USING vec0(
    chunk_id INTEGER PRIMARY KEY,
    embedding FLOAT[768]
);

-- インデックス
CREATE INDEX IF NOT EXISTS idx_session_id ON chunks(session_id);
CREATE INDEX IF NOT EXISTS idx_session_ts ON chunks(session_timestamp);
CREATE INDEX IF NOT EXISTS idx_project ON chunks(project);

-- バルクインポート冪等性（セッション単位）
CREATE TABLE IF NOT EXISTS import_log (
    session_id TEXT PRIMARY KEY,
    chunk_count INTEGER NOT NULL,
    imported_at TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Sonnet 抽出の中断・再開（チャンク単位）
CREATE TABLE IF NOT EXISTS extraction_log (
    chunk_key TEXT PRIMARY KEY,
    extraction_json TEXT NOT NULL,
    extracted_at TEXT NOT NULL DEFAULT (datetime('now'))
);

-- メタデータ（モデル変更時の検出用）
CREATE TABLE IF NOT EXISTS metadata (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
-- INSERT: ('embedding_model', 'cl-nagoya/ruri-v3-310m'), ('embedding_dim', '768')
```

---

## チャンキング戦略

`transcript.jsonl` → Q&A チャンクへの変換:

1. **JSONL 行パース**: `type` が `user` / `assistant` のみ抽出（`file-history-snapshot`, `system`, `progress`, `queue-operation`, `last-prompt` はスキップ）
2. **ターン構築**: user → assistant のペアを1チャンクとする
3. **テキスト抽出**:
   - user: `content` が文字列ならそのまま、リストなら `text` ブロックのみ（XML コマンドタグ除去）
   - assistant: `text` ブロックのみ（`tool_use`, `thinking` はスキップ）、4000字で切断
4. **短ターン統合**: user_text < 30文字かつ疑問符なし → 直前チャンクにマージ
5. **自動タグ**: スラッシュコマンド、ファイルパス、キーワード（Neo4j, 記事, テスト等）のルールベース検出

---

## メタデータ抽出パイプライン

各チャンクから MENTIONS / DISCUSSES / DECIDED を生成する3ステップ統合パイプライン。

```
SessionChunk テキスト
    │
    ├─ Step 1: ルールベース検出
    │   ファイルパス      → Entity(type="module")
    │   パッケージ名      → Entity(type="technology")
    │   コマンド名        → Entity(type="command")
    │   Python import    → Entity(type="library")
    │
    ├─ Step 2: Sonnet tool_use 構造化抽出（1回の呼び出しで3種同時）
    │   tool_choice 強制 → ChunkExtraction Pydantic モデル
    │   entities:  list[ExtractedEntity]   (name, entity_type, confidence)
    │   topics:    list[ExtractedTopic]    (name, confidence)
    │   decisions: list[ExtractedDecision] (content, context, confidence)
    │
    └─ Step 3: entity_linker 4層照合（research/creator-neo4j の実績パターン再利用）
        Layer 1: entity_key exact match ({name}::{entity_type})
        Layer 2: Full-text search + Levenshtein similarity (> 0.8)
        Layer 3: Alias ノード → ALIAS_OF トラバーサル
        Layer 4: e5-small embedding cosine similarity
        → 既存あり: リレーション作成
        → 既存なし: 新規 Entity/Topic ノード作成 + リレーション
```

### 構造化抽出の Pydantic モデル

```python
class ExtractedEntity(BaseModel):
    name: str
    entity_type: str  # company|technology|organization|person|concept|command|module|library
    confidence: float  # 0.0-1.0

class ExtractedTopic(BaseModel):
    name: str
    confidence: float

class ExtractedDecision(BaseModel):
    content: str
    context: str
    confidence: float

class ChunkExtraction(BaseModel):
    entities: list[ExtractedEntity] = Field(default_factory=list)
    topics: list[ExtractedTopic] = Field(default_factory=list)
    decisions: list[ExtractedDecision] = Field(default_factory=list)
```

### Sonnet 呼び出し

```python
response = client.messages.create(
    model="claude-sonnet-4-20250514",
    messages=[{"role": "user", "content": prompt}],
    tools=[{
        "name": "extract_chunk_metadata",
        "description": "Q&Aチャンクからエンティティ・トピック・意思決定を抽出",
        "input_schema": ChunkExtraction.model_json_schema()
    }],
    tool_choice={"type": "tool", "name": "extract_chunk_metadata"}
)
```

### confidence によるフィルタ

| confidence | 処理 |
|-----------|------|
| >= 0.7 | 自動リンク |
| < 0.7 | Embedding 補完（e5-small Layer 4）で追加検証 |
| < 0.3 | 棄却 |

閾値は `SESSION_MEMORY_SIM_THRESHOLD` 環境変数で設定可能。バルクインポート後にサンプリングで校正する。

### Entity/Topic のマスター管理

**シード + 動的生成のハイブリッド方式**:
- プロジェクト主要技術のシードリスト（50-100件）を事前定義
- alias 辞書（`{"neo4j": "Neo4j", "ネオフォージェイ": "Neo4j"}`）で正規化
- シードにない新出エンティティはチャンクから動的に追加

---

## 検索アルゴリズム

```
クエリ + SearchMode
         │
         ├─→ FTS5 trigram検索（キーワード完全一致）──┐
         │    MATCH + BM25 rank                      │
         └─→ sqlite-vec検索（意味的類似性）──────────┤
              Ruri v3-310m cosine similarity          │
                                                      ▼
                                            RRF統合（k=60）
                                         fts_weight=0.4, vec_weight=0.6
                                                      │
                                                      ▼
                                       SearchMode に応じた時間減衰
                                    RELEVANCE: 減衰なし（デフォルト）
                                    RECENT:    半減期30日, weight=0.3
                                    HYBRID:    半減期30日, weight=0.1
                                                      │
                                                      ▼
                                              上位N件を返却
                                                      │
                                                      ▼ (オプション)
                                          note-neo4j でグラフ展開
                                     関連 Entity/Topic/Decision を付与
```

**RRF数式**: `score(d) = Σ weight_r / (60 + rank_r(d))`
**時間減衰**: `final = rrf * (1 - time_weight + time_weight * 0.5^(age_days/30))`

### SearchMode（検索モード）

| モード | デフォルト | time_weight | 用途 |
|--------|-----------|-------------|------|
| `RELEVANCE` | **yes** | 0.0（減衰なし） | 過去の設計判断・議論の理由を検索 |
| `RECENT` | no | 0.3 | 直近の作業内容・進捗の確認 |
| `HYBRID` | no | 0.1 | 通常検索（関連性重視 + 軽い新しさバイアス） |

**設計判断**: 時間減衰はデフォルトOFF。長期記憶システムの主目的は「過去の重要な判断・議論を失わずに検索する」ことであり、関連性の高い古い記憶が新しい無関係な記憶に逆転されることを防ぐ。直近の文脈が欲しい場合のみ `RECENT` / `HYBRID` を明示指定する。

---

## Embedding モデル（併用戦略）

| 用途 | モデル | 次元 | 理由 |
|------|--------|------|------|
| session_memory（長文意味検索、SQLite sqlite-vec） | `cl-nagoya/ruri-v3-310m` | 768 | JMTEB 77.24（日本語SOTA）、長文Q&Aの意味的類似性に最適 |
| entity_linker（短文マッチング、Neo4j Layer 4） | `intfloat/multilingual-e5-small` | 384 | 短いエンティティ名のマッチングに十分、軽量 |

**Ruri v3-310m**:
- 名古屋大学開発、JMTEB 77.24（日本語SOTA）
- 768次元、8192トークン対応
- OpenAI text-embedding-3-small を+6.38pt上回る
- Apache 2.0、CPU実行可能
- 英語も対応（MTEB ~65、英語特化モデルよりは劣るが日英混在には十分）

**フォールバック**: `intfloat/multilingual-e5-small`（Ruri インストール失敗時）

環境変数 `SESSION_MEMORY_MODEL` でオーバーライド可能。

---

## Hook 設定（2層構成）

### プロジェクト設定（ポータブル）

`.claude/settings.json` に追加（git で持ち運べる）:

```json
"SessionEnd": [
  {
    "hooks": [
      {
        "type": "command",
        "command": "uv run python scripts/memory_session_end.py 2>>logs/memory-hook.log &"
      }
    ]
  }
]
```

### グローバル設定（マシン固有）

`~/.claude/settings.json` に追加（finance / quants / notebooklm-mcp 用）:

```json
"SessionEnd": [
  {
    "hooks": [
      {
        "type": "command",
        "command": "cd /Users/yukihata/Desktop/note-finance && uv run python scripts/memory_session_end.py 2>>logs/memory-hook.log &"
      }
    ]
  }
]
```

### Hook 処理フロー

```
stdin → JSON パース
  { "session_id": "abc-123",
    "transcript_path": "~/.claude/projects/-Users-.../abc-123.jsonl",
    "cwd": "/Users/yukihata/Desktop/finance" }
  → cwd からプロジェクト判定
  → 対象4プロジェクト以外は早期スキップ
  → チャンキング → Ruri embedding → SQLite 保存
  → Sonnet 構造化抽出
  → entity_linker 照合
  → note-neo4j 投入
  → ログ出力
```

`&` でバックグラウンド実行（~30-60秒で完了）。Claude Code の終了をブロックしない。

---

## バルクインポート実行計画

### 実行フロー

```
Phase 1: パース + チャンキング（全1,237セッション一括）
    transcript.jsonl → Q&A チャンク生成
    project 判定（ディレクトリ名から自動解決）
    import_log でスキップ判定
    ↓
Phase 2: Embedding 生成（Ruri v3-310m, CPU）
    全チャンクの embedding を生成 → SQLite sqlite-vec に格納
    ↓
Phase 3: Sonnet 構造化抽出（10並列、プロジェクト単位）
    note-finance → finance → quants → notebooklm-mcp の順
    各プロジェクト内で10並列 API 呼び出し
    rate limit エラー時は自動で5並列にフォールバック
    extraction_log で中断・再開
    ↓
Phase 4: entity_linker 4層照合 + Neo4j 投入
    抽出結果を照合 → Session/SessionChunk/リレーション投入
```

### 冪等性・中断再開

- **セッション単位**: `import_log` テーブルで完了セッションをスキップ
- **チャンク単位**: `extraction_log` テーブルで Sonnet 抽出結果を保存、再開時はスキップ
- 全操作が冪等（MERGE ベース）

---

## 依存関係の追加

`pyproject.toml`:
```toml
[project.optional-dependencies]
memory = [
    "sqlite-vec>=0.1.6",
    "sentence-transformers>=3.0.0",
    "anthropic>=0.40.0",
]

[project.scripts]
memory-cli = "session_memory.cli.main:cli"

[tool.hatch.build.targets.wheel]
packages = [..., "src/session_memory"]
```

インストール: `uv sync --extra memory`

---

## 既存コードとの統合

| 統合先 | 方法 |
|--------|------|
| `ScrapeStateDB` パターン | コンテキストマネージャ、WAL、接続チェック、structlog を踏襲 |
| `entity_linker.py` パターン | 4層マッチング戦略（exact → full-text → alias → embedding）を再利用 |
| `entity_linker.py` embedding | `@lru_cache(maxsize=1)` による遅延ロード、ImportError フォールバック |
| `data/cache/` | DB ファイル保存先（academic.db と同階層） |
| `.claude/commands/` | `/memory-search` スラッシュコマンド作成 |
| `Makefile` | 変更不要（既存 check-all が自動カバー） |
| note-neo4j | Session/SessionChunk ノード投入、Entity/Topic/Decision へのリレーション作成 |

---

## CLI コマンド

```bash
# 単一セッション保存
memory-cli save <session_id>

# 検索
memory-cli search "Neo4j スキーマ設計の議論"

# 全既存セッションのバルクインポート（10並列、プロジェクト単位）
memory-cli bulk-import --progress --parallel 10

# 統計
memory-cli stats
```

---

## 実装フェーズ

| Phase | 内容 | 成果物 |
|-------|------|--------|
| **1** | DB 層（types.py, db.py + テスト） | SessionMemoryDB コア |
| **2** | チャンカー（chunker.py + テスト） | transcript → chunks 変換 |
| **3** | エンベッダー（embedder.py + pyproject.toml更新） | Ruri v3 ラッパー |
| **4** | 検索（searcher.py + テスト） | FTS5 + vector + RRF + SearchMode |
| **5** | 構造化抽出（extractor.py + テスト） | Sonnet tool_use + ChunkExtraction |
| **6** | リンカー（linker.py + テスト） | entity_linker 4層照合 |
| **7** | CLI（cli/main.py + pyproject.toml更新） | memory-cli コマンド |
| **8** | Hook（hook.py + settings.json更新） | SessionEnd 自動保存（2層構成） |
| **9** | Neo4j 連携（graph.py + note-neo4j投入） | Session/SessionChunk/リレーション投入 |
| **10** | バルクインポート + スラッシュコマンド | 既存1,237セッション取り込み |
| **11** | 統合テスト + ドキュメント | E2E テスト |

---

## 検証方法

1. `make check-all` が全パス（format, lint, typecheck, test）
2. `memory-cli bulk-import --progress` で既存セッション取り込み成功
3. `memory-cli search "KG v3.0 設計判断"` で関連する過去の議論がヒット
4. `memory-cli stats` でチャンク数・DB サイズが妥当（~12,370チャンク）
5. 新セッション終了時に `logs/memory-hook.log` でエラーなし
6. `data/cache/session_memory.db` が単一ファイルで完結
7. note-neo4j で `MATCH (c:SessionChunk)-[:MENTIONS]->(e:Entity) RETURN count(c)` が妥当
8. プロジェクト別にセッション・チャンクが正しく分離されている
9. 中断・再開が安全に動作する（`extraction_log` でスキップ）

---

## 参照ファイル（実装時に読むべき）

- `src/rss/storage/scrape_state_db.py` — SQLite コンテキストマネージャ参照パターン
- `src/academic/cache.py` — SQLite キャッシュパターン
- `scripts/entity_linker.py` — 4層マッチング戦略、embedding 遅延ロードパターン
- `docs/plan/SideBusiness/2026-03-22_fuzzy-matching-design.md` — fuzzy matching 設計
- `docs/plan/SideBusiness/2026-03-22_entity-normalization.md` — エンティティ正規化ルール
- `.claude/settings.json:154-165` — 既存 Hook 設定
- `template/src/template_package/` — パッケージテンプレート

---

## 議論履歴

- `docs/plan/SideBusiness/2026-03-24_discussion-session-memory-architecture.md` — 全合意事項（20件）
- note-neo4j: `disc-2026-03-24-session-memory-architecture` + `disc-2026-03-24-session-memory-chunk-design`
