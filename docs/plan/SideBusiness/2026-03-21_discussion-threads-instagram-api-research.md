# 議論メモ: Threads API & Instagram Graph API 技術調査

**日付**: 2026-03-21
**参加**: ユーザー + AI
**Neo4j Discussion ID**: disc-2026-03-21-threads-instagram-api-research
**前提議論**: disc-2026-03-21-instagram-expansion, disc-2026-03-21-threads-monetization-strategy

## 背景・コンテキスト

Threads×Instagram自動化マネタイズ戦略（3アカウント構成、転職からパイロット）の技術基盤調査。
act-2026-03-21-011（Threads API調査）とact-2026-03-21-015（Instagram Graph API調査）を並列実行。

## 調査結果サマリー

### 共通アーキテクチャ

両APIとも Meta Graph API ベースで、**Container → Publish の2ステップモデル**を採用。
認証は OAuth 2.0、Long-lived token（60日有効、リフレッシュ可能）で共通。

| 項目 | Threads | Instagram |
|------|---------|-----------|
| ステータス | GA | GA (v24.0) |
| ベースURL | `graph.threads.net/v1.0` | `graph.instagram.com/v24.0` |
| 投稿モデル | Container → Publish | Container → Publish |
| 認証 | OAuth 2.0 | OAuth 2.0 |
| Long-lived token | 60日、リフレッシュ可能 | 60日、リフレッシュ可能 |
| Facebook Page連携 | 不要 | 不要（Instagram Login方式） |
| App Review | 本番公開時に必要 | 自社アカウントのみなら不要 |
| 料金 | 無料 | 無料 |

## Threads API 詳細

### エンドポイント

| エンドポイント | メソッド | 用途 |
|---|---|---|
| `/{user-id}/threads` | POST | メディアコンテナ作成 |
| `/{user-id}/threads_publish` | POST | コンテナの公開（投稿） |
| `/{container-id}?fields=status` | GET | コンテナステータス確認 |
| `/{user-id}/threads_publishing_limit` | GET | レート制限使用状況確認 |

### 投稿フロー（2ステップ）

```
Step 1: POST /{user-id}/threads       → Container ID を取得
        (30秒待機を推奨。動画はステータスポーリング)
Step 2: POST /{user-id}/threads_publish → Container を公開
```

### メディアタイプ別パラメータ

| タイプ | media_type | 追加パラメータ |
|--------|-----------|--------------|
| テキスト | TEXT | text |
| 画像 | IMAGE | image_url, text |
| 動画 | VIDEO | video_url, text |
| カルーセル | CAROUSEL | children(カンマ区切り), text |

### カルーセル投稿（3ステップ）

```
Step 1: 各メディアの子コンテナ作成（is_carousel_item=true）
Step 2: カルーセル親コンテナ作成（media_type=CAROUSEL, children=id1,id2,...）
Step 3: 親コンテナを公開
```

### コンテンツ仕様

| 項目 | 制限 |
|---|---|
| テキスト文字数 | 500文字 |
| ハッシュタグ | 1投稿あたり1つまで |
| 画像フォーマット | JPEG, PNG |
| 画像サイズ上限 | 5MB(モバイル) / 15MB(Web) |
| 動画フォーマット | MP4, MOV (H.264 + AAC) |
| 動画長さ | 最大5分 |
| カルーセル最大数 | 20メディア |
| アスペクト比 | 1:1, 4:5, 16:9, 9:16 |

### Rate Limit

| 操作 | 制限 | 期間 |
|---|---|---|
| 投稿（Publish） | 250件 | 24時間ローリングウィンドウ |
| リプライ | 1,000件 | 24時間ローリングウィンドウ |
| 削除 | 100件 | 24時間ローリングウィンドウ |

- カルーセルは1投稿としてカウント
- リプライは投稿数制限にカウントされない
- 2025年にAPI全体のレート制限が5,000→200 calls/hourに引き下げられた事案あり

### リンクの扱い

テキスト本文にURLを直接含める方式。Threadsが自動でリンクプレビューを生成。
専用の `link` パラメータは存在しない。

### Container ステータス

