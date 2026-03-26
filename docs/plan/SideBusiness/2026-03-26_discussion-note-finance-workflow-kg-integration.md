# 議論メモ: note-financeワークフローへのKG統合

**日付**: 2026-03-26
**参加**: ユーザー + AI

## 背景・コンテキスト

research-neo4jに蓄積したデータ（Entity: 1016件、Source: 1796件、Fact: 1602件、Claim: 1039件、FinancialDataPoint: 453件）を、note記事執筆ワークフローに活用する方針を検討。毎回Web検索に頼るのではなく、既存のKGデータをファーストソースとして使うことでコスト削減と品質向上を図る。

## 議論のサマリー

### 論点1: topic-discoveryのKGファースト化

現行のfinance-suggest-topics（→ topic-discovery）はWeb検索を常時実行しており、LLMコストがかかっていた。research-neo4jのデータが十分蓄積された現時点で、KGファースト設計に切り替えることを検討。

- Phase 0: research-neo4jから候補抽出（8クエリ）
- Phase 0-C: KG充足性評価 + [HF0] ユーザー確認ゲート
- Phase 1: ユーザーが承認した場合のみWeb検索を実行

アナリスト意見（Claim）がない領域でも、Factとソースがあれば記事執筆は可能。KGカバレッジの薄さを別途示すことで対応。

### 論点2: FinancialDataPointの自動チャート化（却下）

neo4jのFinancialDataPointからチャートを自動生成してドラフトに埋め込む提案。しかし「neo4jに入れている数値データは完全ではない」との理由で却下。不完全データからの自動チャートは誤解を招くリスクがある。

### 論点3: /kg-summaryコマンドの新設

記事作成時点でKGデータの充足度を把握するための単体コマンド。LLMを使わずCypherクエリのみで実行。

5クエリ構成:
- Q1: Entity別Fact/Claim/Source件数
- Q2: データ鮮度（最新ソース公開日）
- Q3: 未回答Question
- Q4: Claimセンチメント分布
- Q5: FinancialDataPoint件数

閾値判定（LLMなし）:
- 最新ソース > 30日前 → ⚠ データが古い
- Fact + Claim < 5件 → ⚠ KGカバレッジ薄
- openQuestion > 0件 → ⚠ 未回答Question残存

### 論点4: article-initへのPhase 5自動KGサマリー

article-init完了時に自動でKGサマリーを実行したいが、Claude Codeのhookはツールレベルイベント（PreToolUse/PostToolUse）のみ対応しており、スラッシュコマンド完了イベントはサポートしない。そのため、article-initのPhase 4直後にPhase 5としてインライン埋め込みで実装。

### 論点5: コマンド名の統一

/finance-suggest-topicsとtopic-discoveryスキルで名前が不一致だった。コマンド名をスキル名に揃えて/topic-discoveryにリネーム。旧パス（/finance-suggest-topics）にはリダイレクトスタブを残す。

## 決定事項

1. **topic-discovery KGファースト設計を採用** — Phase 0-CでKG充足性を評価し、[HF0]でユーザーがWeb検索の要否を判断する
2. **FinancialDataPoint自動チャート化を却下** — データが不完全なため
3. **/kg-summaryコマンドを新設（LLM不使用）** — Cypherクエリのみ、閾値ベース判定
4. **article-initにPhase 5を追加** — 完了後に自動でKGサマリーを実行（Neo4j未起動時は無言スキップ）
5. **/finance-suggest-topicsを/topic-discoveryにリネーム** — CLAUDE.mdも更新済み

## アクションアイテム

- [ ] article-draftでKGコンテキストをドラフトに注入する仕組みを実装する（優先度: 中）
  - Entity別のFact/Claim/FinancialDataPointを取得してプロンプトに含める
  - 記事が十分蓄積されたタイミングで実装を検討

## 次回の議論トピック

- 記事フィードバックループ（公開記事のパフォーマンスデータをKGに還元する仕組み）— 記事蓄積後に検討
- article-draftへのKGコンテキスト注入の具体的な実装設計

## 実装済み変更

| ファイル | 変更内容 |
|---------|---------|
| `.claude/commands/topic-discovery.md` | 新設（旧finance-suggest-topicsをリネーム） |
| `.claude/commands/finance-suggest-topics.md` | リダイレクトスタブに変換 |
| `.claude/commands/kg-summary.md` | 新設（LLM不使用、Cypherのみ） |
| `.claude/commands/article-init.md` | Phase 5（KGサマリー）を追加 |
| `.claude/skills/topic-discovery/SKILL.md` | Phase 0-CとHF0ゲートを追加 |
| `CLAUDE.md` | コマンド一覧を更新（topic-discovery/kg-summary追加、finance-suggest-topics非推奨化） |
