# 議論メモ: みつき 投稿頻度・アルゴリズム全面改訂

**日付**: 2026-03-27
**参加**: ユーザー + AI

## 背景・コンテキスト

みつき（美月）アカウントの運用基盤（ペルソナ・スキル・コマンド・数秘術テンプレート）が2026-03-27に整備完了。
投稿頻度を当初設計の週4投稿から大幅に引き上げ、フォロワー獲得フェーズとして1日5投稿体制に移行する議論を実施。
あわせて、self-understandingジャンルの初期素材を creator-research で投入し、コンテンツ生成基盤を整備した。

## 議論のサマリー

### 投稿頻度変更の背景
- 週4投稿では認知獲得に時間がかかりすぎる
- Threads はアルゴリズム上、投稿頻度が高いほど露出しやすい
- 1日5スロット×7日 = 35投稿/週 の体制に移行

### self-understanding ジャンル新設の経緯
- 既存の spiritual ジャンルは「占い副業ビジネス」系データが中心で、みつきのコンテンツ（タロット×心理学・自己理解）に不適合
- 新ジャンル `self-understanding`（genre_id）を creator-neo4j に作成
- creator-research でタロット×ユング、Eurich式自己認識、愛着理論、ジャーナリング（Pennebaker）、認知の歪み（Burns）の素材を投入

## 決定事項

1. **みつきの Threads 投稿頻度**: 週4投稿 → **1日5投稿（35投稿/週）**
   - S1(7:00): タロット / 星座（朝のカードメッセージ）
   - S2(12:00): 自己理解Tips（昼の実践ワーク）
   - S3(15:00): エンゲージメント（問いかけ・共感）
   - S4(19:00): 星座 / タロット深掘り
   - S5(22:00): note誘導 or Story自己開示

2. **note記事の無料→有料移行戦略**
   - まず無料記事で10本蓄積（`note_paid_threshold: 10`）
   - フォロワーの反応が確認できたら有料化（手動判断）
   - 有料プロダクト: 数秘術鑑定書¥500-1,000 / ガイドブック¥2,000-3,000

3. **/mitsuki-draft コマンド設計（案B採用）**
   - 7日分（35 Threads + 7 note = 42コンテンツ）を確認なしで一括生成
   - 生成後にまとめて確認・修正する方式

## 実施済み作業

| ファイル | 変更内容 |
|---------|---------|
| `creator/mitsuki/posting_algorithm.md` | 週4 → 日5スロット、7日サイクル、note無料→有料移行ロジック |
| `creator/mitsuki/posting_state.json` | `posts_per_day:5`、`note_mode:free`、`note_count:0`、7日サイクル配列 |
| `.claude/commands/mitsuki-draft.md` | 7日分42コンテンツ一括生成（案B）に全面改訂 |
| `scripts/emit_creator_queue_v2.py` | `self-understanding` ジャンル追加 |
| `creator/mitsuki/persona.md` | 作成済み（前セッション） |

## creator-research 完了サマリー（self-understanding）

```
トピック: タロット×心理学 自己理解
ジャンル: self-understanding（新規）
深度: deep

投入結果:
  Genre: self-understanding（新規）
  ConceptCategory: PsychologyFramework, SelfAwarenessMethod（新規2件）
  Source: 10件
  Entity: 5件（Carl Gustav Jung, Tasha Eurich, John Bowlby, Mary Ainsworth, James Pennebaker）
  Concept: 22件
  Fact: 5件, Tip: 6件, Story: 4件
```

## アクションアイテム

- [ ] Threads アカウント開設・プロフィール設定（優先度: 高）
  - 表示名: `みつき|占いで自分を知る`
  - Bio: `creator/mitsuki/persona.md` Threads Bio セクション参照
- [ ] `/mitsuki-draft` を実行して最初の7日分ドラフト生成（優先度: 高）
- [ ] `used_material_ids` 消化率70%超で `/creator-research --topic "星座×愛着理論"` 実行（優先度: 中）

## 次回の議論トピック

- Threads アカウント開設後の初投稿戦略（自己紹介投稿のタイミングと内容）
- `/mitsuki-publish` コマンドの設計（Threads API 接続・スロット別スケジュール投稿）
- note 記事の SEO 戦略（タイトル・見出し設計）
- 10本無料記事達成後の有料移行タイミング判断基準

## 参考情報

- アルゴリズム詳細: `creator/mitsuki/posting_algorithm.md`
- 状態管理: `creator/mitsuki/posting_state.json`
- コマンド: `.claude/commands/mitsuki-draft.md`
- ペルソナ定義: `creator/mitsuki/persona.md`
- self-understanding リサーチノート: `.tmp/creator-research-tarot-psychology-self-understanding_20260327-130000.md`