| ステータス | 意味 |
|---|---|
| IN_PROGRESS | 処理中 |
| FINISHED | 公開可能 |
| PUBLISHED | 公開済み |
| ERROR | 処理失敗（error_message にエラーコード） |
| EXPIRED | 24時間以内に公開されず期限切れ |

### 認証スコープ

| スコープ | 用途 |
|---|---|
| threads_basic | 全エンドポイントに必須 |
| threads_content_publish | 投稿の作成・公開に必須 |
| threads_manage_replies | リプライへのPOSTに必要 |
| threads_read_replies | リプライのGETに必要 |
| threads_manage_insights | インサイトのGETに必要 |

### トークン管理

| 項目 | 値 |
|---|---|
| 短命トークン有効期限 | 1時間 |
| 長命トークン有効期限 | 60日（5,184,000秒） |
| リフレッシュ可能タイミング | 発行後24時間以上 かつ 60日以内 |
| リフレッシュ grant_type | th_refresh_token |

### Playwright代替 → 非推奨

公式APIが無料で提供。Playwright方式はアカウントBAN・利用規約違反・UI変更breakage・Instagram連座リスクがある。

## Instagram Graph API 詳細

### エンドポイント

| エンドポイント | メソッド | 用途 |
|---|---|---|
| `/{ig-user-id}/media` | POST | Container作成 |
| `/{ig-user-id}/media_publish` | POST | Container公開 |
| `/{container-id}?fields=status_code` | GET | ステータス確認 |
| `/{ig-user-id}/content_publishing_limit` | GET | レート制限確認 |

### 単一画像投稿（2ステップ）

```
Step 1: POST /{ig-user-id}/media
        → image_url, caption, access_token
        → Container ID を取得
Step 1.5: GET /{container-id}?fields=status_code
        → FINISHED になるまでポーリング
Step 2: POST /{ig-user-id}/media_publish
        → creation_id={container-id}
        → Media ID を取得
```

### カルーセル投稿（5ステップ）

```
Step 1: 各画像の Child Container 作成（is_carousel_item=true）
Step 2: 全 Child Container のステータスポーリング → FINISHED 確認
Step 3: Carousel Parent Container 作成（media_type=CAROUSEL, children=id1,id2,...）
Step 4: Parent Container のステータスポーリング → FINISHED 確認
Step 5: Publish（creation_id={carousel_container_id}）
```

**重要**: children パラメータはカンマ区切り文字列（JSON配列ではない）

### 画像要件

| 項目 | フィード投稿 | ストーリーズ |
|------|------------|------------|
| フォーマット | JPEG推奨 | JPG, PNG |
| 推奨サイズ | 1080x1350 (4:5) | 1080x1920 (9:16) |
| 最大ファイルサイズ | 8MB | 30MB |
| アスペクト比 | 4:5 〜 1.91:1 | 9:16 |

**カルーセル注意**: 最初の画像のアスペクト比に全スライドが合わせてクロップされる

### Rate Limit

| 制限対象 | 上限 | 備考 |
|---|---|---|
| 投稿（media_publish） | 100件/24h | ローリングウィンドウ。カルーセルは1件 |
| 一般APIコール | 200リクエスト/時間 | 2025年に5,000から引き下げ |
| Container有効期限 | 24時間 | 超過するとEXPIRED |

### キャプション仕様

| 項目 | 制限 |
|---|---|
| 最大文字数 | 2,200文字 |
| ハッシュタグ | 最大30個 |
| メンション | 最大20個 |
| 書式 | プレーンテキストのみ（マークダウン非対応） |

### ストーリーズ投稿

APIで投稿可能（v16.0以降）だが、**リンクスティッカーは非対応**。
キャプションも無視される。ASP導線としてのストーリーズリンクは手動運用が必要。

```
POST /{ig-user-id}/media
  ?image_url={画像URL}
  &media_type=STORIES
  &access_token={token}
```

### 認証スコープ（Instagram Login方式）

| スコープ | 用途 |
|---|---|
| instagram_business_basic | 基本的なプロフィール・メディア読み取り |
| instagram_business_content_publish | コンテンツ投稿 |

