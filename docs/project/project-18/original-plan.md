# cognee スキル改善パターンの適用計画

## Context

cognee (v0.5.4) の自動スキル改善ループ（Observe → Inspect → Amend → Evaluate）を、本プロジェクトの Claude Code スキルシステム（57スキル + 64エージェント）に適用する。cognee SDK は使わず、パターンを抽出して独自実装する。

**動機**: 現在スキル実行のトレースが一切なく、フィードバックは手動（`feedback_*.md` 3件のみ）。スキル品質の経年劣化が追跡できない。

**成果物**: SkillRun ログ基盤 → 分析スキル → 改善提案機能の3段階。

---

## Phase A: Observe（スキル実行ログ基盤）— 5日

### A-1: SkillRun サブラベル登録

**変更ファイル**: `.claude/rules/neo4j-namespace-convention.md`

Memory 許可サブラベル一覧テーブルに追加:

```
| SkillRun | スキル実行トレース |
```

### A-2: Neo4j Constraint/Index 追加

**変更ファイル**: `docker/research-neo4j/init/01-constraints-indexes.cypher`

末尾に追加:
```cypher
// === Skill Observability (Memory:SkillRun) ===
CREATE CONSTRAINT skill_run_id IF NOT EXISTS FOR (sr:SkillRun) REQUIRE sr.skill_run_id IS UNIQUE;
CREATE INDEX skill_run_name IF NOT EXISTS FOR (sr:SkillRun) ON (sr.skill_name);
CREATE INDEX skill_run_status IF NOT EXISTS FOR (sr:SkillRun) ON (sr.status);
CREATE INDEX skill_run_start IF NOT EXISTS FOR (sr:SkillRun) ON (sr.start_at);
CREATE INDEX skill_run_command IF NOT EXISTS FOR (sr:SkillRun) ON (sr.command_source);
```

**新規ファイル**: `scripts/migrate_skill_run_schema.py`
- research-neo4j (`bolt://localhost:7688`) に上記制約を適用するマイグレーションスクリプト
- `scripts/validate_neo4j_schema.py` の Neo4j ドライバーパターンを再利用

### A-3: Python ユーティリティ作成

**新規ファイル**: `scripts/skill_run_tracer.py`

CLI インターフェース（`scripts/emit_graph_queue.py` パターンに準拠）:

```bash
# 実行開始（skill_run_id を stdout に返す）
python3 scripts/skill_run_tracer.py start \
    --skill-name save-to-graph \
    --command-source /save-to-graph \
    --input-summary "3 graph-queue files"

# 実行完了
python3 scripts/skill_run_tracer.py complete \
    --skill-run-id <id> \
    --status success \
    --output-summary "45 nodes, 62 relations"

# 失敗記録
python3 scripts/skill_run_tracer.py complete \
    --skill-run-id <id> \
    --status failure \
    --error-message "Neo4j connection refused" \
    --error-type neo4j_connection

# フィードバック記録
python3 scripts/skill_run_tracer.py feedback \
    --skill-run-id <id> --score 0.8
```

**設計ポイント**:
- ノードラベル: `Memory:SkillRun`（デュアルラベルで Memory 名前空間に所属）
- ID 生成: `SHA-256[:32]` of `skill_name:session_id:start_at`（`src/pdf_pipeline/services/id_generator.py` パターン）
- Neo4j 接続: `bolt://localhost:7688`（`scripts/validate_neo4j_schema.py` のドライバーパターン再利用）
- グレースフルデグラデーション: Neo4j 未起動時は警告のみ出力、合成 ID を返す（スキル実行をブロックしない）
- 依存: `neo4j` + `structlog`（既存依存）

**SkillRun ノードプロパティ**:

