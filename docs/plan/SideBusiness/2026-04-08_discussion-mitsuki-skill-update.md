# 議論メモ: みつきスキル更新・環境設定・メンバーシップ生成ロジック実装

**日付**: 2026-04-08
**参加**: ユーザー + AI

## 背景・コンテキスト

前回までの議論でみつきのペルソナが「ギャル×世話好きおばちゃん」に全面改訂され、
`creator/mitsuki/persona.md` と `membership_design.md` が最新状態になっていた。
一方でスキルファイル群（mitsuki-writer/threads/note）はまだ旧トーン（温かい語りかけ型）のままで、
実際の投稿生成時にペルソナとスキルに乖離が生じる状態だった。

また auto_poster.py に `NOTE_HEADLESS: "true"` がハードコードされており、
launchd 自動化時に `NOTE_SESSION_PATH` や `NOTE_HEADLESS=false` を環境変数で渡せない問題があった。

## 実施内容（アクションアイテム完了）

### 013 + 007: スキル更新

**mitsuki-writer/SKILL.md**:
- ペルソナ定義を「ギャル×世話好きおばちゃん」に更新
- 声—口調ルールをギャル×おばちゃん（ですます調カジュアル・絵文字多用）に全面改訂
- 体験談テンプレート3パターン（自身の体験/友達事例/DM架空）を追加
- 投稿の型を4パターン→5パターンに拡張（体験談ベース）
- NG リストに学者名（ボウルビィ等）・英語理論名・「エビデンスによると」を追加
- カテゴリ比率を persona.md の設計（恋愛悩み35%/愛着スタイル25%/タロット×恋愛20%等）に更新

**mitsuki-threads/SKILL.md**:
- ポジション「自己理解ガイド」→「愛着スタイル×占いで恋愛を読み解くお姉さん兼おばちゃん」
- ターゲット「Z世代・自分がよくわからない人」→「交際中・関係性の悩みを抱える20-30代女性」
- 声—口調ルールをギャル×おばちゃんに切り替え（絵文字5-10個/投稿）
- 投稿の型を5パターンに更新（体験談フック中心）
- カテゴリ比率・topic_tag を persona.md と整合

**mitsuki-note/SKILL.md**:
- ポジション・ターゲット更新
- 口調ルールをギャル×おばちゃん（note版は絵文字控えめのですます調）に調整
- 学者名・英語理論名禁止を明記
- description に「メンバーシップ記事」を追加

### 002: auto_poster.py の NOTE_HEADLESS ハードコード修正

`scripts/auto_poster.py` 1706行目:
```python
# 変更前
env={**__import__("os").environ, "NOTE_HEADLESS": "true"},

# 変更後
env=os.environ.copy(),
```

launchd plist で `NOTE_HEADLESS=false` や `NOTE_SESSION_PATH=/path/to/session.json` を
設定すれば、そのまま `publish_to_note.py` のサブプロセスに渡るようになった。
`scripts/note_publisher/config.py` はすでに両 env var を読む設計になっているため、
上流で上書きしないことが正解。

### 003: mitsuki-draft コマンドにメンバーシップ記事生成ロジック追加

`.claude/commands/mitsuki-draft.md` に「メンバーシップ限定記事の生成ロジック」セクションを追加:

- **週次固定スケジュール（週3本）**: 月タロット深掘り / 水Tips深掘り / 金星座リーディング
- **月次特別版の差し替えロジック**（Python コードで明示）:
  - 第1金曜: 星座→月間テーマ（強めCTA）
  - 第2水曜: Tips→セルフケアワークシート（強めCTA）
  - 第3月曜: タロット→みつきの本音コラム（CTAなし）
  - 第4水曜: Tips→月間振り返り&来月プレビュー（CTAなし）
- `membership_enabled: true` フラグで制御（未開設時はロジック不発動）
- ディレクトリ構造・meta.json 記録形式を定義
- NGワードリストにボウルビィ等の学者名を追加

## 決定事項

1. mitsuki-writer / mitsuki-threads / mitsuki-note スキルはギャル×おばちゃん文体・体験談テンプレートを標準とする
2. auto_poster.py は `os.environ.copy()` で env 継承。NOTE_HEADLESS のデフォルト制御は note_publisher/config.py に委ねる
3. mitsuki-draft コマンドは `membership_enabled` フラグで週次+メンバーシップ記事を生成する設計

## 完了アクションアイテム

- [x] `act-2026-04-07-013`: mitsuki-writer/threads/note スキルをギャル×おばちゃん文体・体験談テンプレートで更新
- [x] `act-2026-04-07-007`: mitsuki-threads/mitsuki-note スキルを恋愛×愛着スタイル軸に更新
- [x] `act-2026-03-28-002`: auto_poster.py に NOTE_HEADLESS=false と NOTE_SESSION_PATH を反映
- [x] `act-2026-04-06-funnel-003`: mitsuki-draft スキルにメンバーシップ限定記事の生成ロジックを追加

## 残存アクションアイテム（pending）

- `act-2026-04-07-014` [high]: `/mitsuki-draft` で新戦略（恋愛×愛着スタイル・ギャル×おばちゃん文体）の1週間分ドラフトを生成
- `act-2026-04-07-010` [high]: みつきDタイプ商品の具体設計（収益化/占術/ブランディング）議論
- `act-2026-04-02-mitsuki-membership-launch` [high]: note_count=10 到達後にメンバーシップ開設
- `act-2026-04-02-mitsuki-analysis-to-creator-neo4j` [中]: 20クリエイター分析データを creator-neo4j に投入
- `act-2026-04-02-mitsuki-competitor-posting-analysis` [中]: 成功クリエイター投稿戦略の深掘り分析

## 次回の議論トピック

- Dタイプ商品の具体設計（act-2026-04-07-010）
- `/mitsuki-draft` 実行 → 新文体でのドラフト生成 → レビュー
- posting_state.json に `membership_enabled` フィールドを追加するタイミング
