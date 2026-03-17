# todo スキル実装プラン

## Context

日々のTODOリストを管理するスキルを新規作成する。朝の開始時に前日の未完了タスクを引き継ぎ、日中に更新し、終業時に振り返りを行う3モードのワークフロー型スキル。TODOファイルは `todo/` ディレクトリに日付ベースで保存しログとして保持する。

高レベルタスクはプロジェクトの実装状況（GitHub Issues/Projects、project.md、article meta.yaml、git ブランチ）を参照して具体的なサブタスクにドリルダウンする。

## 作成ファイル一覧

| ファイル | 説明 |
|---------|------|
| `.claude/skills/todo/SKILL.md` | スキル本体（ワークフロー定義） |
| `.claude/skills/todo/templates/todo-template.md` | TODOファイルテンプレート |
| `.claude/commands/todo.md` | スラッシュコマンド |

## 1. スラッシュコマンド: `.claude/commands/todo.md`

```yaml
---
description: 日次TODOリストの作成・更新・振り返りを管理します。
argument-hint: --start | --update | --end
---
```

- `--start`: 朝のルーティン（前日繰り越し＋プロジェクト状況からタスクドリルダウン＋今日のTODO作成）
- `--update`: 日中の更新（タスク追加・完了・メモ）
- `--end`: 終業振り返り（完了/未完了サマリー）
- 引数なし: AskUserQuestion でモード選択

## 2. テンプレート: `templates/todo-template.md`

```markdown
---
date: "{{date}}"
created_at: "{{created_at}}"
updated_at: "{{updated_at}}"
status: active
stats:
  total: 0
  completed: 0
  carried_over: 0
---

# TODO {{date}}

## Carried Over (前日からの繰り越し)

<!-- 前日の未完了タスク。--start 時に自動挿入 -->

## Today's Tasks (今日のタスク)

<!-- 高レベルタスクはサブタスクにドリルダウンして記載 -->
<!-- フォーマット例:
- [ ] 高レベルタスク
  - [ ] サブタスク1（Issue #123）
  - [ ] サブタスク2（article workflow: draft）
  - [x] 完了したサブタスク
-->

## Notes (メモ)

<!-- 自由記述：ブロッカー、気づき、参考情報など -->

## End of Day Summary (振り返り)

<!-- --end 時に自動生成 -->
```

**フロントマター仕様**:
- `status`: `active`（日中） / `closed`（`--end` 後）
- `stats`: タスク数を自動計算（サブタスクも含む）
- チェックボックス形式: `- [ ]`（未完了） / `- [x]`（完了）
- **階層構造**: インデント（2スペース）でサブタスク表現

## 3. SKILL.md 設計

### フロントマター

```yaml
---
name: todo
description: |
  日次TODOリストの作成・更新・振り返りを管理するワークフロースキル。
  /todo コマンドで使用。--start, --update, --end の3モード。
  プロジェクト実装状況に基づいてタスクをサブタスクにドリルダウンする。
  「TODO」「タスク管理」「今日のやること」「朝のルーティン」「振り返り」
  と言われたら必ずこのスキルを使うこと。
allowed-tools: Read, Write, Edit, Bash, Glob, Grep, AskUserQuestion
---
```

### ワークフロー概要

```
--start: 前日TODO読込 → 未完了抽出 → プロジェクト状況収集 → ドリルダウン → 今日のファイル作成 → 報告
--update: 今日のTODO読込 → 対話的に更新（ドリルダウン可） → frontmatter更新
--end:   今日のTODO読込 → 集計（サブタスク含む） → サマリー生成 → status:closed
```

### Mode: `--start`（朝のルーティン）

#### Step 1: 初期化
1. 今日の日付を取得（`YYYY-MM-DD`）
2. `todo/` ディレクトリ存在チェック（なければ `mkdir -p todo/`）
3. 今日のファイル `todo/TODO_YYYY-MM-DD.md` が既存か確認
   - 既存 → AskUserQuestion で `--update` に切替 or 上書き選択

#### Step 2: 前日繰り越し
4. 前日ファイルを検索: `Glob` で `todo/TODO_*.md` → 最新（今日より前）を取得
   - 見つからない場合 → 初回利用として繰り越しなし
5. 前日ファイルから未完了行を抽出（`- [ ]` にマッチ、サブタスクも含む）

