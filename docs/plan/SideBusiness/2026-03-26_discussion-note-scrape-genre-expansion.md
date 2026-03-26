# 議論メモ: note-scrape max-articles無制限化 & asset-managementジャンル追加

**日付**: 2026-03-26
**参加**: ユーザー + AI

## 背景・コンテキスト

note-scrapeスキルで全記事を取得したいケース（hide_taxnote等）が発生。また、資産形成・投資系クリエイターを適切なジャンルで管理するため、新ジャンルの追加が必要になった。

## 議論のサマリー

### --max-articles 無制限化

- **変更前**: `--max-articles` デフォルト = 50
- **変更後**: `--max-articles` デフォルト = None（無制限）
- Python の `list[:None]` が全要素を返す性質を利用し、スライスコードは変更なし
- 明示的に制限したい場合は `--max-articles 30` のように指定可能

**変更ファイル**:
- `src/data_pipeline/__main__.py`: L478 `default=None`、help更新、print文でNone→「無制限」表示
- `.claude/skills/note-scrape/SKILL.md`: デフォルト値の記述更新

### asset-management ジャンル追加

既存ジャンル（career / beauty-romance / spiritual / self-development）はいずれも資産形成・投資系クリエイターとミスマッチだったため、`asset-management`（資産形成・投資）を新設。

**変更ファイル**:
- `scripts/emit_creator_queue_v2.py`: GENRE_NAMES に追加
- `scripts/emit_creator_queue.py`: GENRE_NAMES に追加
- `src/creator_enrichment/config.py`: GENRE_NAMES リストに追加

### hide_taxnote スクレイピング + 投入

- **URL**: https://note.com/hide_taxnote
- **スクレイピング**: 19件取得（有料スキップ0・重複0）
- **投入ジャンル**: asset-management
- **投入結果**: Facts 9 / Tips 8 / Stories 2 → ノード148 / リレーション137
- **RSSモニター**: asset-managementジャンルで登録済み

## 決定事項

1. `--max-articles` のデフォルトを無制限（None）に変更する（後方互換あり）
2. `asset-management`（資産形成・投資）ジャンルをcreator-neo4jパイプラインに追加する

## アクションアイテム

なし（実装・投入まで完了）

## 次回の議論トピック

- asset-managementジャンルのConcept分類カテゴリが適切かレビュー
  （現在はcareerジャンル向けのConceptCategoryLayersを流用している）
- hide_taxnote以外の資産形成系クリエイターの追加候補

## 参考情報

- 変更コミット対象ファイル: `__main__.py`, `emit_creator_queue_v2.py`, `emit_creator_queue.py`, `config.py`, `SKILL.md`
- creator-neo4j投入バイナリ: `.tmp/creator-graph-queue/cq-20260326110603-d8fe6de1.json`
