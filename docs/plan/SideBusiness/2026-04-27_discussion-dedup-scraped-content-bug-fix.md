# 議論メモ: pipeline-scraped-news の content 転送バグ発見・修正・backfill 実行

**日付**: 2026-04-27
**参加**: ユーザー + AI
**Discussion ID**: `disc-2026-04-27-dedup-scraped-content-bug-fix`

## 背景・コンテキスト

`/pipeline-scraped-news` で 4/16 以来となる NAS scraped JSON の research-neo4j 投入を実行。dry-run で 2,480 記事の新規 ingest 候補を確認後、本実行で `4,285 ノード + 9,920 リレーション` を投入完了。

しかし投入結果を検証する過程で **Chunk が +0 件**（Source +2,482 / Claim +1,553 / Topic +5）であることに気付き、当初は「`scrape_finance_news.py` が本文を取得していない（act-2026-04-16-002）」と説明したが、ユーザーから「NAS のテキストはすでに本文付きのはず」と指摘を受けて再調査。

結果として、4/16 議論メモが想定していた根本原因が誤りで、**実際の犯人は `dedup_scraped._to_finance_news_format` が転送する5フィールドの中に content/category/tags/author が含まれていないこと**だったと判明。修正後、processed/ の再スキャンで 2,857 記事を backfill して Chunk/Author/Topic を補完。途中で Neo4j research DB が I/O エラーで stopping 状態になるトラブルもあったが、container restart で復旧して完了。

## 議論のサマリー

時系列で整理。

### 1. 投入実行（順調に見えた）

- dry-run で 2,480 件を確認（cnbc 505 / kabutan 434 / zero_hedge 389 / reuters_jp 308 / hacker_news 274 など 11 ソース）
- 本実行は exit 0、`投入ノード: 4,285 / 投入リレーション: 9,920` と報告
- レジストリ 4,079 → 6,559 URL（+2,480）

### 2. Chunk=0 の発見

verification を試みたが SKILL.md の `MATCH (n) WHERE n.created_at >= datetime(...)` クエリが Source ノードに `created_at` が無いため 0 件返却。代わりにベースライン（4/16）との差分で確認したところ:

| ラベル | 4/16 | 投入後 | delta |
|---|---:|---:|---:|
| Source | 4,595 | 7,077 | +2,482 ✓ |
| Claim | 3,043 | 4,596 | +1,553 |
| Fact | 3,528 | 3,539 | +11 |
| **Chunk** | **3,024** | **3,024** | **+0** ⚠ |
| Topic | 1,375 | 1,380 | +5 |

### 3. 誤った原因説明と訂正

最初は act-2026-04-16-002（「scrape_finance_news に content 取得を追加」）を引き合いに「スクレイパーが本文取ってないからです」と説明したが、ユーザーから「NAS の JSON は本文入ってるはず、確かめて」と指摘。

NAS サンプル（cnbc 4/26）を確認すると:

```json
{
  "title": "...",
  "url": "...",
  "summary": "...",  // ~150字
  "content": "...",  // ~3,500字（本文）
  "author": "...",
  "tags": [...],
  "category": "..."
}
```

全11ソースとも `content` フィールドあり（content_len: federal_reserve 460 〜 developing_telecoms 8,711）。**スクレイパーは正しく本文を取っていた**。

### 4. 真因特定

`scripts/dedup_scraped.py:_to_finance_news_format` を見ると:

```python
return {
    "url": ..., "title": ..., "summary": ...,
    "feed_source": ..., "published": ...,
}  # 5 フィールドのみ。content/category/tags/author を捨てている
```

一方 `scripts/mappers/finance_news.py:142-156` の `FinanceNewsMapper.map()` は `content` を Chunk として、`tags`/`category` を Topic として、`author` を Author として正しく emit する設計。

→ **dedup_scraped が上流で4フィールドを削っているせいで、Mapper が emit すべきものを emit できていなかった**。

### 5. 修正適用

`_to_finance_news_format` に4フィールド追加:

```python
return {
    "url": ..., "title": ..., "summary": ...,
    "feed_source": ..., "published": ...,
    "content": article.get("content") or "",
    "category": article.get("category", ""),
    "tags": article.get("tags") or [],
    "author": article.get("author") or "",
}
```

スモークテストで content/tags/author/category が転送されることを確認。

### 6. 別 PC のスクレイパーへの影響

ユーザーから「別 PC で launchd で動かしているスクレイパーは更新が必要か？」と質問。

回答: 不要。launchd で動いているのは `scrape_finance_news.py`（NAS への書き出し側）であり、修正対象は dedup_scraped.py（NAS から Neo4j への投入側、このMacのみで実行）。スクレイパー側は既に正しく content を NAS に書いているので、修正の影響を受けない。

### 7. Backfill 実行

ユーザーが「遡及補完を優先して」と指示。`.tmp/backfill_chunks.py` を作成し、`processed/{date}/` を再スキャン → URL レジストリは無視 → 修正済み `_to_finance_news_format` で finance-news 形式に変換 → emit_research_queue → ingest_graph_queue を回す方式で実装。

dry-run（dates 2026-04-17〜26）で 3,298 件と判明、ユーザーに「全6,559件」「今日の2,480のみ」「ソース単位で分割」の選択肢を提示し、「今日の2,480件のみ補完」を選択。実装で `--dates` 引数を `nargs="*"` に対応してから本実行。

実際の収集は 2,857 unique articles（2,480 + 過去 ingest 済みの今日の date 範囲分 818）。Stage 3 emit は成功（chunks=2,786 / authors=367 / topics=938 / claims=1,804）したが、Stage 4 で **`.tmp/backfill_chunks.py` の引数バグ**（`--queue-file` ではなく `--file` が正解）により ingest が起動せず失敗。

