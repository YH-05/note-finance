---
name: emit-research-queue
description: |
  アドホック調査データを research-neo4j に投入するためのスキル。
  リサーチ結果の入力 JSON を構築し、emit_graph_queue.py --command web-research で
  graph-queue JSON を生成した後、/save-to-graph でNeo4jに投入する。
  Use PROACTIVELY when リサーチ結果をナレッジグラフに永続化したい場合。
allowed-tools: Read, Write, Bash, Glob
---

# emit-research-queue スキル

アドホック調査データ（Web検索、論文、レポート等）を research-neo4j に投入するためのスキル。
`emit_graph_queue.py --command web-research` のラッパーとして、リサーチ後の Neo4j 永続化フローを統一する。

## 処理フロー

```
1. 入力 JSON 構築（インラインまたはファイル指定）
2. uv run python scripts/emit_graph_queue.py --command web-research --input {file}
3. graph-queue JSON を生成（.tmp/graph-queue/web-research/ に出力）
4. /save-to-graph チェーン呼び出し
```

## 入力 JSON スキーマ

入力 JSON は `.tmp/research-input/` に保存し、`emit_graph_queue.py` に渡す。

### 全体構造

```json
{
  "session_id": "research-20260319-macro-us",
  "research_topic": "米国マクロ経済動向 2026Q1",
  "as_of_date": "2026-03-19",
  "sources": [...],
  "entities": [...],
  "topics": [...],
  "facts": [...]
}
```

### フィールド定義

| フィールド | 必須 | 型 | 説明 |
|---|---|---|---|
| `session_id` | Yes | string | セッション識別子（一意） |
| `research_topic` | Yes | string | リサーチトピック名 |
| `as_of_date` | Yes | string | データ基準日（YYYY-MM-DD 形式） |
| `sources[]` | Yes | array | 情報源リスト（1件以上） |
| `entities[]` | No | array | エンティティリスト |
| `topics[]` | No | array | トピックリスト |
| `facts[]` | Yes | array | ファクトリスト（1件以上） |

### sources[] フィールド

| フィールド | 必須 | 型 | 説明 |
|---|---|---|---|
| `url` | Yes | string | ソースURL |
| `title` | Yes | string | ソースタイトル |
| `authority_level` | Yes | string | 信頼度レベル（下記参照） |
| `published_at` | Yes | string | 公開日（YYYY-MM-DD 形式） |
| `source_type` | No | string | ソース種別（article, report, paper 等） |

#### authority_level 許容値

| 値 | 説明 | 例 |
|---|---|---|
| `official` | 公的機関・企業の公式発表 | 中央銀行声明、決算短信、政府統計 |
| `analyst` | セルサイド/バイサイドアナリストレポート | 証券会社レポート、格付機関レポート |
| `media` | 主要メディアの報道 | Reuters, Bloomberg, 日経新聞 |
| `blog` | ブログ・個人メディア | Substack, note.com, Medium |
| `social` | SNS・フォーラム | Reddit, X(Twitter), StockTwits |
| `academic` | 学術論文・研究機関 | NBER, IMF Working Paper, 大学研究 |

### entities[] フィールド

| フィールド | 必須 | 型 | 説明 |
|---|---|---|---|
| `name` | Yes | string | エンティティ名 |
| `entity_type` | Yes | string | エンティティ種別（company, index, currency, commodity 等） |

### topics[] フィールド

| フィールド | 必須 | 型 | 説明 |
|---|---|---|---|
| `name` | Yes | string | トピック名 |
| `category` | Yes | string | カテゴリ（macro, equity, fx, commodity 等） |

### facts[] フィールド

| フィールド | 必須 | 型 | 説明 |
|---|---|---|---|
| `content` | Yes | string | ファクトの内容（具体的な事実・データ） |
| `source_url` | Yes | string | このファクトの出典URL（`sources[]` 内の URL と一致必須） |
| `confidence` | No | float | 確信度（0.0-1.0） |
| `about_entities[]` | No | array | 関連エンティティ（`name` と `entity_type` を含む） |

