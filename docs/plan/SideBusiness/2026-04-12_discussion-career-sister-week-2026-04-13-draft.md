# 議論メモ: career_sister 週次下書き生成 (week_2026-04-13)

**日付**: 2026-04-12
**参加**: ユーザー + AI
**関連 Discussion**: `disc-2026-04-12-career-sister-week-2026-04-13-draft`

## 背景・コンテキスト

`/career-sister-draft` コマンドで、2026-04-13（月）〜 2026-04-19（日）の1週間分の投稿下書きを一括生成した。
cycle_position=3, current_cycle=5 の状態から開始し、Threads 21本 + Instagram 7本を生成。

## 生成内容サマリー

### 週次カレンダー

| Day | 日付 | 朝 | 昼 | 夜 (📷IG) |
|-----|------|----|----|---------|
| 1 | 04-13 月 | 有益/型1/T1 面接対策 | 有益/型2/T4 キャリアチェンジ | 有益/型5/T9 市場データ |
| 2 | 04-14 火 | 有益/型4/T10 業界別 | ENG/型1-B/T7 メンタル | 収益/型3/T5 エージェント |
| 3 | 04-15 水 | 有益/型3/T6 退職 | 有益/型5/T3 年収 | 有益/型1/T2 職務経歴書 |
| 4 | 04-16 木 | ENG/型1-A/T8 強み | 有益/型2/T4 キャリアチェンジ | 有益/型5/T9 市場データ |
| 5 | 04-17 金 | 有益/型4/T10 業界別 | 有益/型3/T6 退職 | ENG/型1-B/T7 メンタル |
| 6 | 04-18 土 | 収益/型3/T5 エージェント | 有益/型5/T3 年収 | 有益/型1/T1 面接対策 |
| 7 | 04-19 日 | 有益/型2/T2 職務経歴書 | ENG/型1-A/T8 強み | 有益/型5/T9 市場データ |

### 統計

- **Threads**: 21本（有益 15 / ENG 4 / 収益化 2） 全て500字以内
- **Instagram**: 7本、カルーセル計 48 スライド
- **型5使用**: 5回（必須3回以上 ✓）
- **テーマ分布**: 10テーマに均等配分（T9 のみ3回、他は2回ずつ）
- **サイクル消化**: 2.1（cycle 5 → 7）

## 決定事項

1. **Instagram は常に夜スロット固定** (`dec-2026-04-12-ig-slot-evening-convention`)
   - 理由: auto_poster.py と既存ディレクトリ構造が slot_3_evening 前提
2. **型5を週5回使用** (`dec-2026-04-12-type5-weekly-5-uses`)
   - 必須3回以上を上回り、データ駆動の主張7を強化
3. **slides.json 内では日本語鉤括弧 『』 を使用** (`dec-2026-04-12-slides-json-use-bracket-quotes`)
   - Day1/2/3/6 で "〜" による JSON 構文エラーが発生したため

## アクションアイテム

- [ ] [高] week_2026-04-13 下書きを目視レビュー（〜4/13朝まで）
- [ ] [中] 4/13 朝の auto-poster 初回実行ログを確認
- [ ] [低] career-sister-writer スキルに 『』 ルールを追記

## 状態更新

`creator/career_sister/posting_state.json`:
- `current_cycle`: 5 → 7
- `cycle_position`: 3 → 4
- `total_posts`: 43 → 64
- `type_rotation`: 有益 30→45, ENG 9→13, 収益化 4→6

## 次回の議論トピック

- 4/13 週の投稿結果（エンゲージメント・リーチ）レビュー
- 型5の効果検証（T9/T10 データ駆動投稿の反応分析）
- next week (4/20-) のテーマ配分微調整

## 保存先

- Neo4j Discussion: `disc-2026-04-12-career-sister-week-2026-04-13-draft`
- Neo4j Decisions: `dec-2026-04-12-ig-slot-evening-convention`, `dec-2026-04-12-type5-weekly-5-uses`, `dec-2026-04-12-slides-json-use-bracket-quotes`
- Neo4j ActionItems: `act-2026-04-12-001` 〜 `003`
- ドラフト: `creator/career_sister/drafts/week_2026-04-13/`
