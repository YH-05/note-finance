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

# todo スキル

日次TODOリストを `todo/TODO_YYYY-MM-DD.md` として管理する。

- テンプレート: `.claude/skills/todo/templates/todo-template.md`
- 保存先: `todo/` ディレクトリ（日付ベースのログとして保持）

## モード判定

引数から実行モードを決定する:

| 引数 | モード |
|------|--------|
| `--start` | 朝のルーティン |
| `--update` | 日中の更新 |
| `--end` | 終業振り返り |
| 引数なし | AskUserQuestion でモード選択 |

引数なしの場合:
```
AskUserQuestion: どのモードで実行しますか？
1. --start（朝のルーティン：前日繰り越し＋タスクドリルダウン）
2. --update（日中の更新：タスク追加・完了・メモ）
3. --end（終業振り返り：完了/未完了サマリー）
```

---

## Mode: --start（朝のルーティン）

### Step 1: 初期化

1. 今日の日付を取得（`YYYY-MM-DD` 形式）
2. `todo/` ディレクトリ存在チェック → なければ `mkdir -p todo/`
3. `todo/TODO_YYYY-MM-DD.md` が既存か確認
   - 既存の場合 → AskUserQuestion:「今日のTODOは既に存在します。`--update` に切り替えますか？それとも上書きしますか？」

### Step 2: 前日繰り越し

4. `Glob` で `todo/TODO_*.md` を検索 → 今日より前の最新ファイルを特定
   - 見つからない場合 → 繰り越しなし（初回利用）
5. 前日ファイルを `Read` し、未完了タスク行（`- [ ]`）を抽出
   - サブタスクの階層構造（インデント）を維持して抽出
   - `- [x]` 完了済みは除外

### Step 3: プロジェクト状況の収集

以下の情報源からアクティブなタスクを収集する。各情報源でエラーが発生した場合はスキップして次へ進む。

**a. GitHub Issues（`gh` CLI）**
```bash
# アサインされた Open Issue
gh issue list --state open --assignee @me --json number,title,labels,milestone --limit 20
# In Progress ラベルの Issue
gh issue list --state open --label "in-progress" --json number,title,labels --limit 20
```
- `gh` CLI 未認証 / GitHub アクセス不可 → この情報源をスキップ

**b. project.md（ローカルファイル）**
```
Glob: docs/project/*/project.md
```
- 各 project.md から Wave 構造と未完了 Issue を抽出
- 依存関係を解析し、着手可能なタスクを特定
- project.md が存在しない → スキップ

**c. article meta.yaml（記事ワークフロー）**
```
Glob: articles/*/meta.yaml
Glob: articles/*/*/meta.yaml
```
- `workflow` フィールドから次の `pending` フェーズを特定
  - 例: `research: done, draft: pending` → 「初稿作成が必要」
- 進行中の記事がない → スキップ

**d. git ブランチ（ローカル）**
```bash
git branch --list 'feature/*' 'fix/*' 'refactor/*'
```
- アクティブなブランチから進行中の作業を推定

### Step 4: タスクのドリルダウン

6. 収集した情報をユーザーに提示:

```
プロジェクト状況から以下のタスクを検出しました:

[GitHub Issues]
- #131 save-to-article-graph E2Eテスト（Wave C）
- #132 パフォーマンステスト（Wave D, depends on #131）

[記事ワークフロー]
- articles/macro_economy/2026-03-15_fed-rate/ → 次フェーズ: draft

[ブランチ]
- refactor/article-workflow-unification → 進行中

今日取り組むタスクを選択してください（番号、自由入力、または「完了」で終了）:
```

7. ユーザーが選択したタスクをサブタスクにドリルダウン:

**Issue ベース**: `gh issue view {number} --json body,title,labels` で詳細取得 → 本文のチェックリストや受け入れ条件からサブタスク生成
```markdown
- [ ] #131 save-to-article-graph E2Eテスト
  - [ ] テストフィクスチャ作成
  - [ ] wealth-scrape マッパーのテスト
  - [ ] topic-discovery マッパーのテスト
  - [ ] CI に統合
```

**記事ワークフロー**: meta.yaml の workflow 状態からステップ生成
```markdown
- [ ] FRB金利分析記事の初稿作成
  - [ ] /article-draft 実行
  - [ ] 初稿レビュー
  - [ ] 批評・修正（/article-critique）
```

**自由入力**: ユーザーの説明をもとに 3-5 個のサブタスクを提案。関連する Issue やファイルを `Grep` で検索し、見つかれば具体的に、見つからなければ一般的な分解（調査 → 実装 → テスト → レビュー）

8. AskUserQuestion でタスク追加を繰り返し、「完了」で Step 5 へ

### Step 5: ファイル作成

