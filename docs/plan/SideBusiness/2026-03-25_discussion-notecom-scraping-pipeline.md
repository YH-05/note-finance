# 議論メモ: note.comスクレイピング→RawStore→Neo4j統合パイプライン設計

**日付**: 2026-03-25
**参加**: ユーザー + AI

## 背景・コンテキスト

creator-neo4j と research-neo4j への投入パイプラインにおいて、note.com からスクレイピングしたテキストを一旦保存し、投入先を選んで Neo4j に保存する仕組みが必要になった。

### 現状の課題
- data_pipeline（Pythonバッチ）と creator-enrichment（スキル）の2系統が独立しており、RawStore を共有していない
- note.com 専用コレクターが未実装（trafilatura は動作するが有料判定・ページネーションに非対応）
- 収集と投入が一体化しており「一旦保存→後から投入先を選択」ができない
- note.com がソースレジストリに未登録

## 議論のサマリー

### 設計判断の流れ
1. **取得方式**: 非公式API vs trafilatura vs Playwright → **Playwright Python** を選択（非公式API不使用）
2. **ルーティング**: 一体型 vs 分離型 → **収集と投入の2ステップ分離**を選択
3. **既存スキルとの関係**: 並行維持 vs 統合 → **creator-enrichment を RawStore 経由に改修**
4. **記事一覧取得**: API+Playwright vs Playwright only → **全て Playwright で完結**（非公式API不使用）
5. **RSSモニタリング**: 対象クリエイターを JSON config で管理、一括スクレイピング後に追加を質問

## note.com 構造調査結果

### クリエイターページ (`https://note.com/{username}`)
- プロフィール（名前、自己紹介、フォロワー数、SNSリンク）
- メンバーシップ（あれば）
- マガジン（あれば）
- 記事一覧
  - 並び順切替: "新着" | "人気"
  - 記事カード: サムネイル、h3タイトル、`a[href="/n/nXXX"]`、`time`（相対日時）、スキ数
  - 「もっとみる」ボタンで追加読み込み（無限スクロールではない）
  - **重要: 記事一覧では有料/無料が区別できない**

### 記事ページ (`https://note.com/{username}/n/{note_key}`)
- `article` 要素内に全コンテンツ
- 本文: `.note-common-styles__textnote-body` 内の `p` 要素群
- メタデータ: JSON-LD (`BlogPosting`) に headline, datePublished, author, description
- OGP: og:title, og:description, og:image, og:url
- ハッシュタグ: `a[href="/hashtag/XXX"]`

### 有料/無料判定（記事ページでのみ可能）

| 判定要素 | 無料記事 | 有料記事 |
|---|---|---|
| `button "¥XXX〜"` | なし | あり（ヘッダー付近） |
| `"購入手続きへ"` ボタン | なし | あり |
| `"ここから先は"` セクション | なし | あり（ペイウォール境界） |
| `.note-common-styles__textnote-body` | 全文あり | 途中まで |
| `"チップで応援する"` ボタン | あり | なし |

### RSS (`/{username}/rss`)
- RSS 2.0 + note独自名前空間
- 本文なし（概要200-400字のみ）
- `note:creatorName`, `media:thumbnail` 等の拡張フィールド

## 決定事項

### 1. Playwright Python で note.com 専用コレクター新規作成
- 非公式API不使用、全てPlaywrightのDOM操作
- 記事一覧: 「もっとみる」ボタン繰り返しクリックで全記事URL取得
- 有料判定: 各記事ページに遷移し `button "¥XXX"` / `"購入手続きへ"` の有無で判定
- 本文抽出: `.note-common-styles__textnote-body` から `p` テキスト抽出
- メタデータ: JSON-LD から datePublished, author 取得

### 2. 収集と投入の2ステップ分離
- `collect` コマンド: note.com → RawStore 保存（Neo4j投入なし）
- `ingest` コマンド: RawStore → `--target research|creator` で投入先選択 → Neo4j

### 3. creator-enrichment を RawStore 経由に改修
- Phase 2 で取得したテキストを `RawStore.save_text()` でも保存
- 既存フローは壊さず、RawStore 保存をアドオン

### 4. RSSモニタリング + config管理
- `data/config/note-com-creators.json` で対象クリエイター管理
- RSS新着検知 → Playwright本文取得 → RawStore保存
- 一括スクレイピング後に「RSSモニターに追加するか？」を質問

### 5. 非公式API不使用
- `/api/v2/`, `/api/v3/` は変更リスクのため使用しない

## 統合後アーキテクチャ

```
===== 収集レイヤー (collect) =====

  RssCollector ──────┐
  ScrapingCollector ──┤→ RawStore (/Volumes/personal_folder/raw_texts/)
  NoteComCollector ──┘   └── {source_id}/{YYYY-MM-DD}/{hash}.json
  (Playwright新規)
                              ↑
  creator-enrichment ─────────┘ (RawStoreにも保存するよう改修)

===== 投入レイヤー (ingest) =====

  RawStore → --target research → LLM抽出 → emit_research_queue → research-neo4j (7688)
         └→ --target creator  → LLM抽出 → emit_creator_queue   → creator-neo4j (7689)
```

### CLI コマンド設計

```bash
# 一括スクレイピング
uv run python -m data_pipeline note-com scrape {username}

# RSSモニタリング
uv run python -m data_pipeline note-com monitor

# クリエイター管理
uv run python -m data_pipeline note-com add {username}
uv run python -m data_pipeline note-com list
uv run python -m data_pipeline note-com remove {username}

# RawStore → Neo4j 投入
uv run python -m data_pipeline ingest --source note-com-{username} --target creator|research
```

## アクションアイテム

- [ ] NoteComCollector 新規作成 (`src/data_pipeline/collectors/note_com.py`) (優先度: 高)
- [ ] RSSモニタリング機能実装 + `note-com-creators.json` 作成 (優先度: 高)
- [ ] CLI `ingest` サブコマンド追加 (優先度: 高)
- [ ] creator-enrichment RawStore 統合 (優先度: 中)
- [ ] `note-com-creators.json` + クリエイター管理CLI (優先度: 中)

## 実装フェーズ

| Phase | 内容 | 依存 |
|---|---|---|
| 1a | NoteComCollector: Playwright記事一覧取得+有料判定+本文抽出 | なし |
| 1b | NoteComCollector: RawStore保存連携 | 1a |
| 1c | note-com-creators.json + クリエイター管理CLI | なし |
| 2 | CLI note-com scrape/monitor + RSSモニター追加フロー | 1a-c |
| 3 | CLI ingest サブコマンド（RawStore → Neo4j） | なし |
| 4 | creator-enrichment RawStore統合 | 3 |

## 次回の議論トピック

- NoteComCollector の実装詳細（エラーハンドリング、リトライ戦略）
- note.com の robots.txt 準拠チェック
- RSSモニタリングの cron スケジュール設計
- ソースレジストリへの note.com ソース定義追加

## 参考情報

- note.com はNext.jsではなくNuxt.js SSRで、本文がHTMLに含まれる
- trafilatura でも本文取得可能だが、有料判定・ページネーション対応にはPlaywrightが必要
- RawStore デフォルト保存先: `/Volumes/personal_folder/raw_texts/`
- 既存パイプライン: `src/data_pipeline/pipeline.py` の `run_pipeline(target=research|creator)`
