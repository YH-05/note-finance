---
name: reddit-finance-topics
description: |
  Reddit金融コミュニティ（r/investing, r/stocks, r/wallstreetbets等）からトピック・議論・センチメントを収集し、
  投資視点でグループ別に整理するオーケストレータースキル。
  3フェーズ構成（収集→深掘り→記事化ブリッジ）を管理し、Reddit MCP 呼び出し・サブエージェント起動・ユーザーとのインタラクションを担う。
allowed-tools: Read, Write, Bash, Task, ToolSearch, AskUserQuestion, Skill, WebSearch
---

# Reddit金融トピック収集ワークフロー

Reddit金融コミュニティから注目トピックを自動収集し、グループ別に整理して note.com 記事化を支援するオーケストレータースキル。

## アーキテクチャ

```
/reddit-finance-topics (このスキル = オーケストレーター)
  │
  ├── Phase 1: トピック収集（3〜5分）
  │     ├── AskUserQuestion でグループ選択
  │     ├── ToolSearch('reddit') で Reddit MCP をロード
  │     ├── 各 subreddit から hot/top 投稿を取得
  │     ├── フィルタリング（スコア・コメント数・フレア）
  │     ├── 重複除去
  │     └── .tmp/reddit-topics/{timestamp}.json に保存 → テーブル表示
  │
  ├── Phase 2: 深掘り分析（--deep 指定時のみ、5〜10分）
  │     └── reddit-topic-analyzer を**逐次** Task() 呼び出し（カテゴリ別）
  │
  └── Phase 3: 記事化ブリッジ（インタラクティブ）
        ├── AskUserQuestion でトピック番号選択（0: スキップ 含む）
        └── 選択時: Skill: finance-full --category {category} を自動起動
```

## 使用方法

```bash
# 標準実行（デフォルト: 過去7日間、全グループ、各最新10件）
/reddit-finance-topics

# 特定グループのみ
/reddit-finance-topics --days 3 --groups "general_investing,macro_economics" --top-n 5

# 深掘り収集（コメント詳細・関連スレッドを含む）
/reddit-finance-topics --deep --groups "general_investing,trading"

# 過去1日間の速報確認
/reddit-finance-topics --days 1 --top-n 20
```

## パラメータ

| パラメータ | デフォルト | 説明 |
|-----------|-----------|------|
| `--days` | 7 | 過去何日分の投稿を対象とするか |
| `--top-n` | 10 | 各グループの最大取得件数（スコア降順） |
| `--groups` | all | 対象グループ（カンマ区切り / all）。グループキーは `data/config/reddit-subreddits.json` 参照 |
| `--deep` | false | 深掘りモード。reddit-topic-analyzer を逐次呼び出し |

---

## Phase 1: トピック収集

### ステップ 1.1: パラメータ解析

入力からパラメータを解析してデフォルト値を設定する:

```python
days = 7
top_n = 10
groups = "all"  # またはカンマ区切りのグループキー
deep = False    # --deep フラグが指定された場合 True

# --groups のカンマ区切りリスト → 配列変換
# 入力例: "general_investing,macro_economics"
# 処理: groups_list = [g.strip() for g in groups.split(",") if g.strip()]
# 結果: ["general_investing", "macro_economics"]
# "all" の場合: data/config/reddit-subreddits.json の groups キーを全展開
```

### ステップ 1.2: 設定ファイルの読み込み

`data/config/reddit-subreddits.json` を Read で読み込み、対象グループ・subreddit・フィルタ設定を取得する。

グループキー一覧（`data/config/reddit-subreddits.json` の `groups` オブジェクト）:

| グループキー | グループ名（日本語） | subreddit 例 |
|-------------|---------------------|-------------|
| `general_investing` | 投資全般 | r/investing, r/stocks, r/ValueInvesting |
| `trading` | トレーディング | r/wallstreetbets, r/options, r/Daytrading |
| `macro_economics` | マクロ経済 | r/Economics, r/econmonitor |
| `deep_analysis` | 詳細分析 | r/SecurityAnalysis, r/quant |
| `sector_specific` | セクター特化 | r/technology, r/artificialintelligence |

### ステップ 1.3: AskUserQuestion でグループ選択

