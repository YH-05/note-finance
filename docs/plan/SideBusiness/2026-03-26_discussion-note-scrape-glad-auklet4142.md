# 議論メモ: note.com/glad_auklet4142 スクレイピング & RSS登録

**日付**: 2026-03-26
**参加**: ユーザー + AI

## 背景・コンテキスト

note.com クリエイター `glad_auklet4142` を creator-neo4j のナレッジグラフに取り込むため、
`/note-scrape` スキルで全記事をスクレイピングし、RSS モニターに追加した。

## 実行内容

### Phase 1: スクレイピング

```
uv run python -m data_pipeline note-com scrape glad_auklet4142 --max-articles 50
```

- 記事URL: 19件
- 保存: 19件
- 有料スキップ: 0件
- 重複スキップ: 0件

### Phase 2: Neo4j 投入（creator-neo4j）

```
uv run python -m data_pipeline ingest --source note-com-glad_auklet4142 --target creator --genre career
```

| 項目 | 件数 |
|------|------|
| 読み込み | 19件 |
| Facts | 10件 |
| Stories | 8件 |
| Tips | 0件 |
| Entities | 75件 |
| Neo4j ノード | 166件 |
| Neo4j リレーション | 139件 |
| スキップ（JSON parse error） | 1件 |

スキップされた記事: 「月商1000万でも「毎朝起きるのが怖い」と彼は言った...」
（本文が長く、LLM の JSON レスポンスパースに失敗）

### Phase 3: RSS モニター登録

```
uv run python -m data_pipeline note-com add glad_auklet4142 --genre career
```

`data/config/note-com-creators.json` に `rss_enabled=true` で追加。

## 決定事項

1. `glad_auklet4142` を RSS モニター対象に追加（genre: career）
   - 新着記事を自動検知し、launchd 定期実行（03:00/21:00 JST）で取得

## RSSモニター実装の確認

**対象コード**: `src/data_pipeline/collectors/note_com_rss.py`
**クラス**: `NoteComRssMonitor`

フロー:
1. `data/config/note-com-creators.json` から `enabled=true` & `rss_enabled=true` のクリエイターを読み込み
2. `https://note.com/{username}/rss` を `feedparser` で取得
3. RawStore 未保存エントリのみ抽出（`_filter_new`）
4. 新着がある場合のみ `NoteComBrowser`（Playwright）でスクレイピング
5. 有料記事はスキップ、無料記事を RawStore 保存
6. `last_rss_checked_at` をコンフィグに書き戻し

**エントリーポイント**:
```bash
uv run python -m data_pipeline note-com monitor
```

## アクションアイテム

- [ ] JSON parse エラーが発生した1件（月商1000万記事）を手動で再試行または原因調査（優先度: 低）

## 参考情報

- クリエイタープロフィール: `https://note.com/glad_auklet4142`
- 記事ジャンル: 金融・地政学（中東・ロシア・インド）、AI・半導体、SNS運用・ライティング
- graph-queue: `.tmp/creator-graph-queue/cq-20260326101925-a19de49c.json`
