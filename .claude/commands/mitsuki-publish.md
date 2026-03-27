# mitsuki-publish: 下書き投稿

みつき（美月）アカウントの下書きをレビューし、Threads に投稿するコマンド。

## 引数

- 下書きパス（任意）: 特定の下書きディレクトリを指定。未指定なら未投稿の下書き一覧を表示

## 処理フロー

### Step 1: 下書き一覧表示

```
creator/mitsuki/drafts/
```

配下の全ディレクトリを走査し、`meta.json` の `status` が `draft` のものを一覧表示:

```
未投稿の下書き:

week_2026-03-31:
  1. 月 タロット   塔（認知的再評価）       380字  未投稿
  2. 水 自己理解   Eurich式自己認識         420字  未投稿
  3. 金 星座      天秤座（均衡欲求）        350字  未投稿
  4. 日 ENG       問いかけ                 250字  未投稿
```

### Step 2: ユーザー選択

AskUserQuestion で投稿する下書きを選択してもらう。

### Step 3: プレビュー表示

選択された下書きの内容を表示:
- `post.md` の全文
- 文字数
- カテゴリ・型・テーマ

ユーザーに「このまま投稿しますか？」と確認。

### Step 4: Threads 投稿

フロントマターから `topic_tag` を読み取り、`--topic-tag` に渡す:

```bash
uv run python -m src.creator.poster threads \
  --account mitsuki \
  --text "<投稿文>" \
  --topic-tag "<topic_tag>"
```

`topic_tag` がない場合は `--topic-tag` を省略する。

投稿成功時の permalink を記録。

### Step 5: meta.json 更新

該当投稿の情報を更新:
```json
{
  "posted_at": "2026-03-31T20:00:00+09:00",
  "permalink": "https://www.threads.com/@mitsuki_jibunguide/post/XXX"
}
```

全投稿が投稿済みなら week 全体の status を `published` に更新。

### Step 6: posting_state.json 更新

投稿履歴を `post_history` に追記:
```json
{
  "post_id": "2026-03-31_001",
  "date": "2026-03-31",
  "day": "月",
  "category": "タロット",
  "type": "型1-A",
  "tarot_card": "塔",
  "material_ids": [],
  "posted_at": "2026-03-31T11:00:00+00:00",
  "permalink": "https://www.threads.com/@mitsuki_jibunguide/post/XXX"
}
```

### Step 7: 結果報告

- Threads 投稿 URL
- 「次の下書きを投稿しますか？」と確認

## note有料記事の投稿

数秘術鑑定書・ガイドブックの note 投稿は別フローで行う:

```bash
# note記事のMarkdownを生成後、publish-to-note スキルで投稿
/article-publish <path_to_numerology_article>
```

## 注意事項

- 投稿前に必ずユーザー確認を取る
- 投稿失敗時は meta.json に `failed` ステータスとエラー内容を記録
- note有料記事の投稿は `/article-publish` を使用