| プロパティ | 型 | 必須 | 説明 |
|-----------|-----|------|------|
| skill_run_id | string | UNIQUE | SHA-256[:32] |
| skill_name | string | Yes | スキル名（SKILL.md の name） |
| status | string | Yes | success / failure / partial / timeout |
| command_source | string | No | 呼び出し元コマンド |
| session_id | string | No | セッション ID |
| start_at | datetime | Yes | 開始時刻 |
| end_at | datetime | No | 終了時刻 |
| duration_ms | integer | No | 実行時間 |
| input_summary | string | No | 入力概要（max 500字） |
| output_summary | string | No | 出力概要（max 500字） |
| error_message | string | No | エラー内容 |
| error_type | string | No | エラー分類 |
| feedback_score | float | No | 品質スコア 0.0-1.0 |
| metadata | string | No | JSON シリアライズ追加情報 |

**リレーション**:

| 型 | From | To | 説明 |
|----|------|-----|------|
| INVOKED_SKILL | SkillRun | SkillRun | 親→子（オーケストレータパターン） |
| PRODUCED | SkillRun | Source/Entity/Topic | KG ノード生成の追跡 |

### A-4: 主要スキル 5 つへの初期統合

各 SKILL.md に「Observability」セクションを追加。Phase 開始時に `start`、完了時に `complete` を呼ぶ。

| スキル | パス | 理由 |
|--------|------|------|
| save-to-graph | `.claude/skills/save-to-graph/SKILL.md` | 最重要パイプライン、失敗頻度高 |
| pdf-to-knowledge | `.claude/skills/pdf-to-knowledge/SKILL.md` | 4Phase オーケストレータ、カスケード失敗 |
| topic-discovery | `.claude/skills/topic-discovery/SKILL.md` | 高頻度、品質のばらつき大 |
| generate-market-report | `.claude/skills/generate-market-report/SKILL.md` | 週次定期、トレンド分析に最適 |
| experience-db-critique | `.claude/skills/experience-db-critique/SKILL.md` | 4並列エージェント、品質スコア直接記録 |

**統合パターン（全スキル共通）**:
```markdown
### Observability

Phase 開始時:
SKILL_RUN_ID=$(python3 scripts/skill_run_tracer.py start \
    --skill-name {name} --command-source "{cmd}" \
    --input-summary "{summary}")

Phase 完了時:
python3 scripts/skill_run_tracer.py complete \
    --skill-run-id "$SKILL_RUN_ID" --status success \
    --output-summary "{result}"
```

### A-5: 検証

```bash
# 1. マイグレーション実行
python3 scripts/migrate_skill_run_schema.py

# 2. テスト記録
SRID=$(python3 scripts/skill_run_tracer.py start --skill-name test-skill --command-source test)
python3 scripts/skill_run_tracer.py complete --skill-run-id "$SRID" --status success

# 3. Neo4j で確認
# bolt://localhost:7688 で以下を実行:
MATCH (sr:Memory:SkillRun) RETURN sr.skill_name, sr.status, sr.start_at LIMIT 10

# 4. スキーマ検証
python3 scripts/validate_neo4j_schema.py --neo4j-uri bolt://localhost:7688
```

---

## Phase B: Inspect（分析）— 4日

依存: Phase A 完了

### B-1: Cypher クエリライブラリ

**新規ファイル**: `.claude/skills/skill-analytics/queries.md`

主要クエリ:
- スキル実行頻度（過去30日）
- スキル別失敗率
- 平均実行時間トレンド（週次バケット）
- エラータイプ別発生数
- オーケストレータ→子のカスケード失敗パターン
- KG ノード生産性（PRODUCED リレーション集計）

### B-2: skill-analytics スキル新設

**新規ディレクトリ**: `.claude/skills/skill-analytics/`

```yaml
---
name: skill-analytics
description: |
  スキル実行トレースの分析。SkillRun Neo4jデータから失敗パターン、
  パフォーマンストレンド、利用頻度を分析。
  Use PROACTIVELY when reviewing skill performance or after skill failures.
allowed-tools: Read, Bash, Grep, Glob
---
```

ワークフロー:
1. research-neo4j に接続
2. ユーザー意図に応じたクエリ実行（失敗分析 / パフォーマンス / 利用状況）
3. Markdown テーブルでレポート出力