```
AskUserQuestion:
  質問: 以下のグループから対象を選択してください。

  利用可能なグループ:
  1. general_investing（投資全般）: r/investing, r/stocks, r/ValueInvesting
  2. trading（トレーディング）: r/wallstreetbets, r/options, r/Daytrading
  3. macro_economics（マクロ経済）: r/Economics, r/econmonitor
  4. deep_analysis（詳細分析）: r/SecurityAnalysis, r/quant
  5. sector_specific（セクター特化）: r/technology, r/artificialintelligence
  0. 全グループ（all）

  番号を入力（カンマ区切りで複数選択可）: 例: "1,3" または "0"（--groups 引数で指定済みの場合はスキップ）
```

**注意**: `--groups` オプションが引数で指定されている場合、このステップはスキップして指定グループを使用する。

### ステップ 1.4: ToolSearch で Reddit MCP をロード

**必須**: Reddit MCP ツールを使用するため、ToolSearch を呼び出す。

```
ToolSearch('reddit')
```

**失敗した場合（Reddit MCP 未設定エラー）**:

```
エラー [E001]: Reddit MCP が設定されていません

Reddit MCPを使用するには、.mcp.json に以下の設定が必要です:

{
  "mcpServers": {
    "reddit": {
      "command": "uvx",
      "args": ["mcp-reddit"],
      "env": {
        "REDDIT_CLIENT_ID": "your_client_id",
        "REDDIT_CLIENT_SECRET": "your_client_secret",
        "REDDIT_USERNAME": "your_username",
        "REDDIT_PASSWORD": "your_password"
      }
    }
  }
}

設定方法:
1. https://www.reddit.com/prefs/apps でアプリを作成
2. Client ID・Secret を取得
3. .mcp.json に上記設定を追記
4. Claude Code を再起動

処理を中断します。
```

### ステップ 1.5: subreddit ごとに投稿を取得

選択したグループに含まれる各 subreddit から投稿を取得する:

```
各 subreddit に対して:
  1. mcp__reddit__get_subreddit_hot_posts を呼び出し
     - subreddit: "investing" など（r/ プレフィックスなし）
     - limit: top_n * 2（フィルタリング後に top_n 件を確保するため）
  2. mcp__reddit__get_subreddit_top_posts を呼び出し（time_filter: "week"）
     - フィルタ設定の time_filter を使用

  失敗時:
    - 当該 subreddit をスキップして継続
    - fetch_errors に記録: {"subreddit": name, "error": message}
```

**重要**: `get_subreddit_info` は API 制限により失敗する場合があるため、使用しない。

### ステップ 1.6: フィルタリング・重複除去

取得した投稿に対してフィルタリングを適用する:

```python
filters = config["filters"]  # data/config/reddit-subreddits.json から取得
min_score = filters["min_score"]         # デフォルト: 50
min_comments = filters["min_comments"]  # デフォルト: 10
exclude_flairs = filters["exclude_flairs"]  # ["Meme", "Shitpost", "Satire", "Not News"]
time_limit = datetime.now() - timedelta(days=days)  # days パラメータで計算

filtered_posts = []
seen_ids = set()

for post in all_posts:
    # 重複除去
    if post["post_id"] in seen_ids:
        continue

    # スコアフィルタ
    if post["score"] < min_score:
        continue

    # コメント数フィルタ
    if post["num_comments"] < min_comments:
        continue

    # フレアフィルタ
    if post.get("flair") in exclude_flairs:
        continue

    # 日時フィルタ（days パラメータ）
    if post["created_at"] < time_limit.isoformat():
        continue

    seen_ids.add(post["post_id"])
    filtered_posts.append(post)

# グループ別にスコア降順でソートし top_n 件に絞る
for group_key, posts in group_posts.items():
    group_posts[group_key] = sorted(posts, key=lambda p: p["score"], reverse=True)[:top_n]
```

### ステップ 1.7: .tmp/reddit-topics/{timestamp}.json に保存

```python
import json
from datetime import datetime
from pathlib import Path

timestamp = datetime.now().strftime("%Y-%m-%dT%H-%M-%S")
session_id = f"reddit-collection-{timestamp}"
output_dir = Path(".tmp/reddit-topics")
output_dir.mkdir(parents=True, exist_ok=True)
output_file = output_dir / f"{timestamp}.json"

# トピック ID を付与（T001, T002...）
topic_counter = 1
for group_key, posts in group_posts.items():
    for post in posts:
        post["topic_id"] = f"T{topic_counter:03d}"
        topic_counter += 1

session_data = {
    "session_id": session_id,
    "timestamp": datetime.now().isoformat(),
    "parameters": {
        "days": days,
        "top_n": top_n,
        "groups": selected_groups,
        "deep": deep
    },
    "groups": {
        group_key: {
            "group_name": config["groups"][group_key]["name"],
            "group_name_ja": config["groups"][group_key]["name_ja"],
            "topics": posts,
            "config": {
                "min_score": filters["min_score"],
                "min_comments": filters["min_comments"],
                "time_filter": filters["time_filter"]
            }
        }
        for group_key, posts in group_posts.items()
    },
    "stats": {
        "total_topics": topic_counter - 1,
        "groups_processed": len(group_posts),
        "fetch_errors": fetch_errors
    }
}

with open(output_file, "w", encoding="utf-8") as f:
    json.dump(session_data, f, ensure_ascii=False, indent=2)
```