9. テンプレート（`.claude/skills/todo/templates/todo-template.md`）を `Read` し、以下を埋め込み:
   - `{{date}}`: 今日の日付
   - `{{created_at}}`, `{{updated_at}}`: 現在のISO 8601タイムスタンプ
   - `Carried Over` セクション: 前日の未完了タスク（階層構造維持）
   - `Today's Tasks` セクション: ドリルダウン済みの新規タスク
   - `stats`: total / completed / carried_over を計算

10. `Write` で `todo/TODO_YYYY-MM-DD.md` を作成

11. 報告:
```
✅ 今日のTODO作成完了: todo/TODO_YYYY-MM-DD.md
- 繰り越し: X件
- 新規タスク: Y件（サブタスク含む計Z件）
```

---

## Mode: --update（日中の更新）

### Step 1: ファイル読込

1. 今日の `todo/TODO_YYYY-MM-DD.md` を `Read`
   - 存在しない場合 →「今日のTODOがまだありません。`/todo --start` で作成してください。」と案内して終了
2. 現在のタスク一覧を階層構造で表示

### Step 2: 対話的更新

3. AskUserQuestion で操作をループ:

```
操作を選択してください:
a. タスク追加
b. タスク完了（番号指定）
c. サブタスク追加（親タスク番号指定）
d. メモ追加
e. 完了（更新終了）
```

**a. タスク追加**
- 高レベルタスクの場合 → プロジェクト状況（GitHub Issues 等）を参照してドリルダウン提案
- 単純タスクの場合 → そのまま `- [ ]` として追加
- `Edit` で "Today's Tasks" セクション末尾に挿入

**b. タスク完了**
- ユーザーが指定したタスクの `- [ ]` → `- [x]` に `Edit` で変更
- サブタスク全完了時 → 親タスクの自動完了を提案:
  「親タスク "XXX" のサブタスクが全て完了しました。親タスクも完了にしますか？」

**c. サブタスク追加**
- 既存タスク配下にインデント付き `- [ ]` を `Edit` で追加

**d. メモ追加**
- `Edit` で "Notes" セクションに追記

**e. 完了** → ループ終了

### Step 3: メタデータ更新

4. フロントマターを `Edit` で更新:
   - `updated_at`: 現在のタイムスタンプ
   - `stats.total`: 全チェックボックス（`- [ ]` + `- [x]`）の行数
   - `stats.completed`: `- [x]` の行数

---

## Mode: --end（終業振り返り）

### Step 1: 集計

1. 今日の `todo/TODO_YYYY-MM-DD.md` を `Read`
   - 存在しない場合 → エラー:「今日のTODOがありません。」
2. 全タスク（親＋サブ）を集計:
   - 完了数: `- [x]` の行数
   - 未完了数: `- [ ]` の行数
   - 完了率: completed / total

### Step 2: 振り返り

3. AskUserQuestion:「明日への申し送りはありますか？（任意、Enter でスキップ）」
4. "End of Day Summary" セクションに `Edit` で書込:

```markdown
## End of Day Summary (振り返り)

### 達成状況
- 完了: X/Y タスク (Z%)
- 親タスク: A/B 完了
- サブタスク: C/D 完了

### 未完了タスク（明日に繰り越し）
- [ ] 未完了タスク1
  - [ ] 未完了サブタスク

### 明日への申し送り
- （ユーザー入力）
```

### Step 3: ステータス更新

5. フロントマターを `Edit` で更新:
   - `status`: `closed`
   - `stats`: 最終集計値
   - `updated_at`: 現在のタイムスタンプ

6. 報告:
```
📊 本日の振り返り完了
- 完了率: X/Y (Z%)
- 未完了: W件（明日に繰り越し）
- ファイル: todo/TODO_YYYY-MM-DD.md
```

---

## エッジケース対応

| ケース | 対応 |
|--------|------|
| `todo/` ディレクトリ未存在 | `mkdir -p todo/` で自動作成 |
| 前日ファイルなし（初回利用） | 繰り越しなしで新規作成 |
| 今日のファイルが既存（`--start`） | AskUserQuestion で update 切替 or 上書き選択 |
| 今日のファイル未存在（`--update`/`--end`） | `--start` 実行を案内 |
| 引数なし | AskUserQuestion でモード選択 |
| 休日明け（数日ギャップ） | Glob で最新のTODOファイルから繰り越し |
| `gh` CLI 未認証 / GitHub アクセス不可 | GitHub 情報源をスキップ、ローカル情報のみで動作 |
| project.md が存在しない | Wave ドリルダウンをスキップ |
| 進行中の記事がない | 記事ドリルダウンをスキップ |
| サブタスク全完了 → 親タスク | 親タスクの自動完了をユーザーに提案 |

## stats 計算ルール

- `total`: `- [ ]` と `- [x]` の合計行数（親・サブ全て含む）
- `completed`: `- [x]` の行数
- `carried_over`: Carried Over セクション内のタスク行数（`--start` 時のみ設定）
- 親タスクとサブタスクを区別する場合: インデントなし = 親、インデントあり = サブ
