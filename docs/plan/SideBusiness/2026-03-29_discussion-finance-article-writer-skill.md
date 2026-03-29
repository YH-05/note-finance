# 議論メモ: finance-article-writer スキル実装・エージェント移行

**日付**: 2026-03-29
**参加**: ユーザー + AI

## 背景・コンテキスト

`/article-draft` コマンドが呼び出す記事執筆ロジックを、エージェントベースからスキルベースに移行する作業。
また asset-management-writer エージェントのルールを統合し、カテゴリ別にルールファイルを整理した。

## 議論のサマリー

### 1. スキル実装

finance-article-writer スキルを以下の構成で実装した:

```
.claude/skills/finance-article-writer/
├── SKILL.md                      # オーケストレーター（6ステップフロー）
└── references/
    ├── common-rules.md           # 全カテゴリ共通ルール
    ├── stock-analysis.md         # 株式分析
    ├── macro-economy.md          # マクロ経済分析
    ├── investment-education.md   # 投資教育
    ├── quant-analysis.md         # クオンツ分析
    ├── market-report.md          # 週次市場レポート
    └── asset-management.md       # 資産形成
```

SKILL.md はオーケストレーターとして:
1. 入力検証（article_dir / カテゴリ確認）
2. ルール読み込み（common-rules.md + カテゴリ別ルール）
3. general-purpose Agent を起動（ルール埋め込み済みプロンプト）
4. 出力検証（first_draft.md 存在確認、文字数チェック）
5. meta.yaml の workflow.draft を "done" に更新
6. 完了レポート

### 2. エージェント移行

既存エージェントをtrash/に移動:
- `trash/finance-article-writer.md` （元: `.claude/agents/`）
- `trash/asset-management-writer.md` （元: `.claude/agents/`）

`/article-draft` コマンドの処理フローを更新:
- Before: カテゴリ別に個別エージェントを起動
- After: 全カテゴリで `Skill("finance-article-writer")` を起動（side_business除く）

### 3. ディスクレーマー統一

全カテゴリテンプレートのディスクレーマー配置を統一:
- Before: 冒頭に `> **本記事について**:` + 末尾にリスク開示の二重配置
- After: 記事本文の一番最後に1箇所のみ

統一ディスクレーマー文:
```
> 本記事は一般的な情報提供を目的としており、特定の金融商品の売買を推奨するものではありません。
> 投資には元本割れリスクがあります。投資に関する最終決定は、ご自身の判断と責任において行ってください。
```

quant-analysis の場合はバックテスト免責も統合:
```
> 本記事は戦略の検証結果を共有するものであり、将来のパフォーマンスを保証するものではありません。
> バックテスト結果は過去のデータに基づくシミュレーションであり、実際の運用では取引コスト、スリッページ、
> 流動性リスク等により結果が異なる可能性があります。投資に関する最終決定は、ご自身の判断と責任において行ってください。
```

## 決定事項

1. finance-article-writer はエージェントではなくスキルとして実装する
   - 理由: カテゴリ別ルールのファイル分けが容易、SKILL.md がオーケストレーターとして機能
2. ディスクレーマーは記事本文の一番最後に1箇所だけ挿入する
   - 理由: 冒頭配置は読者に不快感を与え、記事の導入が重くなるため
3. 既存エージェント（finance-article-writer, asset-management-writer）を trash/ に移行
   - 理由: スキルベースに移行したため不要。trash/ 規約に従い削除はせず移動。

## アクションアイテム

- [ ] 記事 publish 4本 (優先度: 高)
  - FOMC入門
  - インデックス投資入門
  - オルカン vs S&P500
  - US テレコムセクター
- [ ] Indonesia Telecom 記事 review → publish 3本 (優先度: 高)

## 次回の議論トピック

- finance-article-writer スキルを使った実際の記事生成のフィードバック
- asset-management カテゴリのソースキュレーション（curated_sources.json）フロー

## 参考情報

- スキルファイル: `.claude/skills/finance-article-writer/`
- マイグレーションプラン: `docs/plan/2026-03-29_finance-article-writer-skill-migration.md`
