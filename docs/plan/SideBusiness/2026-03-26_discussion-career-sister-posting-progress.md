# 議論メモ: career_sister 週次投稿進捗 (week_2026-03-24)

**日付**: 2026-03-26
**参加**: ユーザー + AI

## 背景・コンテキスト

career_sister アカウントの週次投稿スケジュール (week_2026-03-24, 3/24〜3/30) の実行フロー。
3スロット/日 × 7日 = 21 Threads投稿 + 7 Instagram カルーセルが含まれる。

## 本セッションでの実施内容

### 投稿済みスロット (本セッション前)

| 日 | スロット | 状態 | Threads URL |
|---|------|------|-------------|
| 月 3/24 朝 | 有益/型2 | 投稿済 | https://www.threads.com/@career_sister/post/DWQF-5xE0fO |
| 月 3/24 昼 | エンゲージメント/型1-A | 投稿済 | https://www.threads.com/@career_sister/post/DWQKMqbE5mQ |
| 月 3/24 夜 | 有益/型4 + IG | 投稿済 | https://www.threads.com/@career_sister/post/DWQKTz4k3Ba |
| 火 3/25 朝 | 有益/型3 | 投稿済 | https://www.threads.com/@career_sister/post/DWSc53gE4SN |
| 火 3/25 昼 | 有益/型1 | 投稿済 | https://www.threads.com/@career_sister/post/DWSs_r7E5kC |
| 火 3/25 夜 | 有益/型2 + IG | 投稿済 | https://www.threads.com/@career_sister/post/DWTmBXrE-5d |
| 水 3/26 朝 | エンゲージメント/型1-B | 投稿済 | https://www.threads.com/@career_sister/post/DWU_TrlAb5w |
| 水 3/26 昼 | 収益化/型3 | 投稿済 | https://www.threads.com/@career_sister/post/DWVP0yXicWG |

### 本セッションで投稿

**水 3/26 夜 (有益/型5/T9, Instagram+7枚)**

内容: 転職求人倍率2.40倍・売り手市場データ (Threads) + 2026年企業が求めるスキルTOP5 (Instagram カルーセル)

手順:
1. `creator/career_sister/drafts/week_2026-03-24/day_3_wed/slot_3_evening/` を確認
2. `carousel/` ディレクトリ未生成を検知
3. `render_carousel.py slides.json --output-dir carousel/` で7枚PNG生成
4. R2 `upload_batch()` で career_sister/ プレフィックスにアップロード
5. `poster threads --text <threads_post.md>` で投稿
6. `poster instagram --image-urls <7URLs>` でカルーセル投稿
7. `meta.json` の水夜スロットを `published` に更新

結果:
- Threads: https://www.threads.com/@career_sister/post/DWWPBNPkiY2
- Instagram: https://www.instagram.com/p/DWWPWnGEmGd/

## 決定事項

1. **カルーセル投稿フロー確立**: `instagram_caption.md` が存在しない場合、`slides.json` の `hook` フィールドをキャプション生成のベースとする。carousel/ 未生成なら `render_carousel.py` を先に実行する。

## 残りスロット (12件)

| 日 | スロット | テーマ | Instagram |
|---|------|--------|-----------|
| 木 3/27 朝 | 年収交渉でやらかした話 | ✅ 7枚 |
| 木 3/27 昼 | スキルを「動詞」で分解する | - |
| 木 3/27 夜 | キャリアチェンジアンケート | - |
| 金 3/28 朝 | 履歴書写真とPDF化 | - |
| 金 3/28 昼 | 30代転職54%が年収アップ | ✅ 7枚 |
| 金 3/28 夜 | 転職1ヶ月目に後悔した話 | - |
| 土 3/29 朝 | 面接で最高の手応えがあった回答 | ✅ 7枚 |
| 土 3/29 昼 | 年収満足度アンケート | - |
| 土 3/29 夜 | 転職サイトの使い分け方 | - |
| 日 3/30 朝 | 未経験からCS職への転職 | - |
| 日 3/30 昼 | 職種別年収ランキング・SaaS vs SIer | ✅ 7枚 |
| 日 3/30 夜 | 職務経歴書で大恥かいた話 | - |

## アクションアイテム

- [ ] 残り12スロットを順次投稿 (次: 木朝 3/27, 優先度: 高, 期限: 2026-03-30)
  - Instagram スロットは `render_carousel.py` → R2アップロード → 投稿の順で実行
  - `/career-sister-publish` コマンドを使う

## 参考情報

- `creator/career_sister/drafts/week_2026-03-24/meta.json`: 投稿状態の管理ファイル
- R2 public URL: `https://pub-589efc877dc54a9d967741f7e2a1c5f9.r2.dev`
- Instagram carousel: 子コンテナ全7件が FINISHED になるまで数分かかる
