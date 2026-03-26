# 議論メモ: creator-enrichment Genre誤分類 根本原因調査 & 3バグ修正

**日付**: 2026-03-26
**参加**: ユーザー + AI

## 背景・コンテキスト

`disc-2026-03-26-creator-quality-fix-execution` でGenre誤分類の一括修正（101件）とsource_url充填（1,491件）を実行した。
beauty-romance→career が 88件と想定より大規模だったため、enrichmentスクリプトの根本原因調査を実施。

## 根本原因: 3バグカスケード

beauty-romance ジャンルに career コンテンツが混入した原因は以下の3バグが連鎖して発生:

### Bug 1: Q4クエリのジャンルフィルタ欠落（主要因）

**ファイル**: `src/creator_enrichment/phases/gap_analysis.py`

```cypher
-- BEFORE（バグ）: $genre_id パラメータは WHERE 句に含まれておらず、
-- g 変数が WITH 句で使われないため全ジャンルのコンテンツを集計していた
OPTIONAL MATCH (content)-[:IN_GENRE]->(g:Genre {genre_id: $genre_id})
WITH concept.name AS name, cc.name AS category,
     count(DISTINCT content) AS content_count

-- AFTER（修正）: WHERE 条件に IN_GENRE フィルタを追加
WHERE (content:Fact OR content:Tip OR content:Story)
  AND (content)-[:IN_GENRE]->(:Genre {genre_id: $genre_id})
WITH concept.name AS name, cc.name AS category,
     count(DISTINCT content) AS content_count
```

結果: beauty-romance サイクル選択時にも career 系 Concept（アフィリエイト副業 etc.）が
低カバレッジ上位に上がり、career 向けクエリが生成されていた。

### Bug 2: LLMプロンプトのcareer偏重例文（増幅要因）

**ファイル**: `src/creator_enrichment/phases/search.py`

`_QUERY_GENERATION_PROMPT` の例文が全て career 系（"affiliate marketing side hustle tips 2026", "副業 アフィリエイト 成功事例 2026"）だったため、beauty-romance ジャンルを指定しても LLM が career 系クエリを生成することがあった。

**修正**: 例文を削除し、「必ず{genre_name_ja}ジャンルに関連するクエリのみ生成」という明示的制約を追加。

### Bug 3: IN_GENRE上書きによる誤ジャンル変更（伝播要因）

**ファイル**: `src/creator_enrichment/neo4j_writer.py`

IN_GENRE リレーションが常に既存を削除して新規作成していたため、career コンテンツが beauty-romance サイクルで再処理された際に、ジャンルが beauty-romance に変更されていた。

**修正**: 既存ジャンルと同じ場合はスキップ、異なる場合のみ削除・付け替えするガードを追加:

```cypher
OPTIONAL MATCH (a)-[existing:IN_GENRE]->(current_genre:Genre)
WITH a, b, existing, current_genre
WHERE existing IS NULL OR current_genre.genre_id <> row.to_id
FOREACH (_ IN CASE WHEN existing IS NOT NULL THEN [1] ELSE [] END |
    DELETE existing
)
WITH a, b
MERGE (a)-[:IN_GENRE]->(b)
```

## 修正結果

- 全3バグを修正
- 回帰テスト追加: `test_正常系_Q4がgenre_idパラメータつきで呼ばれる`（Bug 1の再発防止）
- テスト 208件 pass

## 決定事項

1. **Q4クエリはジャンルフィルタ必須**: `$genre_id` パラメータは WHERE 句のフィルタ条件として使用する
2. **LLMプロンプトに例文を含めない**: ジャンル名のみ変数化し、例文のバイアスを排除する
3. **IN_GENRE は同一ジャンルなら上書きしない**: 誤ジャンル付与の伝播を防ぐ保護機能を維持する

## アクションアイテム（引き継ぎ）

- [ ] **[中] 孤立Concept 2,117件の削減** (`act-2026-03-26-concept-isolation-reduce`) — pending
- [ ] **[中] self-development ジャンル増強** (`act-2026-03-26-self-development-boost`) — pending
- [ ] **[高] backfill_creator_source_published_at.py の本番実行** (`act-2026-03-26-backfill-run`) — pending

## 次回の議論トピック

- beauty-romance / spiritual ジャンルの enrichment 再開（修正後の動作確認）
- Concept粒度の見直し（4,177件は多すぎる可能性）
- careerジャンルでの記事生成パイプライン設計

## 参考情報

- 3バグ修正済みファイル: `src/creator_enrichment/phases/gap_analysis.py`, `search.py`, `neo4j_writer.py`
- 回帰テスト: `tests/unit/test_creator_enrichment/test_gap_analysis.py::TestLowCoverageConcepts::test_正常系_Q4がgenre_idパラメータつきで呼ばれる`
- 前回実行結果: Genre修正101件（spiritual→career 13件, beauty-romance→career 88件）、source_url充填1,491件
