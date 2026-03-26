# 議論メモ: JETRO スクレイパー 本文取得 & max_articles 早期終了修正

**日付**: 2026-03-26
**参加**: ユーザー + AI

## 背景・コンテキスト

`disc-2026-03-26-jetro-log-fix-archive-pages` の同日に発覚した問題。
出力 JSON の `content` / `summary` が常に `null` で、本文テキストが取れていなかった。

## 議論のサマリー

### 1. 問題の確認

出力 JSON の構造:
```json
{
  "title": "中国、臨時調整措置で...",
  "content": null,
  "summary": null
}
```

### 2. 原因分析

| フェーズ | `--include-content` なし | `--include-content` あり |
|---|---|---|
| Phase 1（RSS） | `content=null`（RSSのdescriptionが空） | **本文取得できる** |
| Phase 2（カテゴリ） | `content=null` | null のまま（未実装） |
| Phase 3（アーカイブ） | `content=null` | null のまま（未実装） |

JETROのRSSフィードは `<description>` が空のため `summary` も常に null。

### 3. バグ発見: 無駄なHTTPリクエスト

`--max-articles 3` を指定しても RSS フィードの全40件にHTTPリクエストが送られていた。

**原因**: `_collect_rss_articles` が全エントリを処理してから返し、`collect_news` の最後で件数を絞っていた。

### 4. 修正内容

**`src/news_scraper/jetro.py`**:

```python
# _collect_rss_articles に max_articles パラメータ追加
def _collect_rss_articles(
    entries, config, delay,
    max_articles: int = 0,  # 0 = 無制限
) -> list[Article]:
    ...
    for i, entry in enumerate(entries):
        if max_articles > 0 and len(articles) >= max_articles:
            break  # 早期終了
        ...

# collect_news から max_per_source を渡す
articles = _collect_rss_articles(entries, config, delay, max_articles=max_per_source)
```

### 5. 検証結果

```
修正前: --max-articles 3 → 40件分のHTTPリクエスト
修正後: --max-articles 3 → 3件分のHTTPリクエストのみ

本文取得例:
- 中国、臨時調整措置で石油製品の急騰抑制... → 989文字
- 台湾中油、ガソリン・軽油価格を引き上げ  → 1596文字
- 在中国日系企業の最大の競合相手は中国企業 → 1344文字
```

## 決定事項

1. **`--include-content` フラグが本文取得の必須オプション**: デフォルト動作は本文なし。KG投入・記事素材用途では必ず付ける
2. **`max_articles` 早期終了を実装**: HTTPリクエスト数を指定件数に抑制

## アクションアイテム

- [ ] Phase 2/3（Playwright クロール）でも `--include-content` を効かせる実装（優先度: 中）
- [ ] `_collect_rss_articles` の `max_articles` 早期終了のユニットテスト追加（優先度: 低）

## 次回の議論トピック

- Phase 2/3 での本文取得実装（Playwright クロール記事に対する httpx フェッチ追加）
- archive_pages 実運用テスト（`--regions id --archive-pages 3 --include-content`）
- 定期実行設定（macOS launchd）

## Neo4j 保存情報

- Discussion: `disc-2026-03-26-jetro-content-fetch-fix`
- Decision: `dec-2026-03-26-include-content-usage`, `dec-2026-03-26-max-articles-early-stop`
- 前回: `disc-2026-03-26-jetro-log-fix-archive-pages` → `FOLLOWED_BY` → 今回
