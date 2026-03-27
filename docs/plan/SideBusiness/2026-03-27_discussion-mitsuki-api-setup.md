# 議論メモ: みつきアカウント投稿インフラ整備

**日付**: 2026-03-27
**参加**: ユーザー + AI

## 背景・コンテキスト

みつき（@mitsuki_fortune）アカウントのMeta API設定が完了し、Threads投稿インフラを整備した。
前セッションでcareer_sisterとmitsukiを間違えて投稿したインシデントを受け、アカウント安全機構を強化した。
あわせてThreads APIのtopic_tag仕様を調査し、英字大文字から日本語への変更を決定・実施した。

## 議論のサマリー

### マルチアカウント対応（完了）

- `poster.py` に `THREADS_ACCOUNT_ENV` dict を追加
- `ThreadsConfig.for_account()` classmethod で環境変数を切り替え
- CLI に `--account` 引数を追加（`career_sister` / `mitsuki`）
- 投稿前に `get_account_info()` でアカウント確認表示: `Posting as: @username (id=...)`

### topic_tag 仕様調査と修正（完了）

- Meta公式ドキュメント（developers.facebook.com/docs/threads/posts）を調査
- **topic_tag は自由文字列**（1〜50字、ピリオドとアンパサンド不可）であることが判明
- 以前使用していた `ASTROLOGY_METAPHYSICS` 等は任意文字列として受け入れられるが、Threads UIとの対応は不明
- 日本語で直接指定する方針に変更
- `poster.py` にバリデーション追加（50文字超・禁止文字でエラー）

### week_2026-03-31 ドラフト確認

- 35本のThreads投稿ドラフトが全て未投稿状態（3/31〜4/6）
- フロントマターに `topic_tag` フィールドなし → 次回 `/mitsuki-draft` で生成分から日本語topic_tagが付く

## 決定事項

1. **topic_tag は日本語自由文字列**: カテゴリ別デフォルトを下記に設定
   - タロット → `タロット占い`
   - 星座 → `星座占い`
   - Tips / ENG / note誘導 / Story → `自己理解`

2. **マルチアカウント対応**: `THREADS_ACCOUNT_ENV` + `for_account()` + `get_account_info()` の3点セットで誤投稿を防止

## 変更ファイル

| ファイル | 変更内容 |
|---------|---------|
| `src/creator/poster.py` | topic_tagバリデーション（1-50字・禁止文字チェック）・警告メッセージ更新 |
| `.claude/commands/mitsuki-draft.md` | topic_tagデフォルト値を日本語化、自由文字列説明追記 |

## アクションアイテム

- [ ] テスト投稿2件を削除: @career_sister/post/DWYMpClEg3w と @mitsuki_fortune/post/DWYMnKdkneC (優先度: 高)
- [ ] persona.mdの自己紹介テンプレートを使ってThreads @mitsuki_fortuneに初回投稿 (優先度: 高)
- [ ] note アカウントの表示名・Bio設定（persona.md note プロフィールセクション参照）(優先度: 高)
- [ ] week_2026-03-31 ドラフト（35本）をレビューして投稿準備（3/31から） (優先度: 高)

## 次回の議論トピック

- 自己紹介投稿後のフォロワー反応に応じたコンテンツ方針微調整
- topic_tagの実際の表示確認（投稿後にThreads UIで確認）
- `/mitsuki-publish` でのスロット別スケジュール投稿フロー確立

## 参考情報

- Threads API topic_tag 仕様: 1〜50文字、ピリオド（.）とアンパサンド（&）不可、日本語使用可
- 出典: developers.facebook.com/docs/threads/posts