#### Step 3: プロジェクト状況の収集
6. 以下の情報源からアクティブなタスクを収集:

   **a. GitHub Issues/Projects（Bash: `gh` CLI）**
   ```bash
   # In Progress の Issue を取得
   gh issue list --state open --label "in-progress" --json number,title,labels
   # アサインされた Issue
   gh issue list --state open --assignee @me --json number,title,labels,milestone
   ```

   **b. project.md（Read + Glob）**
   - `Glob`: `docs/project/*/project.md` で全プロジェクトファイルを検索
   - 各 project.md から Wave 構造と未完了 Issue を抽出
   - 依存関係を解析し、着手可能なタスクを特定

   **c. article meta.yaml（Glob + Read）**
   - `Glob`: `articles/*/meta.yaml` で進行中の記事を検索
   - `workflow` フィールドから次に必要なフェーズを特定
     - 例: `research: done, draft: pending` → 「初稿作成が必要」

   **d. git ブランチ（Bash）**
   ```bash
   git branch --list 'feature/*' 'fix/*' 'refactor/*'
   ```
   - アクティブなブランチから進行中の作業を推定

#### Step 4: タスクのドリルダウン
7. 収集した情報をもとに、ユーザーに今日のタスク候補を提示:

   ```
   プロジェクト状況から以下のタスクを検出しました:

   [GitHub Issues]
   - #131 save-to-article-graph E2Eテスト（Wave C, depends on #128）
   - #132 パフォーマンステスト（Wave D, depends on #131）

   [記事ワークフロー]
   - articles/macro_economy/2026-03-15_fed-rate/ → 次フェーズ: draft

   [ブランチ]
   - refactor/article-workflow-unification → 進行中

   今日取り組むタスクを選択してください（番号 or 自由入力）:
   ```

8. ユーザーが選択したタスクをサブタスクにドリルダウン:

   **Issue ベースのドリルダウン例**:
   ```markdown
   - [ ] #131 save-to-article-graph E2Eテスト
     - [ ] テストフィクスチャ作成
     - [ ] wealth-scrape マッパーのテスト
     - [ ] topic-discovery マッパーのテスト
     - [ ] CI に統合
   ```

   **記事ワークフローのドリルダウン例**:
   ```markdown
   - [ ] FRB金利分析記事の初稿作成
     - [ ] /article-draft 実行
     - [ ] 初稿レビュー（HF5）
     - [ ] 批評・修正（/article-critique）
   ```

   ドリルダウンの情報源:
   - **Issue**: Issue 本文の受け入れ条件（チェックリスト）、project.md の詳細
   - **記事**: meta.yaml の workflow 状態、カテゴリ別の標準フェーズ
   - **自由入力**: ユーザーの説明をもとに 3-5 個のサブタスクを提案

#### Step 5: ファイル作成
9. テンプレートに日付・繰り越し・ドリルダウン済みタスクを埋め込んで `Write`
10. 報告: 繰り越し件数、新規タスク件数、ファイルパス

### Mode: `--update`（日中の更新）

#### Step 1: ファイル読込
1. 今日のファイルを `Read`（なければ `--start` を案内）
2. 現在のタスク一覧を階層構造で表示

#### Step 2: 対話的更新
3. AskUserQuestion で操作選択:

   **a. タスク追加**
   - 高レベルタスクの場合 → プロジェクト状況を参照してドリルダウン提案
   - 単純タスクの場合 → そのまま `- [ ]` として追加
   - `Edit` で "Today's Tasks" セクションに挿入

   **b. タスク完了**
   - 番号指定で `- [ ]` → `- [x]` に変更
   - サブタスク全完了時、親タスクも自動完了を提案

   **c. サブタスク追加**
   - 既存タスクにサブタスクを追加（インデント付き `- [ ]`）

   **d. メモ追加**
   - `Edit` で "Notes" セクションに追記

   **e. 完了** → ループ終了

#### Step 3: メタデータ更新
4. `updated_at` と `stats`（total/completed をサブタスク含めて再計算）を更新

### Mode: `--end`（終業振り返り）

#### Step 1: 集計
1. 今日のファイルを `Read`（なければエラー）
2. 全タスク（親＋サブ）を集計:
   - 完了: `- [x]` の行数
   - 未完了: `- [ ]` の行数
   - 完了率: completed / total

#### Step 2: 振り返り
3. AskUserQuestion で明日への申し送り（任意）
4. "End of Day Summary" セクションに `Edit` で書込:

   ```markdown
   ## End of Day Summary (振り返り)

   ### 達成状況
   - 完了: 8/12 タスク (66.7%)
   - 親タスク: 2/3 完了
   - サブタスク: 6/9 完了

   ### 未完了タスク（明日に繰り越し）
   - [ ] #132 パフォーマンステスト
     - [ ] ベンチマークスクリプト作成
     - [ ] CI 閾値設定

   ### 明日への申し送り
   - #131 のレビュー待ち → マージ後に #132 着手可能
   ```

