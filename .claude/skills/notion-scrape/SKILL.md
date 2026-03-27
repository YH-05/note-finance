---
name: notion-scrape
description: >
  Notion Database（メインDB: 2d18b707-7dce-801e-bc9d-ff46f91e4d42）からアイテムを取得し、
  RawStore経由で creator-neo4j または research-neo4j に投入するスキル。
  タグ・期間・件数・投入先を自然言語で指定できる。
  「Notionから取ってきて」「NotionのDBをneo4jに入れて」「notion scrape」
  「ai_snsタグの直近1週間をcreator-neo4jに」「side_businessのアイテムをとってきて」
  と言われたら必ずこのスキルを使うこと。note.com スクレイピング（/note-scrape）とは別スキル。
---

# notion-scrape スキル

Notion Database からアイテムを自然言語指定でフェッチし、Neo4j に投入するパイプライン。

## 実行スクリプト

```
/Users/yukihata/Desktop/note-finance/scripts/fetch_notion_database.py
```

実行方法:
```bash
cd /Users/yukihata/Desktop/note-finance
uv run python scripts/fetch_notion_database.py [OPTIONS]
```

## Step 1: 自然言語からパラメータを解釈する

ユーザーの発言から以下の5パラメータを抽出する。

### タグ（`--tag TAG`）

Notion DB の `tags` プロパティでフィルタリングする。利用可能なタグ:

| タグ名 | 内容 | 推奨ターゲット |
|-------|------|-------------|
| `ai_sns` | AI×SNS活用 | creator |
| `ai_agent` | AIエージェント | creator |
| `ai_writing` | AI文章生成 | creator |
| `ai_coding` | AIコーディング | creator |
| `ai_image` | AI画像生成 | creator |
| `ai_rag` | RAG・検索拡張 | research |
| `ai_database` | AIデータベース | research |
| `side_business` | 副業 | creator |
| `knowledge_management` | 知識管理 | creator |
| `study` | 学習 | creator |
| `note_summary` | noteまとめ | creator |
| `scrapbook` | スクラップブック | creator |
| `finance` | 金融・投資 | research |
| `quants` | クオンツ | research |
| `python` | Python | research |
| `Claude` | Claude AI | creator |
| `notion` | Notion | creator |
| `memo` | メモ | creator |

ユーザーが言及した言葉からタグを推定する（例: 「AI副業」→ `side_business` または `ai_sns`）。
複数タグの指定は非対応（1つ選ぶ）。タグ不明・全件の場合は `--tag` を省略。

### 期間（`--since YYYY-MM-DD`）

「直近N日」「今週」「今月」などの表現を日付に変換する。
日付計算は Bash で実行する:

```bash
# 直近7日（1週間）
SINCE=$(python3 -c "from datetime import date,timedelta; print((date.today()-timedelta(days=7)).strftime('%Y-%m-%d'))")

# 直近3日
SINCE=$(python3 -c "from datetime import date,timedelta; print((date.today()-timedelta(days=3)).strftime('%Y-%m-%d'))")

# 今月（月初）
SINCE=$(python3 -c "from datetime import date; print(date.today().replace(day=1).strftime('%Y-%m-%d'))")

# 直近N日（汎用）
SINCE=$(python3 -c "from datetime import date,timedelta; print((date.today()-timedelta(days=N)).strftime('%Y-%m-%d'))")
```

期間指定なしなら `--since` を省略（全期間）。

### 件数上限（`--max-pages N`）

「N件だけ」「最大N件」「直近N件」→ `--max-pages N`
指定なしなら省略（全件）。

### 投入先と投入実行（`--ingest --target creator|research`）

| ユーザー発言 | 引数 |
|------------|------|
| 「creator-neo4jに入れて」「creatorに投入」 | `--ingest --target creator` |
| 「research-neo4jに入れて」「researchに投入」 | `--ingest --target research` |
| 「RawStoreに保存だけ」「保存のみ」 | `--ingest` なし |
| 投入先不明 | タグから自動推定（上表参照）→ それでも不明なら質問する |

### ジャンル（`--genre GENRE`）

creator向け投入時のジャンル分類。デフォルトは `career`。
「financeジャンル」「副業ジャンル」などユーザーが言及した場合に指定する。

## Step 2: コマンドを組み立てて実行する

```bash
cd /Users/yukihata/Desktop/note-finance

# 例1: タグ+期間+投入
SINCE=$(python3 -c "from datetime import date,timedelta; print((date.today()-timedelta(days=7)).strftime('%Y-%m-%d'))")
uv run python scripts/fetch_notion_database.py \
  --tag ai_writing \
  --since "$SINCE" \
  --ingest --target creator

# 例2: タグのみ、全件取得、RawStore保存だけ
uv run python scripts/fetch_notion_database.py --tag side_business

# 例3: 件数制限+dry-run
uv run python scripts/fetch_notion_database.py --tag finance --max-pages 10 --dry-run

# 例4: 全件、research-neo4jに投入
uv run python scripts/fetch_notion_database.py --tag finance --ingest --target research
```

`source_id` は自動決定される:
- タグあり → `notion-db-{tag}`（例: `notion-db-ai_sns`）
- タグなし → `notion-db`

## Step 3: 結果の確認と次ステップ案内

スクリプト実行後、出力された統計を確認してユーザーに報告する:
- 取得件数・保存件数・重複スキップ件数
- `--ingest` なしの場合は次のコマンドを案内:
  ```
  uv run python -m data_pipeline ingest --source notion-db-{tag} --target {target} --genre career
  ```

## よくある使用例

| ユーザー発言 | 実行コマンドのポイント |
|------------|-------------------|
| `ai_writingタグの直近1週間をcreatorに` | `--tag ai_writing --since {7日前} --ingest --target creator` |
| `side_businessのNotionアイテムを全部とってきて` | `--tag side_business` |
| `financeタグ10件をresearchに投入` | `--tag finance --max-pages 10 --ingest --target research` |
| `Notionの全アイテムをdry-run` | `--dry-run` |
| `今月追加したai_agentを取ってきて` | `--tag ai_agent --since {月初日付}` |

## 注意事項

- `--tag` に指定するのは**タグ名の完全一致**（スペースなし）
- `--since` は `Created time`（Notionへの追加日）でフィルタリングする（記事の公開日ではない）
- note.com スクレイピングは別スキル（`/note-scrape`）を使うこと
