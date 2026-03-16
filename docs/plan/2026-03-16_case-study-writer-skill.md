# 事例分析型執筆ルールスキル（case-study-writer）の作成

## Context

2026-03-09に「副業・資産形成は事例分析型に転換」と決定したが、実際の記事は合成パターン法で作られていた。
2026-03-16の議論で事例分析型への統一を再確認（disc-2026-03-16-sidebiz-article-format）。
side_business カテゴリ用の文体・構成ルールスキルが未定義のため、新規作成する。

## 実装スコープ

| # | 作業 | ファイル | 変更量 |
|---|------|---------|--------|
| 1 | 執筆ルールスキル新規作成 | `.claude/skills/case-study-writer/SKILL.md` | 新規 ~350行 |
| 2 | ライターエージェント新規作成 | `.claude/agents/case-study-writer.md` | 新規 ~50行 |
| 3 | article-init コマンド修正 | `.claude/commands/article-init.md` | type選択分岐追加 |
| 4 | article-draft コマンド修正 | `.claude/commands/article-draft.md` | side_business分岐追加 |
| 5 | article-research コマンド修正 | `.claude/commands/article-research.md` | side_business分岐追加 |
| 6 | article-critique コマンド修正 | `.claude/commands/article-critique.md` | side_business分岐追加 |
| 7 | Neo4j 復旧 + ノード投入 | Docker コンテナ再起動 | 運用作業 |

## Step 1: Neo4j 復旧

Neo4j（note-finance コンテナ）が critical error で停止中。

```bash
docker restart note-finance-neo4j  # コンテナ名を確認して再起動
```

復旧後、disc-2026-03-16 の Decision/ActionItem ノードを投入（保留中のクエリを実行）。

## Step 2: 執筆ルールスキル作成

**ファイル**: `.claude/skills/case-study-writer/SKILL.md`

**構造**（mary-tone-writer に準拠した単一ファイル構成）:

```
セクション 1: ペルソナ・スタンス
  - 三人称の分析者視点（「〜した人がいる」「〜という事例がある」）
  - データ・数字を多用、主張には根拠を添える
  - 読者との距離感: 専門家が分かりやすく解説（上から目線でない）

セクション 2: テンプレート選択ガイド
  - A: ジャンル別事例分析
  - B: ジャンル横断共通点分析（横断型パターン抽出）
  - C: AI一人スタートアップ事例分析（看板シリーズ）
  - meta.yaml の case_study.template_type で判定

セクション 3-5: テンプレートA/B/C の構成定義
  - 各セクションの目的・文字数目安・必須要素
  - [EMBED] マーカー配置ルール
  - 原本参照: docs/plan/SideBusiness/事例分析型テンプレート_v1.md

セクション 6: 文体・トーンルール
  - 基本: 分析者視点の「です・ます」調
  - 一人称禁止（「私は」→ 主語省略 or 「分析すると」「見えてくるのは」）
  - 数字の具体性（「稼いだ」→「月3.2万→6ヶ月後に月8万」）
  - 比較と対比を必ず含める
  - セクション末尾に問いかけ

セクション 7: 共通ルール
  - 文字量: 6,000-8,000字（最低5,500字）
  - 埋め込みリンク: [EMBED] 位置に1-3個
  - 禁止語: 「誰でもできる」「簡単に稼げる」「必ず成功」

セクション 8: 品質チェックリスト（自己チェック用）

セクション 9: 禁止事項
```

**再利用するリソース**:
- テンプレート構成定義: `docs/plan/SideBusiness/事例分析型テンプレート_v1.md`
- 文体参考: `.claude/skills/mary-tone-writer/SKILL.md`
- 批評基準（参照のみ）: `.claude/resources/case-study-criteria/`

## Step 3: ライターエージェント作成

**ファイル**: `.claude/agents/case-study-writer.md`

**テンプレート**: `.claude/agents/experience-writer.md` に準拠

```yaml
---
name: case-study-writer
description: 事例分析データから事例分析型記事の初稿（6000-8000字）を生成するエージェント
---
```

- 入力: `01_research/` 配下のソース・事例データ + `meta.yaml`
- 参照スキル: `.claude/skills/case-study-writer/SKILL.md`
- 出力: `02_draft/first_draft.md`

## Step 4: コマンド修正（4ファイル）

### article-init.md

side_business の Phase 1 Step 4（カテゴリ別追加入力）に type 選択を追加:

```
記事タイプを選択してください:
1. case_study    (事例分析型 - テンプレートA/B/C) ← デフォルト
2. experience    (体験談 - 合成パターン法)
```

`case_study` 選択時のテンプレート選択:

```
テンプレートを選択してください:
1. B: ジャンル横断共通点分析
2. C: AI一人スタートアップ事例分析
3. A: ジャンル別事例分析
```

meta.yaml に `case_study` セクション追加:

```yaml
type: "case_study"
case_study:
  template_type: "B"
  template_label: "ジャンル横断共通点分析"
```

カテゴリ別デフォルト設定表の side_business 行を修正:

| カテゴリ | type | target_wordcount |
|----------|------|-----------------|
| side_business | case_study | 7000 |

### article-draft.md (L34-35)

```
├── side_business (type: case_study)
│   └── case-study-writer エージェント + case-study-writer スキル参照
├── side_business (type: experience)
│   └── experience-writer エージェント
```

### article-research.md (L35)

```
├── side_business (type: case_study)  → Web検索 + Reddit + RSS（事例収集+パターン抽出）
├── side_business (type: experience)  → experience-db-workflow Phase 1-2
```

### article-critique.md (L42-44)

```
├── side_business (type: case_study)
│   └── case-study-critique スキル（既存、4エージェント並列）
├── side_business (type: experience)
│   ├── quick: exp-critic-reality, exp-critic-balance
│   └── full:  + exp-critic-empathy, exp-critic-embed
```

## 対象外（今回のスコープ外）

- 事例分析型専用リサーチワークフローの作成（当面は汎用Web検索+Redditで代替）
- case-study-reviser エージェントの作成（当面はfinance-reviserまたは手動修正で代替）
- article-full.md の修正（article-draft/research/critique の変更に自動追従）

## 検証方法

1. **スキル読み込み確認**: `/article-init` で side_business + case_study を選択し、meta.yaml が正しく生成されるか
2. **分岐テスト**: `/article-draft` 実行時に case-study-writer エージェントに振り分けられるか
3. **批評連携テスト**: `/article-critique` 実行時に case-study-critique スキルが起動されるか
4. **E2E テスト**: テンプレートBで横断型パターン抽出記事を1本作成し、全工程が通るか

## 実装順序

```
Step 1: Neo4j 復旧
Step 2: .claude/skills/case-study-writer/SKILL.md 作成
Step 3: .claude/agents/case-study-writer.md 作成
Step 4: コマンド4ファイル修正（article-init → draft → research → critique）
Step 5: E2Eテスト（テンプレートBで1本作成）
```
