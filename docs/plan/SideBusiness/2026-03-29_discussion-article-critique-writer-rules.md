# 議論メモ: article-critique に finance-writer-rules チェックを追加

**日付**: 2026-03-29
**参加**: ユーザー + AI

## 背景・コンテキスト

`/article-critique` コマンドは5つの批評エージェント（fact, compliance, structure, data, readability）で記事を評価するが、
これらは `.claude/resources/critique-criteria/` の汎用基準で動作しており、
`finance-article-writer` スキル（`.claude/skills/finance-article-writer/references/`）が定義するルールを直接チェックしていなかった。

初稿生成時に守られたルールが批評時に検証されないため、修正版で崩れても検出できないリスクがあった。

### 対象外だったルール

- **文字数要件**: stock: 4000-6000字、macro: 3000-5000字、asset: 2000-4000字 等
- **必須セクション構成**: カテゴリ別テンプレート順序
- **フロントマター必須項目**: symbol, indicators, topic, strategy, theme 等
- **信頼度別表現パターン**: verified→断定形、unverified→伝聞形 等
- **カテゴリ固有制約**: macro→シナリオ分析、education→FAQ、quant→バックテスト透明性 等

## 実装内容

### 新規作成ファイル

1. **`.claude/agents/finance-critic-writer-rules.md`**
   - finance-article-writer の執筆ルール準拠を検証する新規批評エージェント
   - quick モード: word_count / sections / frontmatter（3サブエリア）
   - full モード: + confidence_expression / category_constraints / checklist（6サブエリア）
   - スコア計算: `100 - (high x 15 + medium x 5 + low x 2)`

2. **`.claude/resources/critique-criteria/writer-rules-evaluation.md`**
   - カテゴリ別文字数範囲テーブル（6カテゴリ）
   - カテゴリ別必須セクションリスト
   - カテゴリ別フロントマター必須項目
   - 信頼度→表現パターン対応表
   - カテゴリ固有制約チェックリスト
   - 他エージェントカバー済み項目（スキップ対象）の明示

### 修正ファイル

3. **`.claude/commands/article-critique.md`**
   - Step 2: quick モードにTask 3（finance-critic-writer-rules, 3サブエリア）追加
   - Step 2: full モードにTask 6（finance-critic-writer-rules, 全項目）追加
   - Step 3: critic.json スキーマに `"writer_rules"` キー追加
   - Step 3: critic.md テンプレートにライター規約準拠セクション追加
   - 完了報告テーブルに `| ライター規約 | {writer_rules}/100 |` 追加

4. **`.claude/resources/critique-criteria/scoring-methodology.md`**
   - writer_rules スコア計算式追加
   - 総合スコア重みを5→6エージェント体制に再配分:
     - compliance: 30% → 25%
     - fact: 25% → 22%
     - data_accuracy: 20% → 17%
     - structure: 15% → 12%
     - readability: 10% → 9%
     - writer_rules: 0% → **15%**（新設）
   - quick モード重み追加: compliance 45%, fact 35%, writer_rules 20%

5. **`.claude/agents/finance-reviser.md`**
   - 修正優先順位に writer_rules を追加（4位: high、7位: medium）
   - writer_rules 修正方針セクション追加
   - 修正履歴テンプレートに `- writer_rules 修正: {count}` 追加

## 決定事項

1. **新規批評エージェント `finance-critic-writer-rules` を追加**
   - quick モードでも文字数・セクション・フロントマターをチェック（機械的判定かつ高インパクト）
   - 他エージェントとの重複回避ルールを明示（compliance/fact 済み項目はスキップ）

2. **scoring-methodology を6エージェント体制に再配分**
   - writer_rules 15%: 仕様準拠違反は構造的問題で compliance より低いが structure/readability より高い

3. **finance-reviser の修正優先順位に writer_rules を組み込み**
   - writer_rules high 問題（文字数不足等）は記事の基本要件不満なので structure より高優先

## アクションアイテム

- [x] finance-critic-writer-rules.md 作成（完了）
- [x] writer-rules-evaluation.md 作成（完了）
- [x] article-critique.md 修正（完了）
- [x] scoring-methodology.md 修正（完了）
- [x] finance-reviser.md 修正（完了）
- [ ] 既存記事でテスト実行（`/article-critique @articles/stock_analysis/2026-03-28_us-telecom-sector/ --mode full`）

## 次回の議論トピック

- writer_rules エージェントの実際の動作検証（既存記事でのテスト実行）
- side_business カテゴリへの writer_rules 拡張（experience 記事のルールチェック）