**フィルタ後0件の場合**:

```
警告 [W001]: フィルタリング後、対象トピックが0件です

グループ: {group_name}
フィルタ条件:
  - 最小スコア: {min_score}
  - 最小コメント数: {min_comments}
  - 期間: 過去{days}日間

対処法:
  - --days を増やしてください（例: --days 14）
  - --top-n を増やしてください（例: --top-n 20）
  - スコアフィルタを下げることを検討してください
```

### ステップ 1.8: テーブル表示

収集結果をユーザーに分かりやすく表示する:

```
## Reddit 金融トピック収集結果

収集日時: 2026-02-23 12:00:00
対象グループ: 3グループ | 対象期間: 過去7日間 | 取得件数上限: 10件/グループ

---

### 投資全般（general_investing）: 8件

| No | トピックID | タイトル | subreddit | スコア | コメント |
|----|-----------|--------|-----------|-------|---------|
| 1 | T001 | Why I moved from growth to value... | r/investing | 2,341 | 234 |
| 2 | T002 | S&P 500 at all-time high - thoughts? | r/stocks | 1,892 | 189 |
...

### マクロ経済（macro_economics）: 5件

| No | トピックID | タイトル | subreddit | スコア | コメント |
|----|-----------|--------|-----------|-------|---------|
| 9 | T009 | Fed holds rates - what it means... | r/Economics | 3,102 | 412 |
...

---

合計: 13件 | セッション: reddit-collection-2026-02-23T12-00-00
保存先: .tmp/reddit-topics/2026-02-23T12-00-00.json
```

---

## Phase 2: 深掘り分析（--deep 指定時のみ）

`--deep` フラグが指定された場合のみ実行する。指定がない場合は Phase 3 に進む。

### ステップ 2.1: グループ別に reddit-topic-analyzer を逐次呼び出し

**重要**: 各カテゴリを**逐次**処理すること。並列呼び出しは Reddit API レート制限を超える可能性があるため禁止。

```python
analyzed_groups = []
timestamp = session_data["session_id"].replace("reddit-collection-", "")

for group_key, group_data in session_data["groups"].items():
    if not group_data["topics"]:
        continue  # トピックが0件のグループはスキップ

    # カテゴリ別入力ファイルを作成
    category_input = {
        "session_id": session_data["session_id"],
        "timestamp": session_data["timestamp"],
        "category": group_key,
        "category_name_ja": group_data["group_name_ja"],
        "topics": group_data["topics"],
        "config": group_data["config"]
    }
    category_file = f".tmp/reddit-topics/{timestamp}-{group_key}.json"
    with open(category_file, "w", encoding="utf-8") as f:
        json.dump(category_input, f, ensure_ascii=False, indent=2)

    # reddit-topic-analyzer を逐次呼び出し（並列禁止）
    # 出力先: analyzed-{timestamp}-{group_key}.json（カテゴリ別独立ファイル）
    result = Task(
        subagent_type="reddit-topic-analyzer",
        description=f"{group_key}: {len(group_data['topics'])}件の深掘り分析",
        prompt=f"""以下のカテゴリのトピックを深掘り分析してください。

入力ファイル: {category_file}

上記ファイルを Read で読み込み、処理を実行してください。
結果は .tmp/reddit-topics/analyzed-{timestamp}-{group_key}.json に新規書き込みしてください。
"""
    )
    analyzed_groups.append(group_key)
    logger.info("Category analysis completed", group_key=group_key)
```

### ステップ 2.2: 深掘り結果の集約表示

全グループの処理完了後、カテゴリ別ファイルを集約して高優先度の記事化提案を一覧表示する:

