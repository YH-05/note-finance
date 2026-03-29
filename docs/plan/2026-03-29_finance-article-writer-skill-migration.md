# finance-article-writer: エージェント廃止 → スキルベース統合

## Context

現在、記事の初稿生成は `/article-draft` コマンドが **カテゴリ別にエージェントファイルを直接指定** して起動する構成になっている:

```
/article-draft → Agent(subagent_type="finance-article-writer")  ← .claude/agents/finance-article-writer.md
             → Agent(subagent_type="asset-management-writer") ← .claude/agents/asset-management-writer.md
```

問題: 執筆ルールが「エージェント定義 + スキル references/ + rules/ + resources/」の4箇所に分散しており、ルール変更時の保守性が低い。

**目標**: エージェント定義ファイルを廃止し、`.claude/skills/finance-article-writer/` がルール参照 + エージェントスポーンを一体で担う構成に統合する。

## 設計

### Before（現在）

```
/article-draft (command)
├── category判定
├── stock/macro/quant/edu → Agent(subagent_type="finance-article-writer")
│                            └── agents/finance-article-writer.md (system prompt)
│                                └── 「references/ を読め」という間接参照
└── asset_management     → Agent(subagent_type="asset-management-writer")
                           └── agents/asset-management-writer.md (system prompt)
                               └── 「references/ を読め」という間接参照
```

### After（提案）

```
/article-draft (command)
├── category判定
├── stock/macro/quant/edu/asset_management
│   └── Skill("finance-article-writer") を起動
│       └── SKILL.md がオーケストレーション:
│           1. meta.yaml を読み、category を確認
│           2. common-rules.md を読む
│           3. category別 references/ を読む
│           4. Agent(subagent_type="general-purpose") をスポーン
│              prompt に「読んだルール全文 + 入力データパス + 出力指示」を渡す
│           5. 出力確認（first_draft.md の存在・文字数チェック）
├── side_business → experience-writer (変更なし)
└── market_report → weekly-report-lead (変更なし)
```

### 核心: SKILL.md の役割変更

| | Before | After |
|---|---|---|
| SKILL.md | ナレッジベース（参照用） | **オーケストレーター**（ルール読込 + Agent スポーン + 品質チェック） |
| agents/*.md | system prompt（カテゴリ別2ファイル） | **廃止** → trash/ に移動 |
| references/ | エージェントが自分で読む（間接参照） | SKILL.md が読んでプロンプトに埋め込む |

### Agent スポーンのプロンプト設計

SKILL.md が構築するプロンプトの構造:

```markdown
あなたは金融記事のライターです。以下のルールに従って初稿を生成してください。

## 共通ルール
{common-rules.md の内容をここに展開}

## カテゴリ別ルール（{category}）
{category別 references/ の内容をここに展開}

## 入力データ
- meta.yaml: {article_dir}/meta.yaml
- decisions.json: {article_dir}/01_research/decisions.json
- sources.json: {article_dir}/01_research/sources.json

## 出力
- {article_dir}/02_draft/first_draft.md

## 追加出力（asset_management の場合のみ）
- {article_dir}/02_draft/curated_sources.json
```

**ポイント**: references/ の内容をプロンプトに**直接展開**するため、スポーンされた agent は references/ を自分で読む必要がない。これにより:
- agent のツール呼び出し回数が減る（Read × 2回分）
- ルールの適用漏れリスクが消える

## 変更対象ファイル

### 1. 変更: `.claude/skills/finance-article-writer/SKILL.md`

現在のナレッジベースからオーケストレーターに書き換え:

```markdown
---
name: finance-article-writer
description: (現状維持)
---

# finance-article-writer

## トリガー
/article-draft から呼び出されたとき、以下を実行する。

## オーケストレーションフロー

### Step 1: 入力確認
1. 引数から article_dir を受け取る
2. {article_dir}/meta.yaml を Read し category を取得
3. workflow.research = "done" を確認

### Step 2: ルール読込
4. references/common-rules.md を Read
5. category に応じた references/{category}.md を Read

### Step 3: Agent スポーン
6. Agent(subagent_type="general-purpose") をスポーン
   - prompt: Step 2 で読んだルール全文 + 入力パス + 出力指示を含む
   - mode: "bypassPermissions" (ファイル書き込みを許可)

### Step 4: 出力検証
7. first_draft.md の存在確認
8. 文字数チェック（カテゴリ別の目標範囲内か）
9. asset_management の場合: curated_sources.json の存在確認

### Step 5: meta.yaml 更新
10. workflow.draft = "done" に更新
```

### 2. 変更: `.claude/commands/article-draft.md`

Step 2 のカテゴリ別ルーティングを修正:

```diff
- ├── stock_analysis / macro_economy / quant_analysis / investment_education
- │   └── finance-article-writer エージェント
- ├── asset_management
- │   └── asset-management-writer エージェント
+ ├── stock_analysis / macro_economy / quant_analysis / investment_education / asset_management
+ │   └── Skill("finance-article-writer") を起動
+ │       引数: article_dir
```

side_business, market_report のルーティングは変更なし。

### 3. 廃止: エージェントファイル

```bash
# trash/ に移動（rm 禁止ルール遵守）
mv .claude/agents/finance-article-writer.md trash/
mv .claude/agents/asset-management-writer.md trash/
```

### 4. 影響確認: 他の参照箇所

| ファイル | 参照内容 | 対応 |
|---------|---------|------|
| `.claude/commands/article-full.md` | `/article-draft` を呼ぶだけ | **変更不要**（article-draft の内部変更で透過的に対応） |
| `.claude/commands/article-critique.md` | critic 系エージェントを使用（writer 無関係） | **変更不要** |
| `AGENTS.md` | エージェント一覧に記載あり | 記載を更新 |
| `CLAUDE.md` | エージェント数「60」の記述 | 数を更新 |

## 変更しないもの

- `references/` 配下の7ファイル（共通ルール + カテゴリ別6ファイル）→ そのまま
- critic 系エージェント（finance-critic-*.md）→ そのまま
- finance-reviser エージェント → そのまま
- `/article-critique`, `/article-revise`, `/article-publish` → そのまま
- `snippets/`, `template/`, `.claude/resources/critique-criteria/` → そのまま

## 検証方法

1. **ドライラン**: `/article-draft @articles/stock_analysis/2026-03-28_us-telecom-sector/` を実行し、first_draft.md が生成されることを確認
2. **カテゴリ網羅テスト**: stock_analysis, macro_economy, asset_management の各カテゴリで1本ずつ実行
3. **品質チェック**: 生成された記事が以下を満たすか確認
   - 免責事項（冒頭）とリスク開示（末尾）が挿入されている
   - 禁止表現がない
   - 文字数がカテゴリ別目標範囲内
   - 表が画像化されている（該当する場合）
4. **後続コマンドとの結合**: `/article-critique` が first_draft.md を正しく読めること