Facebook Page連携不要。App Review も自社アカウントのみなら不要。

### 画像ホスティング要件

image_url はPublic URLが必須。認証・CDN制限・期限付きURLは不可。
推奨: AWS S3, Google Cloud Storage, Cloudflare R2 等のオブジェクトストレージ。

## ASP導線への影響

| プラットフォーム | ASP導線方法 |
|----------------|------------|
| Threads | 投稿テキスト内に直接リンク or コメント欄にPRリンク |
| Instagram | プロフィールリンク（linktree等）+ キャプションで誘導。ストーリーズリンクは手動 |

## 実装上の重要発見

1. **Playwright は非推奨** — 両APIとも公式で無料提供。BANリスクが高い
2. **画像はPublic URL必須** — S3/GCS/R2等のオブジェクトストレージが必要
3. **Instagram ストーリーズのリンクスティッカーはAPI非対応** — ASP導線は手動運用
4. **カルーセル画像のアスペクト比統一必須** — 1枚目に全スライドが合わせられる（推奨: 1080x1350 / 4:5）
5. **トークン管理は共通化可能** — 両方60日/リフレッシュ構造が同じ。30-50日ごとのcron推奨
6. **API一般コール制限** — 200リクエスト/時間に注意（2025年に5,000から引き下げ）

## 決定事項

1. **dec-2026-03-21-api-over-playwright**: 両プラットフォームとも公式APIを使用。Playwright方式は採用しない
2. **dec-2026-03-21-image-hosting-required**: 画像ホスティング（S3/R2等）のセットアップが必要
3. **dec-2026-03-21-stories-link-manual**: Instagramストーリーズのリンクスティッカーは手動運用
4. **dec-2026-03-21-carousel-aspect-ratio**: カルーセル画像は全スライド1080x1350 (4:5) JPEG統一

---

## 他ユーザー投稿の読み取りAPI調査（2026-03-21 追記）

以下は、**他のユーザーの投稿を読み取る**際のAPI制限に特化した調査結果。
投稿（Publishing）側の調査は上記セクションを参照。

---

### Threads API: 他ユーザー投稿の読み取り

#### 1. 他ユーザーの投稿を取得するエンドポイント

**存在する。** 2つの公式エンドポイントが利用可能:

##### (a) 特定の公開プロフィールの投稿一覧取得

```
GET /profile_posts?username={target_username}
    &fields=id,media_product_type,media_type,permalink,owner,username,text,topic_tag,timestamp,shortcode,is_quote_post
    &access_token={token}
```

- **用途**: 指定ユーザー名の公開投稿をページネーション付きで取得
- **必要スコープ**: `threads_basic`
- **Advanced Access 承認後**: 任意の公開ユーザーの投稿を取得可能
- **Advanced Access 未承認時**: テスターが作成した投稿のみ取得可能

レスポンス例:
```json
{
  "data": [
    {
      "id": "1234567",
      "media_product_type": "THREADS",
      "media_type": "TEXT_POST",
      "permalink": "https://www.threads.net/@meta/post/...",
      "owner": { "id": "1234567" },
      "username": "meta",
      "text": "Today Is Monday",
      "topic_tag": "Mondays",
      "timestamp": "2023-10-09T23:18:27+0000",
      "shortcode": "abcdefg",
      "is_quote_post": false
    }
  ],
  "paging": {
    "cursors": {
      "before": "BEFORE_CURSOR",
      "after": "AFTER_CURSOR"
    }
  }
}
```

##### (b) 単一投稿の取得

```
GET /{threads-media-id}
    ?fields=id,media_product_type,media_type,permalink,owner,username,text,timestamp,shortcode,is_quote_post
    &access_token={token}
```

- Media IDがわかっていれば、他ユーザーの公開投稿を直接取得可能

#### 2. キーワード検索（Keyword Search API）

```
GET /keyword_search
    ?q={検索キーワード}
    &fields=id,media_product_type,media_type,text,username,timestamp,permalink
    &since={unix_timestamp}
    &until={unix_timestamp}
    &limit={1-100}
    &access_token={token}
```

**必要スコープ**: `threads_basic` + `threads_keyword_search`

**Rate Limit**:

| 制限項目 | 値 | 備考 |
|---------|-----|------|
| 検索クエリ数 | **2,200件/24時間** | ローリングウィンドウ |
| スコープ | ユーザー単位（アプリ横断） | 複数アプリから同一ユーザーで叩いても合算 |
| 結果なしのクエリ | カウントされない | 結果が0件の場合は制限にカウントされない |
| 1回あたり最大取得数 | 100件 | `limit` パラメータで指定（デフォルト25） |
| 期間指定 | `since`/`until`（Unix timestamp） | 範囲を絞って取得可能 |

**重要な制約**:
- App Reviewで `threads_keyword_search` の承認が必要。未承認だと自分の投稿のみ検索可能
- センシティブ/攻撃的と判断されたキーワードは空配列が返る
- **既知の不具合（2026-02時点）**: ページネーションの `afterCursor` が常に同じ値を返し、重複結果が大量発生する報告あり。10,000件のレスポンス中、ユニークが約300件のみというケースが報告されている
- `since`/`until` パラメータが正しく機能しないケースも報告されている

#### 3. トピックタグ検索

```
GET /keyword_search
    ?q={topic_tag_name}
    &search_type=TOPIC_TAG
    &access_token={token}
```

- キーワード検索と同一エンドポイント。`search_type=TOPIC_TAG` で切り替え
- Rate Limitもキーワード検索と共通（2,200件/24時間）

#### 4. Threads API 読み取り全体のRate Limit

```
24時間あたりの最大APIコール数 = 4800 * インプレッション数
```

- `threads_basic` スコープの一般的な読み取りコールはこの計算式に基づく
- アプリごと・ユーザーごとのペアで計算
- キーワード検索は独自の2,200件/24時間制限が別途適用

#### 5. 必要なスコープ・パーミッション一覧（読み取り用）

| スコープ | 読み取り用途 | App Review |
|---------|------------|------------|
| `threads_basic` | 全エンドポイント（自分 + 他ユーザー公開投稿） | Advanced Access 要承認 |
| `threads_keyword_search` | キーワード検索・トピックタグ検索 | 要承認 |
| `threads_read_replies` | リプライの読み取り | 要承認 |
| `threads_manage_insights` | インサイト（自分のアカウントのみ） | 要承認 |
| `threads_manage_mentions` | メンションの取得 | 要承認 |

---

### Instagram Graph API: 他ユーザー投稿の読み取り

#### 1. Business Discovery API

**他のビジネス/クリエイターアカウントの投稿・メタデータを取得する唯一の公式手段。**

```
GET /{your-ig-user-id}
    ?fields=business_discovery.username({target_username}){
        id,
        username,
        name,
        biography,
        website,
        followers_count,
        follows_count,
        media_count,
        profile_picture_url,
        media{
            id,
            caption,
            media_type,
            media_url,
            permalink,
            timestamp,
            like_count,
            comments_count,
            thumbnail_url
        }
    }
    &access_token={token}
```

レスポンス例:
```json
{
  "business_discovery": {
    "followers_count": 267793,
    "media_count": 1205,
    "media": {
      "data": [
        { "id": "17858843269216389" },
        { "id": "17894036119131554" }
      ]
    },
    "id": "17841401441775531"
  },
  "id": "17841405309211844"
}
```

**制限事項**:

| 項目 | 制限 |
|------|------|
| 対象アカウント | **ビジネス/クリエイターアカウントのみ**（個人アカウントは不可） |
| 年齢制限アカウント | データ返却されない |
| メディアへの直接アクセス | 不可（返された Media ID で直接 GET すると権限エラー） |
| Rate Limit | Instagram Platform Rate Limit に包含（後述） |
| 必要パーミッション | `instagram_basic` + `Instagram Public Content Access` feature |
| ストーリーズ | 取得不可（他アカウントのストーリーズは対象外） |
| リール | 取得可能（media_type = VIDEO として返却） |

**ネスト化リクエスト**: `fields` パラメータで `media` エッジを指定することで、プロフィール情報と投稿一覧を**1回のAPIコール**で取得可能。ページネーションで追加投稿を取得する場合は追加コールが必要。

