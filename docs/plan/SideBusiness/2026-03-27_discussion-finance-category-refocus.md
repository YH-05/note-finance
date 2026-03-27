# 議論メモ: 金融記事カテゴリ再編 — side_business除外・投資分析特化

**日付**: 2026-03-27
**参加**: ユーザー + AI

## 背景・コンテキスト

note.com 金融記事プロジェクトで、side_business（副業系）カテゴリを除外し、純粋な投資分析・市場分析・資産形成にテーマを絞る方針を決定。副業系コンテンツはcreator系アカウント（キャリアお姉さん、self-dev、みつき）で別途運用する。

## 議論のサマリー

- ユーザーが金融記事のテーマを純粋な投資分析・市場分析・資産形成に絞りたいと提案
- investment_education は残す（side_business のみ除外）
- 既存 side_business 記事3本と関連スキル・エージェントを一括で trash/ に移動
- 設定ファイル内の side_business 参照も全箇所除去

## 決定事項

1. **カテゴリ構成**: 5カテゴリ体制に確定
   - macro_economy（市場分析）
   - stock_analysis（投資分析）
   - asset_management（資産形成）
   - investment_education（投資教育）
   - market_report（週次レポート）

2. **side_business 関連の廃止**: 以下を `trash/2026-03-27_sidebiz-removal/` に移動
   - 記事3本（articles/side_business/）
   - スキル4個（case-study-writer, case-study-critique, experience-db-workflow, experience-db-critique）
   - エージェント12個（csa-critic-* 4個, exp-critic-* 4個, experience-* 3個, case-study-writer）
   - テンプレート2個（事例分析型テンプレート_v1.md, 体験談DB統一テンプレート_v2.md）

3. **設定ファイル更新**: 8箇所から side_business 参照を除去
   - topic-discovery/SKILL.md, references/neo4j-mapping.md
   - generate-image-prompt/SKILL.md, guide.md
   - x-post-generator/SKILL.md（2箇所）, templates/hook-patterns.md, references/README.md

## アクションアイテム（全て完了 2026-03-27）

- [x] note-neo4j に Decision 保存
- [x] articles/side_business/ を trash/ に移動
- [x] 関連スキル・エージェントを trash/ に移動
- [x] 設定ファイルの side_business 参照を除去（8箇所）
- [x] emit_research_queue.py の TOPIC_DISCOVERY_CATEGORIES から side_business 除去
- [x] migrate_articles.py の CATEGORY_MAP/TYPE_MAP から side_business 除去
- [x] test_emit_graph_queue.py・test_migrate_articles.py を5カテゴリ体制に修正
- [x] topic-suggester.md から side_business セクション除去
- [ ] note.com 上に公開済みの side_business 記事があれば非公開化（低優先度）

## 次回の議論トピック

- note.com 上に既に公開済みの side_business 記事の扱い（非公開化？）
