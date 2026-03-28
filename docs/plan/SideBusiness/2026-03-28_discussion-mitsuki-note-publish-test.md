# 議論メモ: みつき note下書き投稿テスト

**日付**: 2026-03-28
**参加**: ユーザー + AI

## 背景・コンテキスト

みつき（美月）アカウントの note.com 下書き投稿を `publish_to_note.py --creator-mode` で自動化するテストを実施。week_2026-03-31 の全7日分（7本）を対象とした。

## 議論のサマリー

### 発生した問題

実行コマンド:
```bash
uv run python scripts/publish_to_note.py --creator-mode creator/mitsuki/drafts/week_2026-03-31/day_1_月
```

エラー:
```
waiting for locator('div[contenteditable="true"]') to be visible
Timeout 30000ms exceeded
```

### 根本原因の特定

1. セッションファイル `config/note-storage-state.json`（実体: `data/config/note-storage-state.json`）が存在しない
2. ログイン状態がないため note.com はログインページにリダイレクト
3. エディタ要素が出ず 30秒タイムアウト

### 追加判明事項

- **みつきと玄人領域は別々の note.com アカウント**を持つ
- そのためセッションファイルはクリエイターごとに分ける必要がある
- headless モードでは note.com がbot検出してエディタを出さない → `NOTE_HEADLESS=false` が必須

### 解決手順

```bash
# 1. みつき専用セッションでログイン
NOTE_HEADLESS=false NOTE_SESSION_PATH=data/config/note-storage-state-mitsuki.json \
  uv run python scripts/publish_to_note.py --login-only

# 2. セッションを使って投稿
NOTE_HEADLESS=false NOTE_SESSION_PATH=data/config/note-storage-state-mitsuki.json \
  uv run python scripts/publish_to_note.py --creator-mode creator/mitsuki/drafts/week_2026-03-31/day_1_月
```

### テスト結果

week_2026-03-31 全7日分の下書き投稿に成功:

| 日 | テーマ | 下書きnote ID |
|----|--------|--------------|
| 月 | タロット解説（魔術師） | n467031371f07 |
| 火 | 星座×心理学（牡牛座） | n1c24cc106bef |
| 水 | 自己理解Tips（愛着理論） | n3377bc4e32ef |
| 木 | タロット解説（塔） | nda20d5260157 |
| 金 | 星座×心理学（獅子座vs乙女座） | n190f8d6006fe |
| 土 | Tips実践（ジャーナリング） | n6fec7dd5c350 |
| 日 | 占い入門（数秘術） | ned400b1dd33e |

## 決定事項

1. **クリエイター別セッションファイル分離**（dec-2026-03-28-note-session-per-creator）
   - mitsuki: `data/config/note-storage-state-mitsuki.json`（作成済み）
   - kuroto_area: `data/config/note-storage-state-kuroto.json`（次回テスト時に作成）

2. **NOTE_HEADLESS=false 必須**（dec-2026-03-28-note-headless-required）
   - headless モードでは note.com がbot検出してエディタを出さない
   - mitsuki・kuroto_area 両方に適用

## アクションアイテム

- [x] mitsuki week_2026-03-31 note下書き全7日分投稿（完了）
- [x] イントロ段落確認（全7日分OK）
- [ ] kuroto_area も同様のセッションセットアップ + テスト投稿 (優先度: 高)
- [ ] auto_poster.py / mitsuki-publish / kuroto-publish スキルに NOTE_HEADLESS=false と NOTE_SESSION_PATH を反映（launchd自動化時に必要） (優先度: 中)

## 次回の議論トピック

- kuroto_area の note 投稿テスト（同様の手順で実施）
- NOTE_HEADLESS=false の launchd / auto_poster.py への組み込み方針