### B-3: feedback_*.md との構造的連携

`skill_run_tracer.py` に `feedback` サブコマンドで、`feedback_score` 更新 + 既存 `feedback_*.md` との参照リレーション作成機能を追加。

### B-4: 検証

- テスト SkillRun を数件記録した上で、queries.md の全クエリが正常に動作することを確認
- `/skill-analytics` を実行して読みやすいレポートが生成されることを確認

---

## Phase C: Amend（改善提案）— 4日

依存: Phase B 完了 + SkillRun 20件以上蓄積

### C-1: 改善提案テンプレート

**新規ファイル**: `.claude/skills/skill-expert/improvement-template.md`

構造: Evidence（実行データ）→ Issues → Proposed Changes → Rollback Criteria → Verification

### C-2: skill-creator に改善提案モード追加

**変更ファイル**: `.claude/agents/skill-creator.md`

「ステップ 6: 改善提案モード (Amend)」を追加:
- 失敗率 > 15% or フィードバックスコア < 0.6 のスキルに対して起動
- SkillRun データを分析 → 改善提案を生成 → ユーザー承認後に適用

### C-3: Critique スキルとの統合

**変更ファイル**:
- `.claude/skills/experience-db-critique/SKILL.md` — Phase 6 追加（スコアを SkillRun に記録）
- `.claude/agents/finance-critic-*.md` 系 — 同様のスコア記録

### C-4: 評価ループ（Evaluate）

**新規ファイル**: `.claude/skills/skill-analytics/evaluation-guide.md`

プロトコル:
1. 修正前 10 件の SkillRun をベースライン化
2. 修正適用 → 3-5 回実行
3. 比較 Cypher で改善効果を測定
4. 失敗率 20%↓ or フィードバック 0.1↑ → Keep、それ以外 → Rollback

---

## 依存関係

```
A-1 (スキーマ登録) → A-2 (制約/インデックス) → A-3 (tracer CLI)
                                                  ↓
                                            A-4 (スキル統合) → A-5 (検証)
                                                  ↓
                                            B-1 (クエリ集) → B-2 (analytics スキル)
                                                  ↓
                                            B-3 (feedback連携) → B-4 (検証)
                                                  ↓
                                            C-1 (テンプレート) → C-2 (skill-creator 拡張)
                                                  ↓              ↓
                                            C-3 (critique 統合)  C-4 (評価ループ)
```

## 工数見積

| Phase | 内容 | 工数 | 1h/日換算 |
|-------|------|------|-----------|
| A: Observe | ログ基盤 + 5スキル統合 | 5h | 5日 |
| B: Inspect | 分析クエリ + analytics スキル | 4h | 4日 |
| C: Amend | 改善提案 + 評価ループ | 4h | 4日 |
| **合計** | | **13h** | **13日** |

## リスク軽減

| リスク | 対策 |
|--------|------|
| Neo4j 未起動 | tracer はグレースフルデグラデーション（警告のみ、合成ID返却） |
| KG v2 汚染 | `Memory:SkillRun` デュアルラベルで完全分離。既存 `WHERE NOT 'Memory'` パターンで除外 |
| パイプライン破壊 | `emit_graph_queue.py` / `save-to-graph` のコアロジックは変更しない |
| 実行オーバーヘッド | 1回あたり MERGE 2回のみ（~5-10 runs/日で無視可能） |

## 再利用する既存リソース

| ファイル | 再利用内容 |
|---------|-----------|
| `scripts/validate_neo4j_schema.py` | Neo4j ドライバー接続パターン、スキーマ検証ロジック |
| `scripts/emit_graph_queue.py` | CLI 設計パターン（argparse + structlog） |
| `scripts/session_utils.py` | get_logger、Pydantic モデルパターン |
| `src/pdf_pipeline/services/id_generator.py` | SHA-256 ベース ID 生成 |
| `.claude/skills/skill-expert/guide.md` | スキル品質基準の参照元 |
| `.claude/agents/skill-creator.md` | Phase C で改善提案モード追加先 |