#### 2. Hashtag Search API

公開投稿をハッシュタグで検索するエンドポイント群。

```
# Step 1: ハッシュタグのノードIDを取得
GET /ig_hashtag_search
    ?user_id={your-ig-user-id}
    &q={hashtag_name}
    &access_token={token}

# レスポンス: { "data": [{ "id": "17843857450040591" }] }
# (ハッシュタグIDは静的・グローバル。全アプリ・全ユーザーで共通)

# Step 2a: トップ投稿を取得
GET /{ig-hashtag-id}/top_media
    ?user_id={your-ig-user-id}
    &fields=id,caption,media_type,media_url,permalink,timestamp,like_count,comments_count
    &access_token={token}

# Step 2b: 最新投稿を取得
GET /{ig-hashtag-id}/recent_media
    ?user_id={your-ig-user-id}
    &fields=id,caption,media_type,media_url,permalink,timestamp
    &access_token={token}

# 検索済みハッシュタグの確認
GET /{your-ig-user-id}/recently_searched_hashtags
    &access_token={token}
```

**Rate Limit（ハッシュタグ検索特有）**:

| 制限項目 | 値 | 詳細 |
|---------|-----|------|
| ユニークハッシュタグ数 | **30個/7日間** | ローリングウィンドウ。1アカウントあたり |
| 同一ハッシュタグの再検索 | カウントされない | 7日間のタイマーリセットもされない |
| タイマーリセット | 初回検索から7日後 | ハッシュタグごとに独立 |
| コメント | 発見したメディアにコメント不可 | API制限 |
| ストーリーズ | 対象外 | ハッシュタグ付きストーリーズは検索不可 |
| 絵文字 | 非対応 | 絵文字を含むクエリはエラー |
| センシティブワード | 汎用エラー返却 | 不適切と判断されたハッシュタグ |

**必要パーミッション**: `instagram_basic` + `Instagram Public Content Access` feature（App Review 必須）

#### 3. Basic Display API 廃止後の代替手段

| 旧API | 廃止日 | 代替手段 | 制約 |
|--------|--------|---------|------|
| Instagram Basic Display API | **2024-12-04** | Instagram API with Instagram Login | Professional（Business/Creator）アカウントのみ |
| Legacy API（個人向け） | 2020年 | 完全廃止、代替なし | 個人アカウント向けの公式APIは2026年時点で存在しない |

**2026年の現実**:
- 個人アカウント（Consumer）向けのInstagram APIは完全に消滅
- 他ユーザーの投稿を公式APIで読み取るには、Business Discovery APIが唯一の手段
- ただしBusiness Discovery APIで取得できるのは **Business/Creator アカウントの公開投稿のみ**
- 個人アカウントの投稿は公式APIでは一切取得不可

#### 4. Instagram Platform Rate Limit（読み取り含む全般）

```
24時間あたりのAPIコール数 = 4800 * インプレッション数
```

| 制限項目 | 値 | 備考 |
|---------|-----|------|
| 計算式 | `4800 * Number of Impressions` | インプレッション = 24時間以内にそのアカウントのコンテンツが画面に表示された回数 |
| 適用範囲 | アプリ + ユーザーのペアごと | Business Discovery / Hashtag Search 含む |
| 最低保証 | 明記なし | 小規模アカウントはインプレッションが少ないため実質的に制限が厳しい |
| メッセージング | 別枠（200 DM/時間） | Platform Rate Limit とは別カウント |
| 失敗リクエスト | カウントされる | 無効リクエスト・エラーレスポンスも消費 |

**実用的な見積もり**:
- インプレッション数 1,000/日 のアカウント: 4,800,000 コール/24時間（十分な余裕）
- インプレッション数 100/日 の小規模アカウント: 480,000 コール/24時間（まだ余裕）
- 実質的なボトルネックはインプレッション計算よりも**ハッシュタグ30個/週**の方が厳しい

#### 5. ページネーション時のAPIコール消費

