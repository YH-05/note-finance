# 議論メモ: SNS自動投稿スクリプト設計（auto_poster.py + launchd）

**日付**: 2026-03-27
**参加**: ユーザー + AI

## 背景・コンテキスト

みつき（@mitsuki_fortune）とキャリアお姉さん（@career_sister）の投稿を自動化するスクリプトの設計。
MacBook Pro と Mac Mini の2台から launchd を使って Threads / Instagram / note.com に定時投稿できる仕組みを設計した。

## 議論のサマリー

### アーキテクチャ設計

`scripts/auto_poster.py` を以下の4コンポーネント構成で設計:

| コンポーネント | 役割 |
|---------------|------|
| `AutoPosterConfig` | 設定・環境変数管理 |
| `SlotMatcher` | 現在時刻→今日のスロット特定 |
| `DraftReader` | meta.json・post.md 読み込み |
| `AccountPoster` | Threads/Instagram/note.com への投稿 |
| `StateUpdater` | meta.json / posting_state.json 更新 |

### ディレクトリ構造の差異

| アカウント | 日付ディレクトリ | スロットディレクトリ | 投稿ファイル |
|-----------|----------------|-------------------|------------|
| mitsuki | `day_1_月/` ... `day_7_日/` | `s1_tarot.md`（ファイル直置き） | ファイル自体がpost.md相当 |
| career_sister | `day_1_mon/` ... `day_7_sun/` | `slot_1_morning/` サブディレクトリ | `threads_post.md`, `instagram_post.md` |

### DAY_DIR_MAP（両アカウント共通キー）

```python
DAY_DIR_MAP = {
    "mitsuki": {0: "day_1_月", 1: "day_2_火", 2: "day_3_水", 3: "day_4_木", 4: "day_5_金", 5: "day_6_土", 6: "day_7_日"},
    "career_sister": {0: "day_1_mon", 1: "day_2_tue", 2: "day_3_wed", 3: "day_4_thu", 4: "day_5_fri", 5: "day_6_sat", 6: "day_7_sun"},
}
```

### SLOT_TIME_MAP（投稿時刻 JST）

```python
SLOT_TIME_MAP = {
    "mitsuki": {
        "朝": "07:00", "昼": "12:00", "夕": "17:00", "夜": "21:00",
    },
    "career_sister": {
        "朝": "07:00", "昼": "12:00", "夜": "21:00",
    },
}
```

### マルチマシン対応

- **NASロックファイル**: `/Volumes/NAS/note-finance/.auto_poster.lock` で同時実行防止
- **drafts同期**: NAS上の共有draftsを両マシンが参照
- **ライブラリ**: `filelock` で排他制御

### launchd スケジュール（8スロット）

```
mitsuki:       07:00 / 12:00 / 17:00 / 21:00
career_sister: 07:00 / 12:00 / 21:00
```

`com.note-finance.auto-poster.plist` の StartCalendarInterval で設定。

### 実装ステップ（10段階）

1. `AutoPosterConfig` クラス実装
2. `SlotMatcher` クラス実装（時刻→スロット名変換）
3. mitsuki の `DraftReader` 実装
4. career_sister の `DraftReader` 実装
5. `AccountPoster.post_threads()` 実装
6. `AccountPoster.post_instagram()` 実装（R2経由）
7. `AccountPoster.post_note()` 実装（Playwright）
8. `StateUpdater` 実装（meta.json / posting_state.json）
9. NASロックファイル実装（filelock）
10. launchd plist 作成・登録

## 決定事項

1. **auto_poster.py アーキテクチャ**: `SlotMatcher` / `DraftReader` / `AccountPoster` / `StateUpdater` の4コンポーネント構成
2. **launchd plist設計**: `StartCalendarInterval` で8スロット時刻を定義。MacBook Pro・Mac Mini 両方にインストール
3. **マルチマシン対応**: NASロックファイル（filelock）+ NAS上の共有draftsで排他制御と同期を両立

## アクションアイテム

- [ ] `scripts/auto_poster.py` を実装（10ステップ） (優先度: 中)
- [ ] `config/launchd/com.note-finance.auto-poster.plist` を作成・登録 (優先度: 中)
- [ ] テスト投稿2件を削除: @career_sister/post/DWYMpClEg3w と @mitsuki_fortune/post/DWYMnKdkneC (優先度: 高)
- [ ] Threads @mitsuki_fortuneに自己紹介投稿（persona.md テンプレート使用） (優先度: 高)
- [ ] note アカウントの表示名・Bio設定 (優先度: 高)
- [ ] week_2026-03-31 ドラフト（35本）のレビューと投稿準備（3/31から） (優先度: 高)

## 次回の議論トピック

- auto_poster.py の実装開始タイミング
- Mac Mini への launchd plist インストール手順
- week_2026-03-31 の投稿スケジュール確認

## 参考情報

- 設計詳細: `docs/plan/2026-03-27_sns-auto-poster-design.md`
- poster.py: `src/creator/poster.py`
- mitsuki drafts: `creator/mitsuki/drafts/week_YYYY-MM-DD/`
- career_sister drafts: `creator/career_sister/drafts/week_YYYY-MM-DD/`
