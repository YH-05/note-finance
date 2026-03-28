# 議論メモ: ask-research-neo4j スキル作成

**日付**: 2026-03-28
**参加**: ユーザー + AI

## 背景・コンテキスト

research-neo4j（bolt://localhost:7688）に蓄積���れたKGデータ（Entity 1609件, Fact 2911件, Claim 2158件, Source 2720件, FDP 453件）を活用し��ユーザーの質問にKGデータのみで回答するスキルが必要だった。既存スキルとの差別化ポイント:

- `/kg-summary`: LLM不使用、数値サマリーのみ
- `/investment-research`: KG照会 + 外部Web検索
- **`/ask-research-neo4j`（新規）**: KGデータのみでLLMが回答を合成

## 議論のサマリー

1. スキーマ調査（research-get_neo4j_schema）で全ラベル・プロパティ・リレーションを確認
2. 既存スキル（kg-summary, investment-research, topic-discovery）のクエリパターンを参照
3. 7種のCypherクエリテンプレート（Q1-Q7）を設計し、実データで動作検証
4. Fact→Source接続パスが3種あることを発見（STATES_FACT逆, SOURCED_FROM, EXTRACTED_FROM→Chunk→Source）
5. FinancialDataPoint→Metric は MEASURES リレーション��主接続（FOR_METRIC は補助）
6. Claim.sentiment は文字列("bullish"等)とFLOAT(-1.0〜1.0)の混在を確認

## 決定事項

1. **KGデータのみで回答**する設計方針。LLM事前学習知識での補完は禁止
2. **適応的クエリ方式**: question_type に応じてQ1-Q7から必要ク��リのみ実行
3. **Fact→Source接続**: 3パスを coalesce で統合。Metric への接続は MEASURES を使用

## 作成したファイル

| ファイル | 説明 |
|---------|------|
| `.claude/skills/ask-research-neo4j/SKILL.md` | スキル本体（277行） |
| `.claude/commands/ask-research-neo4j.md` | スラッシュコマンド |

## アクションアイテム

- [ ] テストケース実行・回答品質評価（NVIDIA業績 / イン��ネシア通信 / KGに存在しないテーマ）(優先度: 中)
- [ ] /sync-claude-gemini で Gemini 側に同期 (優先度: 低)

## 次回の議論トピック

- テスト結果に基づくスキル改善（クエリ最適化、出力フォーマット調整）
- 全文検索（Fact.content への全文インデックス）の検討
