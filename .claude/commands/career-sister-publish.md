# career-sister-publish: 下書き投稿

career_sister アカウントの下書きをレビューし、Threads + Instagram に投稿するコマンド。

## 引数

- 下書きパス（任意）: 特定の下書きディレクトリを指定。未指定なら未投稿の下書き一覧を表示

## 処理フロー

### Step 1: 下書き一覧表示

```
creator/career_sister/drafts/
```

配下の全ディレクトリを走査し、`meta.json` の `status` が `draft` のものを一覧表示:

```
未投稿の下書き:
1. 2026-03-23_001 - 「職務経歴書のプロセス翻訳」(有益/型1) 350字 6スライド
2. 2026-03-23_002 - 「30代転職は遅くない」(有益/型4) 420字 5スライド
```

### Step 2: ユーザー選択

AskUserQuestion で投稿する下書きを選択してもらう。

### Step 3: プレビュー表示

選択された下書きの内容を表示:
- `threads_post.md` の全文
- `instagram_caption.md` の全文
- カルーセル画像の枚数

ユーザーに「このまま投稿しますか？」と確認。

### Step 4: Threads 投稿

```bash
uv run python -m src.creator.poster threads --text "<投稿文>"
```

投稿成功時の permalink を記録。

### Step 5: Instagram カルーセル投稿

1. カルーセル画像を R2 にアップロード:
```bash
# 各スライドをR2にアップロード
uv run python -m src.creator.image_hosting upload <carousel/slide_01.png>
uv run python -m src.creator.image_hosting upload <carousel/slide_02.png>
...
```

2. Instagram カルーセル投稿:
```bash
uv run python -m src.creator.poster instagram-carousel \
  --text "<キャプション>" \
  --image-urls "<url1>,<url2>,..."
```

**注意**: poster.py に `instagram-carousel` サブコマンドがない場合は、
Instagram Graph API の Container → Carousel Container → Publish フローを
直接実行するか、poster.py を拡張する。

### Step 6: meta.json 更新

```json
{
  "status": "published",
  "published_at": "2026-03-23T16:00:00+09:00",
  "threads_permalink": "https://www.threads.com/@career_sister/post/XXX",
  "instagram_permalink": "https://www.instagram.com/p/XXX/"
}
```

### Step 7: 結果報告

- Threads 投稿 URL
- Instagram 投稿 URL
- 「次の下書きを投稿しますか？」と確認

## Instagram カルーセル投稿の技術詳細

Instagram Graph API でのカルーセル投稿手順:

1. 各画像の Container を作成:
```
POST /{ig-user-id}/media
  image_url=<公開URL>
  is_carousel_item=true
```

2. Carousel Container を作成:
```
POST /{ig-user-id}/media
  media_type=CAROUSEL
  children=<container_id1>,<container_id2>,...
  caption=<キャプション>
```

3. 公開:
```
POST /{ig-user-id}/media_publish
  creation_id=<carousel_container_id>
```

poster.py にこのフローが未実装の場合は、このコマンド内で直接 API を呼ぶか、
poster.py を拡張してから実行する。

## 注意事項

- 投稿前に必ずユーザー確認を取る
- R2 アップロードには .env の R2 認証情報が必要
- Instagram カルーセルは最大10枚まで
- 投稿失敗時は meta.json の status を `failed` に更新し、エラー内容を記録