## 使用手順

### ステップ 1: 入力 JSON を構築

リサーチ結果から入力 JSON を構築し、`.tmp/research-input/` に保存する。

```bash
# 保存先ディレクトリ作成
mkdir -p .tmp/research-input
```

```json
{
  "session_id": "research-20260319-fed-rate",
  "research_topic": "FRB利下げサイクル分析",
  "as_of_date": "2026-03-19",
  "sources": [
    {
      "url": "https://www.federalreserve.gov/monetarypolicy/fomcminutes20260319.htm",
      "title": "FOMC Minutes - March 2026",
      "authority_level": "official",
      "published_at": "2026-03-19",
      "source_type": "report"
    },
    {
      "url": "https://www.reuters.com/markets/fed-holds-rates-steady/",
      "title": "Fed holds rates steady amid uncertainty",
      "authority_level": "media",
      "published_at": "2026-03-19",
      "source_type": "article"
    }
  ],
  "topics": [
    {
      "name": "FRB金融政策",
      "category": "macro"
    }
  ],
  "entities": [
    {
      "name": "Federal Reserve",
      "entity_type": "institution"
    }
  ],
  "facts": [
    {
      "content": "FRBは2026年3月FOMCで政策金利を4.25-4.50%に据え置き",
      "source_url": "https://www.federalreserve.gov/monetarypolicy/fomcminutes20260319.htm",
      "confidence": 1.0,
      "about_entities": [
        {
          "name": "Federal Reserve",
          "entity_type": "institution"
        }
      ]
    },
    {
      "content": "FOMC声明文ではインフレの上振れリスクに言及、利下げ時期の後ずれを示唆",
      "source_url": "https://www.reuters.com/markets/fed-holds-rates-steady/",
      "confidence": 0.9,
      "about_entities": [
        {
          "name": "Federal Reserve",
          "entity_type": "institution"
        }
      ]
    }
  ]
}
```

### ステップ 2: graph-queue JSON を生成

```bash
uv run python scripts/emit_graph_queue.py \
  --command web-research \
  --input .tmp/research-input/{session_id}.json
```

出力先: `.tmp/graph-queue/web-research/gq-{timestamp}-{hash4}.json`

### ステップ 3: Neo4j に投入

`/save-to-graph` スキルを呼び出して graph-queue JSON を Neo4j に投入する。

```bash
/save-to-graph --source web-research
```

## 投入前チェックリスト

データ投入の実行前に、以下の5項目を全て確認すること（`.claude/rules/neo4j-write-rules.md` 準拠）:

- [ ] 入力 JSON に `sources[].authority_level` が設定されているか
- [ ] `facts[].source_url` が `sources` 内の URL と一致しているか
- [ ] `emit_graph_queue.py --command web-research` で graph-queue JSON が生成できるか
- [ ] graph-queue JSON の `fact_entity` のリレーションタイプが `RELATES_TO` であるか
- [ ] `/save-to-graph` 実行前に MATCH クエリで対象データ件数を確認したか

## エラーハンドリング

| エラー | 原因 | 対処 |
|---|---|---|
| `KeyError: 'authority_level'` | sources に authority_level が未設定 | 全ソースに authority_level を設定 |
| `Fact source_url not found in sources` | facts の source_url が sources に存在しない | source_url を sources 内の URL と一致させる |
| graph-queue JSON が空 | 入力 JSON のフォーマット不正 | 入力 JSON スキーマを確認 |
| `/save-to-graph` 失敗 | Neo4j 未起動 | Neo4j を起動してから再実行 |

## 関連ファイル

| リソース | パス |
|---------|------|
| graph-queue 生成スクリプト | `scripts/emit_graph_queue.py` |
| Neo4j 投入スキル | `.claude/skills/save-to-graph/SKILL.md` |
| Neo4j 直書き禁止ルール | `.claude/rules/neo4j-write-rules.md` |
| ナレッジグラフスキーマ | `data/config/knowledge-graph-schema.yaml` |
| graph-queue 出力先 | `.tmp/graph-queue/web-research/` |