### 8. Neo4j research DB I/O エラー

正しい引数で `ingest_graph_queue.py --file <queue>` を直接実行したところ、Neo4j 側で:

```
neo4j.exceptions.DatabaseError: TransactionLogError
Could not append transaction (3,180 commands) to log
Caused by: java.io.IOException: Input/output error
  at /logs/security.log への書き込み失敗
```

`SHOW DATABASES` で確認すると **research DB が `stopping` 状態（statusMessage: Input/output error）**。他の DB（creator/note/quants/system/neo4j）は online。

ディスク空きは /Volumes/NeoData に 1.9TB 残あり（容量問題ではない）。原因は外付け SSD への一時的な OS レベル I/O glitch と推定。

ユーザーが「Neo4j コンテナごと restart」を選択。`docker restart neo4j-enterprise` で 11秒で healthy 復帰、research DB も online に戻った。データ破損なし（カウント維持）。

### 9. Backfill 再実行成功

復旧後、同じ queue file で再 ingest:

- **投入ノード: 8,999** / **投入リレーション: 21,628**
- 失敗: 0 件 / Exit code: 0

最終的なラベル件数:

| ラベル | backfill前 | backfill後 | delta |
|---|---:|---:|---:|
| Source | 7,077 | 7,718 | +641 ※要調査 |
| **Chunk** | **3,024** | **5,712** | **+2,688** ✓ |
| Claim | 4,596 | 5,075 | +479 |
| Topic | 1,380 | 2,066 | +686 |
| Author | (未測定) | 596 | (新規) |

`CONTAINS_CHUNK` リレーションも +2,688 で Chunk 増分と一致。

## 決定事項

| # | 決定 ID | 内容 |
|---|--------|------|
| 1 | `dec-2026-04-27-dedup-scraped-include-content-fields` | `dedup_scraped._to_finance_news_format` に content/category/tags/author の4フィールドを追加し、Mapper まで届くようにする |
| 2 | `dec-2026-04-27-backfill-via-processed-rescan` | 既投入分の Chunk/Author/Topic 補完は processed/{date}/ を再スキャン → registry bypass → emit→ingest 方式で行う（MERGE 冪等性で安全） |
| 3 | `dec-2026-04-27-neo4j-io-error-restart-recovery` | research DB が I/O error で stopping した場合の標準復旧手順は `docker restart neo4j-enterprise`（11秒で healthy、データ破損なし実績） |
| 4 | `dec-2026-04-27-act-002-superseded` | `act-2026-04-16-002`（scrape_finance_news に content 取得を追加）は誤った前提に基づくため superseded。実体は本日の `dec-2026-04-27-dedup-scraped-include-content-fields` で達成 |

## アクションアイテム

- [ ] `act-2026-04-27-001` (中) `.tmp/backfill_chunks.py` の `--queue-file` → `--file` 修正、または `scripts/replay_processed.py` として正式版に昇格（act-2026-04-16-004 と統合）
- [ ] `act-2026-04-27-002` (中) `pipeline-scraped-news` SKILL.md の verification クエリを `created_at` ベースから「投入前後のラベル件数差分」方式に書き換え（今回 0件と誤検出した根本対策）
- [ ] `act-2026-04-27-003` (高) `src/data_pipeline/neo4j_loader.py` に `--batch-size` を導入してトランザクションを数百コマンド単位に分割し、I/O エラー再発時の影響範囲を局所化
- [ ] `act-2026-04-27-004` (低) `act-2026-04-16-002` を `superseded` に更新（メモ反映済、Neo4j 側のステータス更新が残）
- [ ] `act-2026-04-27-005` (中) backfill 後の Source +641 の謎を調査（restart 中の他プロセス ingest？ MERGE キー揺れ？）
- [ ] `act-2026-04-27-006` (中) `FinanceNewsMapper.map()` および `dedup_scraped._to_finance_news_format` に対する unit test を追加して content/tags/author の脱落を恒久的に防ぐ（act-2026-04-16-003 を拡張）
- [ ] `act-2026-04-27-007` (中) ingest_graph_queue の Stage 4 サマリで「expected sources/chunks/authors/topics（queue file から読む）」と「actual created（DB から読む）」を突き合わせ、乖離があれば WARN を出す（act-2026-04-16-005 の具体化）

## 次回の議論トピック

- 別 PC のスクレイパーに送り込んでいる `scrape_finance_news.py` の取得対象拡張（USサイト中心 → 日経・東洋経済等の追加検討）
- Source +641 の調査結果次第で、MERGE キー（URL 正規化）に手を入れるべきかの判断
- `processed/` のレジストリ GC 戦略（年内 1万件突破見込み、`act-2026-04-16-004` 関連）

## 参考情報

- 4/16 議論メモ（誤った前提を含む）: `docs/plan/SideBusiness/2026-04-16_scraped-news-pipeline.md`
- 4/10 launchd 停止調査: `docs/plan/SideBusiness/2026-04-10_discussion-rss-scraping-stopped-investigation.md`
- 修正対象ファイル: `scripts/dedup_scraped.py:300-319` (`_to_finance_news_format`)
- backfill 一時スクリプト: `.tmp/backfill_chunks.py`（用途完了後に削除予定）
- 最終投入ログ: `.tmp/pipeline-runs/run-20260427085948.log`, `.tmp/pipeline-runs/backfill-ingest-retry-*.log`
- queue file（再利用可）: `.tmp/graph-queue/finance-news-workflow/gq-20260427020143-504d93ac.json`