#### Step 3: ステータス更新
5. フロントマター更新: `status: closed`, `stats` 最終値, `updated_at`
6. 報告: 完了率、未完了件数、明日の見通し

## 4. ドリルダウンのロジック詳細

### 情報源と優先度

| 優先度 | 情報源 | 取得方法 | ドリルダウン内容 |
|--------|--------|----------|----------------|
| 1 | GitHub Issues (open, assigned) | `gh issue list` | Issue 本文のチェックリスト、受け入れ条件 |
| 2 | project.md (Wave 構造) | `Glob` + `Read` | 依存関係解決済みの着手可能タスク |
| 3 | article meta.yaml | `Glob` + `Read` | 次フェーズの具体的ステップ |
| 4 | git ブランチ | `git branch` | ブランチ名から推定される作業内容 |
| 5 | ユーザー自由入力 | AskUserQuestion | 説明に基づく 3-5 サブタスク提案 |

### Issue ドリルダウンの手順

1. `gh issue view {number} --json body,title,labels` で Issue 詳細を取得
2. Issue 本文から `- [ ]` チェックリストを抽出
3. チェックリストがなければ、Issue の「受け入れ条件」や「詳細」セクションからサブタスクを生成
4. project.md に依存情報があれば、ブロッカーを Notes に記載

### 記事ドリルダウンの手順

1. `meta.yaml` の `workflow` から次の `pending` フェーズを特定
2. カテゴリ別の標準ワークフロー（`article-full.md` 参照）からステップを生成:
   - research → `リサーチソース収集`, `主張抽出`, `HF3確認`
   - draft → `/article-draft 実行`, `初稿レビュー(HF5)`
   - critique → `批評実行`, `修正版生成`, `最終確認(HF6)`
   - publish → `/article-publish 実行`, `note.com確認`

### 自由入力ドリルダウンの手順

1. ユーザーの入力テキストを解析
2. 関連する GitHub Issue やファイルを `Grep` で検索
3. 見つかれば具体的なサブタスクを提案、見つからなければ一般的な分解（調査 → 実装 → テスト → レビュー）

## 5. エッジケース対応

| ケース | 対応 |
|--------|------|
| `todo/` ディレクトリ未存在 | 自動作成 `mkdir -p todo/` |
| 前日ファイルなし（初回利用） | 繰り越しなしで新規作成 |
| 今日のファイルが既存（`--start`） | ユーザーに確認（update切替 or 上書き） |
| 今日のファイル未存在（`--update`/`--end`） | `--start` 実行を案内 |
| 引数なし | AskUserQuestion でモード選択 |
| 休日明け（数日ギャップ） | 直近のTODOファイルから繰り越し |
| `gh` CLI 未認証 / GitHub アクセス不可 | GitHub 情報源をスキップ、ローカル情報のみで動作 |
| project.md が存在しない | Wave ドリルダウンをスキップ |
| 進行中の記事がない | 記事ドリルダウンをスキップ |
| サブタスク全完了 → 親タスク | 親タスクの自動完了をユーザーに提案 |

## 6. 検証方法

1. `/todo --start` → `todo/TODO_2026-03-17.md` が正しいテンプレートで作成されること
2. `/todo --start` → GitHub Issues、project.md、meta.yaml からタスク候補が提示されること
3. `/todo --start` → 選択したタスクがサブタスクにドリルダウンされて記載されること
4. `/todo --update` → タスク追加時にドリルダウン提案が動作すること
5. `/todo --update` → サブタスク完了時に親タスクの自動完了提案が動作すること
6. `/todo --end` → 親タスク・サブタスクの両方が集計されること
7. 翌日 `/todo --start` → 前日の未完了タスク（階層構造含む）が繰り越されること
8. GitHub アクセス不可時 → エラーなくローカル情報のみで動作すること

## 7. 実装順序

1. テンプレート作成 (`.claude/skills/todo/templates/todo-template.md`)
2. SKILL.md 作成（3モード＋ドリルダウンロジック）
3. コマンドファイル作成 (`.claude/commands/todo.md`)
4. 手動テスト（`--start` → `--update` → `--end` の順に実行）
5. CLAUDE.md のコマンド表に `/todo` を追記
