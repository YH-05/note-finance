# 議論メモ: topic-suggest への KG マイニング統合 + 自記事 research-neo4j 投入

**日付**: 2026-04-27
**参加**: ユーザー + AI

## 背景・コンテキスト

`/topic-discovery` を非推奨化（disc-2026-04-27-topic-discovery-deprecation）した結果、KG マイニング機能が失われた。これを `topic-suggest` スキルに段階的に取り込み、加えて株投資ラボ自身のnote記事も research-neo4j に投入することで「自分の知識ギャップ」を抽出可能にする方針で合意。Phase 1 → Phase 2 の順で実装。

## 議論のサマリー

- **Phase 1**: topic-suggest スキルを KG マイニング統合版に再構成。旧 `/topic-discovery` の 8 Cypher クエリと scoring-rubric を `references/` に移植。新たにローカル `articles/` マイニングスクリプト（58記事の集計）を追加。
- **Phase 2**: 株投資ラボの note 記事を `Source` ノード（`source_type='blog'`, `command_source='own-articles'`）として research-neo4j に投入するパイプラインを構築。`OwnArticlesMapper` を `BaseMapper` に追加し、emit_research_queue.py に `own-articles` コマンドを統合。58記事 + 64 Topic + 各種リレーションを投入完了。
- **Phase 2-D**: 自記事に絞った 5 クエリ（OWN-Q1〜Q5）を `kg-own-article-mining.md` に追加。Underexplored / Coverage Gap / Counter-Claim / Recurring Series 4種の候補生成に対応。
- **誤った提案の訂正**: 自動化手段として `/schedule` を提案したが、リモート実行のためローカル Neo4j・articles/ にアクセス不可と判明。撤回し、launchd/cron/手動運用/ワークフロー組込みの4案を提示。

## 決定事項

1. `topic-suggest` スキルを Phase 0 (KG + ローカル) → Phase 1 (Web) → Phase 2 (スコアリング) → Phase 3 (提示) の 4 フェーズ構成に再編する。
2. 株投資ラボのnote記事を research-neo4j に投入する。識別子は `source_type='blog'` + `command_source='own-articles'`。
3. meta.yaml の主要フィールド（article_id, category, target_audience, target_wordcount, status, type, symbols 等）を Source プロパティに保存する。dict 型フィールドは stringify でフラット化。
4. revised_draft.md は `02_draft/revised_draft.md` 等のサブディレクトリ構造にも対応した複数候補探索方式で取り込む。
5. 自記事専用クエリは別ファイル（`kg-own-article-mining.md`）に分離し、5 クエリ（OWN-Q1〜Q5）で構成する。
6. 自記事再投入の自動化方式は未定（launchd / cron / 手動 / ワークフロー組込み から選択予定）。

## アクションアイテム

- [x] `scripts/mine_local_articles.py` 新設
- [x] `kg-topic-mining.md` を topic-suggest 配下に移植（KG v3 個別ラベル準拠）
- [x] `topic-suggest/SKILL.md` を 4 フェーズ構成に再構成、`--no-search` / `--skip-kg` オプション明記
- [x] `scripts/mappers/own_articles.py` (OwnArticlesMapper) 新設
- [x] `scripts/mappers/__init__.py` に `own-articles` コマンド登録
- [x] `scripts/emit_own_articles_queue.py` 新設（articles 走査 + emit_research_queue 呼び出し）
- [x] 全58記事を research-neo4j に投入（128 nodes, 242 relations）
- [x] `kg-own-article-mining.md` 新設（OWN-Q1〜Q5）
- [ ] 自記事再投入の自動化方式を確定（launchd / cron / 手動 / `/article-publish` hook 組込み のいずれか）（優先度: 中）
- [ ] OWN-Q1〜Q5 を実際の topic-suggest 実行で検証（優先度: 中）
- [ ] revised_draft.md の本文を Chunk として投入する v2 拡張を検討（優先度: 低）

## 次回の議論トピック

- 自記事再投入の自動化方式の選定。`/article-publish` 完了 hook で自動投入する案が運用負荷ゼロで有力。
- `save-to-article-graph` スキルの `--command topic-discovery` オプション値を `--command topic-suggest` にリネームするか、新規 `--command own-articles` を追加するかの方針。
- 自記事 Source から Fact/Claim 抽出（Chunk + LLM 構造化）を行うか。

## 影響を受けたファイル

- `.claude/skills/topic-suggest/SKILL.md`
- `.claude/skills/topic-suggest/references/kg-topic-mining.md` (新規)
- `.claude/skills/topic-suggest/references/kg-own-article-mining.md` (新規)
- `.claude/skills/topic-suggest/references/scoring-rubric.md` (新規)
- `scripts/mine_local_articles.py` (新規)
- `scripts/emit_own_articles_queue.py` (新規)
- `scripts/mappers/own_articles.py` (新規)
- `scripts/mappers/__init__.py`
- `docs/plan/2026-04-27_own-articles-research-neo4j-pipeline.md` (新規・設計メモ)

## 投入実績

```cypher
MATCH (s:Source {command_source: 'own-articles'}) RETURN count(s)
// → 58
```

カテゴリ分布: asset_management 16, earnings 10, stock_analysis 8, macro_economy 6, investment_education 4, market_report 2（published のみ）

## 反省点

- `/schedule` をローカルジョブの自動化に提案した誤り。リモートエージェントの制約（ローカル Neo4j・ローカルファイル不可）を踏まえずに提案した。今後は提案前に「実行環境とリソース要求」を確認する。