```python
# 全カテゴリの結果を集約
all_proposals = []
for group_key in analyzed_groups:
    analyzed_file = f".tmp/reddit-topics/analyzed-{timestamp}-{group_key}.json"
    if Path(analyzed_file).exists():
        with open(analyzed_file, encoding="utf-8") as f:
            data = json.load(f)
        for topic in data.get("analyzed_topics", []):
            proposal = topic.get("article_proposal", {})
            if proposal:
                all_proposals.append({
                    "topic_id": topic["topic_id"],
                    "title": topic["title"],
                    "subreddit": topic["subreddit"],
                    "group_key": group_key,
                    **proposal
                })

# 優先度順に並び替え（high → medium → low）
priority_order = {"high": 0, "medium": 1, "low": 2}
all_proposals.sort(key=lambda p: priority_order.get(p.get("priority", "low"), 2))
```

```
## 深掘り分析完了

分析グループ: {len(analyzed_groups)}グループ

### 高優先度 記事化提案

| No | トピックID | 記事タイトル案 | subreddit | 優先度 | 推定文字数 |
|----|-----------|-------------|-----------|--------|----------|
| 1 | T001 | 米国個人投資家が注目するバリュー株回帰 | r/investing | high | medium |
...

分析詳細（カテゴリ別）:
  - .tmp/reddit-topics/analyzed-{timestamp}-general_investing.json
  - .tmp/reddit-topics/analyzed-{timestamp}-trading.json
  ...
```

---

## Phase 3: 記事化ブリッジ

### ステップ 3.1: AskUserQuestion でトピック選択

```
AskUserQuestion:
  質問: 記事化するトピックを選択してください。

  [収集・分析したトピック一覧を番号付きで表示]
  例:
    1. T001: Why I moved from growth to value... (r/investing, スコア: 2,341)
    2. T009: Fed holds rates - what it means... (r/Economics, スコア: 3,102)
    ...
    0. スキップ（記事化しない）

  番号を入力（1つのみ）:
```

**0 を選択した場合**: 記事化をスキップしてワークフロー完了。

### ステップ 3.2: finance-full スキルを自動起動

選択したトピックの情報から `--category` パラメータを生成し、`finance-full` スキルを起動する。

`data/config/reddit-subreddits.json` の `category_mapping` フィールドを使用してカテゴリを決定する:

```python
# category_mapping の例:
# {
#   "general_investing": "market_report",
#   "trading": "stock_analysis",
#   "macro_economics": "economic_indicators",
#   "deep_analysis": "quant_analysis",
#   "sector_specific": "market_report"
# }

selected_topic = topics[selected_number - 1]
group_key = selected_topic["group_key"]  # トピックが属するグループ
category_mapping = config["category_mapping"]
article_category = category_mapping.get(group_key, "market_report")
```

```
Skill: finance-full
Input: --category {article_category}

記事のテーマ参考情報:
- トピック: {selected_topic["title"]}
- Reddit URL: {selected_topic["url"]}
- コミュニティ: r/{selected_topic["subreddit"]}
- スコア: {selected_topic["score"]} | コメント: {selected_topic["num_comments"]}
```

**`--category` パラメータ**: `finance-full` スキルに渡すカテゴリ。`category_mapping` から決定した値（例: `market_report`, `stock_analysis`, `economic_indicators`, `quant_analysis`）。

---

## .tmp ファイル形式

### Phase 1 出力: .tmp/reddit-topics/{timestamp}.json

```json
{
  "session_id": "reddit-collection-2026-02-23T12-00-00",
  "timestamp": "2026-02-23T12:00:00+09:00",
  "parameters": {
    "days": 7,
    "top_n": 10,
    "groups": ["general_investing", "macro_economics"],
    "deep": false
  },
  "groups": {
    "general_investing": {
      "group_name": "General Investing",
      "group_name_ja": "投資全般",
      "topics": [
        {
          "topic_id": "T001",
          "post_id": "abc123",
          "title": "Why I moved from growth to value investing",
          "url": "https://reddit.com/r/investing/comments/abc123",
          "subreddit": "investing",
          "score": 2341,
          "num_comments": 234,
          "created_at": "2026-02-22T10:30:00Z",
          "flair": "Discussion",
          "group_key": "general_investing"
        }
      ],
      "config": {
        "min_score": 50,
        "min_comments": 10,
        "time_filter": "week"
      }
    }
  },
  "stats": {
    "total_topics": 13,
    "groups_processed": 2,
    "fetch_errors": []
  }
}
```

