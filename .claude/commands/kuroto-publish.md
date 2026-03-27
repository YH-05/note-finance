# kuroto-publish: 下書き投稿

玄人領域アカウントの下書きをレビューし、Threads に投稿するコマンド。

## 引数

- 下書きパス（任意）: 特定の下書きディレクトリを指定。未指定なら未投稿の下書き一覧を表示

## 処理フロー

### Step 1: 下書き一覧表示

```
creator/kuroto_area/drafts/
```

配下の全ディレクトリを走査し、`meta.json` の `status` が `draft` のものを一覧表示:

```
未投稿の下書き:

week_2026-03-31:
  1. 月 S1 哲学     PH1 制御二分法（Epictetus）     380字  未投稿
  2. 月 S2 FW       FW1 習慣スタッキング             420字  未投稿
  3. 月 S3 海外     MT1 睡眠最適化（Huberman）       350字  未投稿
  4. 月 S4 内向型   IN1 社会的比較                   400字  未投稿
  5. 月 S5 書籍紹介 Atomic Habits                   350字  未投稿
  ...
```

### Step 2: ユーザー選択

AskUserQuestion で投稿する下書きを選択してもらう。
- 個別選択: 番号を指定
- 日単位: 「月曜分全部」のように日指定も可

### Step 3: プレビュー表示

選択された下書きの内容を表示:
- `post.md` の全文
- 文字数
- カテゴリ・型・テーマ・著者

ユーザーに「このまま投稿しますか？」と確認。

### Step 4: Threads 投稿

フロントマターから `topic_tag` を読み取り、`--topic-tag` に渡す:

```bash
uv run python -m src.creator.poster threads \
  --account kuroto_area \
  --text "<投稿文>" \
  --topic-tag "<topic_tag>"
```

`topic_tag` がない場合は `--topic-tag` を省略する。

投稿成功時の permalink を記録。

### Step 5: meta.json 更新

該当投稿の情報を更新:
```json
{
  "posted_at": "2026-03-31T07:30:00+09:00",
  "permalink": "https://www.threads.com/@kuroto_area/post/XXX"
}
```

全投稿が投稿済みなら week 全体の status を `published` に更新。

### Step 6: posting_state.json 更新

投稿履歴を `post_history` に追記:
```json
{
  "post_id": "2026-03-31_S1",
  "date": "2026-03-31",
  "day": "月",
  "slot": "S1",
  "category": "哲学",
  "type": "型1",
  "theme_id": "PH1",
  "concept": "制御二分法",
  "author": "Epictetus",
  "material_ids": [],
  "posted_at": "2026-03-31T07:30:00+09:00",
  "permalink": "https://www.threads.com/@kuroto_area/post/XXX"
}
```

### Step 7: 結果報告

- Threads 投稿 URL
- 「次の下書きを投稿しますか？」と確認

## 書籍紹介のAmazonリンク

書籍紹介投稿（型5）の場合、投稿後にコメント欄へリンクを追加:

```bash
# メイン投稿後、返信でAmazonリンクを投稿
uv run python -m src.creator.poster threads \
  --account kuroto_area \
  --text "参考文献: {書名} → {Amazon URL}" \
  --reply-to "<parent_post_id>"
```

## note記事の投稿

note記事は別フローで投稿する:

```bash
# note記事のMarkdownを生成後、article-publish スキルで投稿
/article-publish <path_to_note_article>
```

## 注意事項

- 投稿前に必ずユーザー確認を取る
- 投稿失敗時は meta.json に `failed` ステータスとエラー内容を記録
- note記事の投稿は `/article-publish` を使用
- **口調が「です・ます」調であることを投稿前に最終確認**
- 書籍紹介投稿ではコメント欄にAmazonリンクを追加（本文には入れない）
