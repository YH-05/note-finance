# 議論メモ: Notion Database → Neo4j 投入パイプライン設計・実装

**日付**: 2026-03-27
**参加**: ユーザー + AI

## 背景・コンテキスト

Notion DBに蓄積されたアイテム（タグ付きWebページ・メモ）をcreator-neo4jまたはresearch-neo4jに投入するパイプラインが存在しなかった。Notion MCPでの接続を調査した結果、`API-query-data-source`は400エラーで使用不可であることを確認（既存メモリに記録済み）。REST APIを使ったスタンドアロンスクリプトで実装することになった。

## 議論のサマリー

### Notion DB構造の確認

- **DB ID**: `2d18b707-7dce-801e-bc9d-ff46f91e4d42`（メインDB "🕋 Database"）
- **主要プロパティ**: `Name`（title）、`URL`（url）、`tags`（multi_select）、`Created time`（created_time）
- **ブロックタイプ**: paragraph, heading_1/2/3, bulleted_list_item, numbered_list_item, quote, callout, code, divider, image

### パイプライン設計

Notion REST API → RawStore → `data_pipeline ingest` という2段パイプライン方式を採用。

- **スクリプト**: `scripts/fetch_notion_database.py`
- **スキル**: `.claude/skills/notion-scrape/SKILL.md`
- **source_id パターン**: `notion-db-{tag}`（例: `notion-db-ai_sns`）またはタグなしで `notion-db`

### 実装のポイント

- `--since YYYY-MM-DD`: Notionの`Created time`（Notionへの追加日）でフィルタリング
- `--tag`: multi_select contains フィルタ
- `--ingest --target creator|research`: RawStore保存後にdata_pipeline ingestを自動実行
- レートリミット: リクエスト間に0.2-0.3秒スリープ

## 決定事項

1. **パイプライン実装方式**: Notion REST API直接呼び出しのスタンドアロンスクリプト + RawStore再利用方式
   - 理由: MCP toolsはClaude sessions専用でバッチ実行不可。REST APIなら独立実行可能。RawStore再利用により既存のdata_pipeline ingestコマンドが変更なく使える

2. **スキル名**: `notion-scrape`（`note-scrape`ではない）
   - 理由: 既存の`.claude/skills/note-scrape/SKILL.md`がnote.com Playwrightスクレイパー用として存在するため命名競合を避けた

## アクションアイテム

- [ ] notion-scrapeスキルを使って全タグ（ai_sns, side_business, ai_writing, finance等）を本番モードで実行し、creator/research-neo4jに投入する (優先度: 中)
- [ ] `--since`オプションの統合テストを実行し、日付フィルタが正しく機能することを確認する (優先度: 低)

## 次回の議論トピック

- 本番ingest後のcreator-neo4jデータ品質確認
- `--since`フィルタの運用（定期バッチ化の検討）

## 参考情報

### スクリプト実行例

```bash
# dry-run（保存なし）
uv run python scripts/fetch_notion_database.py --tag ai_sns --dry-run

# タグ+期間+creator投入
SINCE=$(python3 -c "from datetime import date,timedelta; print((date.today()-timedelta(days=7)).strftime('%Y-%m-%d'))")
uv run python scripts/fetch_notion_database.py \
  --tag ai_writing \
  --since "$SINCE" \
  --ingest --target creator

# finance タグ全件 → research投入
uv run python scripts/fetch_notion_database.py --tag finance --ingest --target research
```

### タグ→ターゲット対応表

| タグ | 推奨ターゲット |
|------|--------------|
| ai_sns, ai_agent, ai_writing, ai_coding | creator |
| side_business, note_summary, Claude | creator |
| finance, quants, python, ai_rag | research |

### 関連ファイル

- `scripts/fetch_notion_database.py` — メインスクリプト
- `.claude/skills/notion-scrape/SKILL.md` — スキル定義
- `src/data_pipeline/storage/raw_store.py` — RawStore（既存、変更なし）
