# 設計メモ: 株投資ラボのnote記事 → research-neo4j 投入パイプライン

**日付**: 2026-04-27
**目的**: ローカル `articles/` 配下の記事 (revised_draft.md + meta.yaml) を research-neo4j に投入し、topic-suggest スキルが「自分の知識ギャップ」を抽出できるようにする。

## 設計方針

### Source ノードへのマッピング

各記事は `Source` ラベルの単一ノードとして投入。`source_type='own_article'` で識別。

| Source プロパティ | meta.yaml フィールド |
|------------------|---------------------|
| `source_id` | `f"own-{article_id}"` |
| `url` | `draft_url`（noteエディタURL）または `f"local://articles/{category}/{article_id}"` |
| `title` | `topic` または `title` |
| `source_type` | `"own_article"` |
| `authority_level` | `"own"` |
| `published` | `published_at`（未公開なら `created_at`） |
| `category` | `category` |
| `article_id` | `article_id` |
| `target_audience` | `target_audience` |
| `target_wordcount` | `target_wordcount` |
| `status` | `status`（published/draft/review/researched/revised） |
| `article_type` | `type`（column 等） |
| `created_at` | `created_at` |
| `updated_at` | `updated_at` |
| `domain` | `"note.com/kabushiki-labo"` |
| `command_source` | `"own-articles"` |

### Topic ノードへのマッピング

- カテゴリ Topic（既存と統合）: `topic_key = f"category:{category}"` で MERGE
- 記事固有 Topic: `topic_key = f"article:{article_id}"`（topic_id は uuid）

### Symbol → Entity リンク

`symbols`, `tickers`, `fred_series` 等のシンボルは Entity（個別ラベル）への RELATES_TO リレーションとして投入する（既存の entity_linker.py に委譲）。

### Chunk 投入（v1 では省略）

revised_draft.md の本文は v1 では Source.full_text プロパティに格納しない（容量過大）。代わりに以下のメタ情報のみ保持:
- `draft_chars`: 本文文字数
- `keywords`: 上位10キーワード（mine_local_articles.py で抽出済み）

将来拡張で Chunk + Fact 抽出を追加可能。

## 実装ファイル

| ファイル | 役割 |
|---------|------|
| `scripts/emit_own_articles_queue.py` | articles/ を走査して入力 JSON 生成 + emit_research_queue.py 呼び出し |
| `scripts/mappers/own_articles.py` | BaseMapper サブクラス。Source + Topic を生成 |
| `scripts/mappers/__init__.py` | COMMAND_MAPPERS に `own-articles` を追加 |
| `scripts/emit_research_queue.py` | docstring に `own-articles` を追加 |

## 冪等性

- `source_id = "own-" + article_id` で安定ID
- 全ノードは MERGE 投入（既存 pipeline 利用）
- 再実行で内容更新、ノード数は増加しない

## 検証クエリ

```cypher
MATCH (s:Source {source_type: 'own_article'})
RETURN count(s) AS total, collect(DISTINCT s.category) AS categories
```

期待: total >= 50（Phase 1-A の `mine_local_articles.py` で 58 件確認済み）
