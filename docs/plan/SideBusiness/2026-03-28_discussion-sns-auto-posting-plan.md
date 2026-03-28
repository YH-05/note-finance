# 議論メモ: SNS自動投稿 定期実行計画（3ペルソナ対応）

**日付**: 2026-03-28
**参加**: ユーザー + AI
**Neo4j Discussion ID**: disc-2026-03-28-sns-auto-posting-plan

## 背景・コンテキスト

キャリアお姉さん・みつき・玄人領域の3ペルソナのSNS投稿を `auto_poster.py` + `launchd` で定期自動実行する計画の進捗確認と次のアクション整理。

## 決定事項

1. **2アカウント先行開始** → career_sister のみ 3/28 から稼働（dec-2026-03-28-two-account-first）
2. **topic_tag バグ修正**（dec-2026-03-28-topic-tag-fix）
   - auto_poster.py: 本文末尾追記 → Threads API パラメータ渡し
   - career_sister: `CAREERS` → `転職` に日本語化
3. **3アカウント独立 plist 化**（dec-2026-03-28-independent-plist）
   - `com.note-finance.auto-poster-mitsuki.plist`
   - `com.note-finance.auto-poster-career-sister.plist`
   - `com.note-finance.auto-poster-kuroto-area.plist`
4. **mitsuki/kuroto_area は来週まで見送り**（dec-2026-03-28-mitsuki-kuroto-defer）
   - launchd unload 済み。整備完了後に再開
5. **jitter 機能追加**（dec-2026-03-28-jitter-feature）
   - `--jitter 10`（デフォルト有効）で投稿前に半正規分布 0〜10分遅延
   - 3アカウント共通適用。`--jitter 0` で無効化可能
   - launchd plist 変更不要（スクリプト側で遅延）

## 実施済みアクション

### auto_poster.py 変更
- [x] kuroto_area を ACCOUNTS に追加
- [x] per-account SLOT_TIME_MAP（3アカウント別の時刻マッピング）
- [x] per-account SLOT_INDEX_MAP / DAY_DIR_MAP
- [x] DraftReader.get_slot_file(): meta.json の file フィールドから解決（mitsuki/kuroto対応）
- [x] main(): アカウントごとに SlotMatcher 生成
- [x] topic_tag: 本文追記 → API パラメータ渡し

### ドラフト生成
- [x] career_sister week_2026-03-31: Threads 21本 + IG 7本 + カルーセル 49枚
- [x] mitsuki week_2026-03-28: Threads 10本 + note 2本（2日分）

### インフラ
- [x] 3つの独立 launchd plist 作成・登録
- [x] mitsuki/kuroto_area を unload（来週まで見送り）
- [x] carousel.html / posting_algorithm.md / persona.md 復元（git restore）
- [x] jitter 機能追加（`--jitter 10`、半正規分布、デフォルト有効）

### launchd スケジュール

| plist | アカウント | スロット | 状態 |
|-------|-----------|---------|------|
| auto-poster-career-sister | career_sister | 07:30/12:30/20:30 | **稼働中** |
| auto-poster-mitsuki | mitsuki | 07:00/12:00/15:00/19:00/22:00 | 停止（unload） |
| auto-poster-kuroto-area | kuroto_area | 07:30/12:00/18:00/20:00/21:30 | 停止（unload） |

## 残りアクションアイテム

### mitsuki 整備（来週再開前）
- [ ] mitsuki 自己紹介投稿（Threads）
- [ ] note アカウント Bio 設定
- [ ] ドラフトレビュー（week_2026-03-28: 10本, week_2026-03-31: 35本）
- [ ] launchctl load で再開

### kuroto_area 整備（来週再開前）
- [ ] kuroto_area 自己紹介投稿（Threads）
- [ ] ドラフトレビュー（week_2026-03-30: 35本）
- [ ] launchctl load で再開

### career_sister（稼働中）
- [ ] 3/28 夜スロット以降の自動投稿結果を確認

## 再開コマンド

```bash
launchctl load ~/Library/LaunchAgents/com.note-finance.auto-poster-mitsuki.plist
launchctl load ~/Library/LaunchAgents/com.note-finance.auto-poster-kuroto-area.plist
```

## 参考情報

- auto_poster.py: `scripts/auto_poster.py`
- launchd plist: `config/launchd/com.note-finance.auto-poster-*.plist`
- career_sister ドラフト: `creator/career_sister/drafts/week_2026-03-31/`
- mitsuki ドラフト: `creator/mitsuki/drafts/week_2026-03-28/` + `week_2026-03-31/`
- kuroto ドラフト: `creator/kuroto_area/drafts/week_2026-03-30/`
- GitHub Project: [#104](https://github.com/users/YH-05/projects/104)