- Business Discovery API: `media` エッジのページネーションは**カーソルベース**。次ページ取得のたびに1 APIコール消費
- Hashtag Search API: `top_media`/`recent_media` もカーソルベースのページネーション。各ページ取得で1コール消費
- **最適化**: `fields` パラメータで必要なフィールドのみ指定することで、レスポンスサイズ削減とレイテンシ改善（APIコール数自体は変わらない）

---

### 共通: スクレイピング vs API のトレードオフ

#### スクレイピング（Playwright等）のリスク

| リスク項目 | 深刻度 | 詳細 |
|-----------|--------|------|
| アカウントBAN | **高** | Instagram は 2025年に12億アカウントをBANした実績。自動化検出が精緻化 |
| ToS違反 | **中** | Meta ToSは明示的にスクレイピング禁止。ただし Meta v. Bright Data (2024) 判例では、ログアウト状態での公開データ収集はToS適用外と判断 |
| 法的リスク | **中** | ToS違反 = 民事契約紛争（刑事ではない）。ただしGDPR/個人情報保護法に抵触する可能性 |
| 検出技術の進化 | **高** | WebGL fingerprint, TLSハンドシェイク, スクロール挙動, タイピング遅延まで分析される |
| 保守コスト | **高** | UI変更でbreakage頻発。Meta は年数回UIを変更する |
| Instagram連座リスク | **高** | Threads/Instagram共通アカウントのため、一方でBANされると他方も影響 |
| CAPTCHA/JS チャレンジ | **高** | 突破はほぼ全法域で違法と解釈されるリスク |

#### API制限のトレードオフ

| 制限項目 | 影響 | 回避策 |
|---------|------|--------|
| Threads keyword_search 2,200件/日 | 1日約2,200回検索可能。十分 | 効率的なクエリ設計 |
| Instagram ハッシュタグ 30個/週 | **最も厳しい制限**。競合分析の幅が限定される | 重要ハッシュタグに絞る。複数アカウント（非推奨） |
| Instagram Business Discovery | Business/Creatorアカウントのみ | 競合が個人アカウントの場合は取得不可 |
| App Review | 承認に5営業日以上 | 早めに申請。スクリーンキャスト動画が必要 |

#### 結論: API優先 + 限定的サードパーティ利用

| ユースケース | 推奨手段 | 理由 |
|------------|---------|------|
| 競合のThreads投稿監視 | **Threads 公式API** (`profile_posts`) | 無制限に近い取得が可能 |
| Threads トレンド調査 | **Threads 公式API** (keyword_search) | 2,200件/日は十分。トピックタグ検索も利用可 |
| 競合のInstagram投稿分析 | **Business Discovery API** | Business/Creatorアカウントなら取得可能 |
| Instagram ハッシュタグトレンド | **Hashtag Search API** | 30ハッシュタグ/週の制限内で運用 |
| 個人アカウントの投稿取得 | **サードパーティAPI** (SociaVault等) or 断念 | 公式APIでは不可能 |
| 大規模クロール | **サードパーティAPI** | 公式APIのRate Limitでは非現実的な規模の場合 |

---

### 競合分析・トレンド調査の現実的な取得件数見積もり

#### Threads（公式API利用）

| 操作 | 1日あたり | 1週間あたり | 備考 |
|------|----------|------------|------|
| 競合プロフィール投稿取得 | 事実上無制限 | 事実上無制限 | `profile_posts` はPlatform Rate Limitのみ |
| キーワード検索 | 2,200クエリ | 15,400クエリ | 1クエリで最大100件取得可能 |
| キーワード検索で取得可能な投稿数 | 最大220,000件 | 最大1,540,000件 | 2,200クエリ x 100件/クエリ |
| 実用的なユニーク投稿数 | **推定660件/日** | **推定4,620件/週** | 重複問題を考慮（ユニーク率約30%の報告） |

#### Instagram（公式API利用）

| 操作 | 1日あたり | 1週間あたり | 備考 |
|------|----------|------------|------|
| Business Discovery（競合分析） | 約200アカウント | 約1,400アカウント | 1アカウント=1 APIコール（投稿含む） |
| ハッシュタグ検索（ユニーク数） | - | **最大30ハッシュタグ** | 週単位の制限 |
| 同一ハッシュタグのポーリング | 制限なし（Rate Limit内） | 制限なし | 一度検索したハッシュタグの再取得はカウント外 |
| ハッシュタグあたりの投稿数 | 数百件 | 数百件 | top_media + recent_media のページネーション |

