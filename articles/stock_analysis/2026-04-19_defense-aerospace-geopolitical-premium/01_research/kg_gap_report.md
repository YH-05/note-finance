# KG Gap Report — Skipped

**Date**: 2026-04-19
**Status**: SKIPPED

research-neo4j (bolt://localhost:7688) に接続不可のため、Step 0（KG既存データ照会 + ギャップ分析）と Step 4（KG永続化）をスキップしました。

入力JSONは `.tmp/research-input/article-research-defense-aerospace-20260419.json` に保持し、Neo4j 起動後に以下のコマンドで投入可能:

```bash
uv run python scripts/emit_research_queue.py \
  --command web-research \
  --input .tmp/research-input/article-research-defense-aerospace-20260419.json
/save-to-research-graph
```

なお、過去の関連トピック（Iran戦争・原油$200・地政学）に関してはKGに記事化済みFactが存在する可能性が高いが、今回はWeb検索（Tavily 10クエリ）で直接ソース収集を実施した。