### Phase 2 中間ファイル（入力）: .tmp/reddit-topics/{timestamp}-{group_key}.json

reddit-topic-analyzer への入力ファイル（`reddit-topic-analyzer.md` 仕様に準拠）:

```json
{
  "session_id": "reddit-collection-2026-02-23T12-00-00",
  "timestamp": "2026-02-23T12:00:00+09:00",
  "category": "general_investing",
  "category_name_ja": "投資全般",
  "topics": [...],
  "config": {
    "min_score": 50,
    "min_comments": 10,
    "time_filter": "week"
  }
}
```

### Phase 2 出力ファイル（カテゴリ別）: .tmp/reddit-topics/analyzed-{timestamp}-{group_key}.json

reddit-topic-analyzer がカテゴリごとに独立して出力するファイル（追記なし・新規作成）。
全カテゴリ完了後、ステップ 2.2 でオーケストレーターが集約して表示します。

---

## エラーハンドリング

| エラー | 対処 |
|--------|------|
| E001: Reddit MCP 未設定 | エラーメッセージ（.mcp.json 設定方法案内）を出力して処理中断 |
| E002: subreddit 取得失敗 | `fetch_errors` に記録して継続（他の subreddit を処理） |
| E003: フィルタ後0件 | 警告 W001 を表示（グループ単位）して継続 |
| E004: .tmp ディレクトリ作成失敗 | エラー詳細を出力して処理中断 |
| E005: reddit-topic-analyzer 失敗 | エラーを出力してそのグループをスキップ、次のグループへ継続 |
| E006: finance-full 起動失敗 | エラー詳細を出力、手動実行方法を案内 |

---

## 完了条件

- [ ] Phase 1: AskUserQuestion によるグループ選択が完了している（または --groups で指定済み）
- [ ] Phase 1: ToolSearch('reddit') が成功している（失敗時はエラーメッセージで終了）
- [ ] Phase 1: 選択グループの hot/top 投稿が取得されている
- [ ] Phase 1: フィルタリング・重複除去が適用されている
- [ ] Phase 1: `.tmp/reddit-topics/{timestamp}.json` が保存されている
- [ ] Phase 1: 収集結果のテーブルが表示されている
- [ ] Phase 2: --deep 指定時のみ、reddit-topic-analyzer が**逐次**呼び出されている
- [ ] Phase 2: --deep 指定時、`analyzed-{timestamp}-{group_key}.json` がカテゴリ別に生成されている
- [ ] Phase 2: --deep 指定時、高優先度 記事化提案の集約テーブルが表示されている
- [ ] Phase 3: AskUserQuestion によるトピック選択が完了している（0: スキップ含む）
- [ ] Phase 3: 0 選択時（スキップ）もワークフローが正常完了している
- [ ] Phase 3: トピック選択時、`Skill: finance-full` が `--category` パラメータ付きで起動されている

---

## 関連リソース

| リソース | パス |
|---------|------|
| グループ・フィルタ設定 | `data/config/reddit-subreddits.json` |
| コマンド定義 | `.claude/commands/reddit-finance-topics.md` |
| 深掘り分析エージェント | `.claude/agents/reddit-topic-analyzer.md` |
| フォーク元スキル | `.claude/skills/ai-research-workflow/SKILL.md` |
| Reddit MCP サンプル | `.claude/agents_sample/research-reddit.md` |

## 変更履歴

### 2026-02-24: 受け入れ条件レビュー・確定（Issue #3648）

- **受け入れ条件を全項目確認**: allowed-tools・3フェーズ構成・逐次 Task・finance-full ブリッジ・Reddit MCP エラーメッセージをすべて満たしていることを確認
- **関連ファイルとの整合性確認**: `data/config/reddit-subreddits.json`・`reddit-topic-analyzer.md`・`reddit-finance-topics.md` コマンドとの整合を確認

### 2026-02-23: 初版作成（Issue #3648）

- **ai-research-workflow からフォーク**: 3フェーズアーキテクチャを踏襲
- **Reddit MCP 統合**: ToolSearch('reddit') によるロード、hot/top 投稿取得
- **グループ別収集**: `data/config/reddit-subreddits.json` の5グループ対応
- **逐次 Phase 2**: Reddit API レート制限対応のため reddit-topic-analyzer を逐次呼び出し
- **finance-full ブリッジ**: `category_mapping` を使用した自動カテゴリ決定
- **Reddit MCP 未設定エラー**: .mcp.json 設定方法を含む詳細なエラーメッセージ