---

## アクションアイテム

### 投稿（Publishing）関連
- [ ] **act-2026-03-21-020** Meta Developer App 作成（Threads + Instagram 両方のUse Case設定）(優先度: 高)
- [ ] **act-2026-03-21-021** OAuth フロー実装 + Long-lived token取得・自動リフレッシュ (優先度: 高)
- [ ] **act-2026-03-21-022** 画像ホスティング選定・セットアップ（Cloudflare R2推奨：無料枠あり） (優先度: 高)
- [ ] **act-2026-03-21-023** Threads投稿モジュール実装（text/image/carousel） (優先度: 高)
- [ ] **act-2026-03-21-024** Instagramカルーセル投稿モジュール実装 (優先度: 高)
- [ ] **act-2026-03-21-025** レート制限モニタリング + 投稿スケジューラー設計 (優先度: 中)

### 読み取り（Reading）関連
- [ ] **act-2026-03-21-030** App Review 申請: `threads_keyword_search` スコープ承認取得 (優先度: 高)
- [ ] **act-2026-03-21-031** App Review 申請: `Instagram Public Content Access` feature 承認取得 (優先度: 高)
- [ ] **act-2026-03-21-032** Threads 競合投稿取得モジュール実装 (`profile_posts` endpoint) (優先度: 中)
- [ ] **act-2026-03-21-033** Threads キーワード検索モジュール実装（重複排除ロジック含む） (優先度: 中)
- [ ] **act-2026-03-21-034** Instagram Business Discovery モジュール実装（競合分析用） (優先度: 中)
- [ ] **act-2026-03-21-035** Instagram Hashtag Search モジュール実装（30ハッシュタグ/週の管理ロジック含む） (優先度: 中)

## 参考情報

### Threads API
- [Threads API - Meta for Developers](https://developers.facebook.com/docs/threads/)
- [Publishing Reference](https://developers.facebook.com/docs/threads/reference/publishing/)
- [Threads Posting API (Postproxy, 2026-03-10)](https://postproxy.dev/blog/how-to-post-to-threads-via-api/)
- [Retrieve and Discover Posts](https://developers.facebook.com/docs/threads/retrieve-and-discover-posts/retrieve-posts/)
- [Keyword and Topic Tag Search](https://developers.facebook.com/docs/threads/keyword-search/)
- [Threads API Overview (Rate Limiting)](https://developers.facebook.com/docs/threads/overview/)

### Instagram Graph API
- [Content Publishing](https://developers.facebook.com/docs/instagram-platform/content-publishing/)
- [Instagram Platform Overview](https://developers.facebook.com/docs/instagram-platform/overview/)
- [Stories Publishing (2023-05)](https://developers.facebook.com/blog/post/2023/05/16/introducing-stories-publishing-to-the-content-publishing-api-on-instagram/)
- [Elfsight: Instagram Graph API Guide 2026](https://elfsight.com/blog/instagram-graph-api-complete-developer-guide-for-2026/)
- [Business Discovery API](https://developers.facebook.com/docs/instagram-platform/instagram-api-with-facebook-login/business-discovery/)
- [Hashtag Search API](https://developers.facebook.com/docs/instagram-platform/instagram-api-with-facebook-login/hashtag-search/)
- [Graph API Rate Limiting](https://developers.facebook.com/docs/graph-api/overview/rate-limiting/)
- [Basic Display API 廃止通知 (2024-09)](https://developers.facebook.com/blog/post/2024/09/04/update-on-instagram-basic-display-api/)

### 法的リスク参考
- [Meta v. Bright Data (2024)](https://aimultiple.com/is-web-scraping-legal) - ログアウト状態での公開データ収集はToS適用外
- [Instagram ToS](https://help.instagram.com/termsofuse) - 自動データ収集を明示的に禁止
- [2026年のスクレイピング法的リスク](https://itlawco.com/web-scraping-legal-risk-2025/) - 法域別リスク分析
