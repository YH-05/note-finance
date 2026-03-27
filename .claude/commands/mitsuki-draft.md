# mitsuki-draft: 7日分の投稿下書き一括生成

みつき（美月）アカウントの **7日分（35 Threads投稿 + 7 note記事 = 42コンテンツ）** を一括生成するコマンド。

## 引数

- 開始日（任意）: 週の開始日を指定（デフォルト: 次の月曜日）

## 日次スロット（5投稿/日）

| スロット | 時間 | カテゴリ | 文字数目安 |
|---------|------|---------|----------|
| S1 | 07:00 | タロット / 星座 | 300-450字 |
| S2 | 12:00 | 自己理解Tips | 300-450字 |
| S3 | 15:00 | エンゲージメント | 200-350字 |
| S4 | 19:00 | 星座 / タロット（深掘り） | 300-450字 |
| S5 | 22:00 | note誘導 / Story | 250-400字 |

**全投稿文は 500 文字以内**（Threads API 制限）。

## 処理フロー

### Step 0: 状態読み込み

`creator/mitsuki/posting_state.json` を読み込む。
アルゴリズム詳細は `creator/mitsuki/posting_algorithm.md` を参照。

note_mode を確認:
- `"free"` かつ `note_count >= note_paid_threshold(10)`: 有料移行を促すメッセージを表示
- それ以外: free モードで継続

### Step 1: 7日分の全パラメータを一括決定

`posting_state.json` の `seven_day_schedule` から7日分のスロット配分を読み込む。
各スロットについて以下を決定する:

```python
weekly_plan = []

for day_entry in state["seven_day_schedule"]:
    day_plan = {"day": day_entry["day"], "slots": []}

    for slot_key in ["S1", "S2", "S3", "S4", "S5"]:
        category = day_entry[slot_key]

        if category == "タロット":
            card = select_tarot_card(state)  # 直近8枚除外
            psychology = TAROT_PSYCHOLOGY_MAP[card]
            detail = {"tarot_card": card, "psychology": psychology,
                      "type": "型1-A" if state["type_rotation"]["タロット"] % 2 == 0 else "型1-B"}

        elif category == "星座":
            sign = select_zodiac(state)  # エレメント巡回
            psychology = ZODIAC_PSYCHOLOGY_MAP[sign]
            detail = {"zodiac_sign": sign, "psychology": psychology, "type": "型2"}

        elif category == "Tips":
            theme = select_tips_theme(state)  # 重み付き均等分散
            tips_type_idx = state["type_rotation"]["Tips"] % 4
            tips_type = ["型3-A", "型3-B", "型3-C", "型3-D"][tips_type_idx]
            detail = {"theme": theme["id"], "type": tips_type}

        elif category == "ENG":
            detail = {"type": "型4"}

        elif category == "note誘導":
            detail = {"type": "型3-D", "cta_target": "note_article"}

        elif category == "Story":
            detail = {"type": "型4-B"}

        day_plan["slots"].append({"slot": slot_key, "category": category, **detail})

    # note記事テーマも決定
    day_plan["note"] = determine_note_theme(day_plan, state)
    weekly_plan.append(day_plan)
```

決定結果を週間カレンダー形式で提示してから、即座に Step 2 へ進む（確認待ちなし）:

```
7日分の投稿計画（2026-03-31 〜 2026-04-06）note: 無料記事モード（3/10本）

月 07:00 S1  タロット/型1-A   塔（認知的再評価）
   12:00 S2  Tips/型3-A      TI1 Eurich式What問い
   15:00 S3  ENG/型4         問いかけ
   19:00 S4  星座/型2         天秤座（均衡欲求・愛着理論）
   22:00 S5  note誘導/型3-D  自己理解Tips→note CTA
   note        タロット解説（塔）                           [無料]

火 07:00 S1  星座/型2         蠍座（深層心理・Jung）
   ...（以下7日分）
```

### Step 2: 素材取得（全スロット分）

**タロット・星座**: `posting_algorithm.md` のマッピングテーブルを直接参照（neo4j不要）。

**Tips / Story**: creator-neo4j から一括取得。

```cypher
MATCH (content)-[:IN_GENRE]->(g:Genre {genre_id: 'self-understanding'})
WHERE (content:Story OR content:Tip OR content:Fact)
RETURN labels(content)[0] AS type, content.name AS name, content.text AS text,
       elementId(content) AS id
ORDER BY rand()
LIMIT 30
```

使用済み素材（`state.used_material_ids`）を除外。素材が枯渇した場合は
`posting_algorithm.md` のマッピングテーブルからAIで生成する（補足注記あり）。

### Step 3: 全コンテンツ一括生成

**mitsuki-writer スキルを読み込んでから**投稿文を生成する。
`.claude/skills/mitsuki-writer/SKILL.md` を参照。

**確認なしで全42コンテンツを連続生成する（案B）。**

生成順序:
1. Day 1（月）のS1〜S5 + note記事
2. Day 2（火）のS1〜S5 + note記事
3. ...
4. Day 7（日）のS1〜S5 + note記事

#### Threadsスロット別の生成ルール

**S1・S4（タロット）— 型1-A / 型1-B**
```
型1-A（週次1枚引き）:
  「今週のカード: {カード名}」
  → タロットの意味（詩的）+ 心理学概念（Eurich/Jung/愛着理論等）
  → 「今週、これが気になった人へ──」
  300-450字

型1-B（Pick-a-Card）:
  「直感で選んで。」から始める
  → 選んだカードの意味 + 心理学的解説
  → 問いかけで締める
  300-400字
```

**S1・S4（星座）— 型2**
```
星座あるある（共感を引く1-2行）
→ 心理学的理由（{星座}の特性をPsychologyで説明）
→ 共感CTA「{星座}の人、これ刺さった？」
300-450字
```

**S2（Tips）— 型3-A/B/C/D**
```
型3-A: Eurich式What問い実践 → ワーク手順（1〜3ステップ）→ 「今日試してみて」
型3-B: 認知パターン解説 → 「あなたはどのパターン？」
型3-C: ジャーナリングプロンプト → 「今夜書いてみて」
型3-D: Tips本文 → 「もっと深く知りたい人は note へ」（note CTA付き）
300-450字
```

**S3（ENG）— 型4**
```
「〜だったりしない？」or「〜したことある？」の問いかけ1行
→ 「私も（自己開示1文）──」
→ 「コメントで教えてほしいな」
200-350字（短め・コメント誘導重視）
```

**S5（note誘導）— 型3-D**
```
当日S2 Tipsの続きor別角度のワーク紹介
→ 「もっと深く掘り下げた記事を note に書いたよ」
→ 「自分のこと、少しずつわかっていけるといいよね」
250-400字
```

**S5（Story自己開示）— 型4-B**
```
「これ、私も長いこと気づかなかったんだけど──」から始める
→ 具体的な自己開示（過去の体験or気づき、200字以内）
→ 「あなたはどう？」の問いかけ
250-400字
```

#### note記事の生成ルール（無料モード）

文字数目安: 500-900字（Threadsより深い考察）

| 曜日 | テーマ | 構成 |
|------|--------|------|
| 月 | タロット解説（当日S1のカード深掘り） | カードの意味 → 心理学的背景 → 実践ヒント |
| 火 | 星座 × 心理学（当日S1の星座深掘り） | 星座の特性 → 心理学理論 → 自己理解への応用 |
| 水 | 自己理解Tips詳細版（当日S2の拡張） | ワーク概要 → 詳細手順 → よくある躓きと対処 |
| 木 | タロット解説（前日と異なるカード） | カード比較視点も入れる |
| 金 | 星座 × 心理学（別星座、対比視点） | 2星座の対比で理解を深める |
| 土 | 自己理解Tips実践ワーク手順書 | より詳しい手順書形式 |
| 日 | 占い入門 / 数秘術概要 | 占いを自己理解ツールとして使う視点 → 数秘術へ自然に誘導 |

**フォーマット**: note.com での読みやすさ重視。見出し（##）を使う。
**ハッシュタグ**: #占い #自己理解 #心理学 #タロット（カード記事）or #星座（星座記事）

### Step 4: 下書き保存

```
creator/mitsuki/drafts/week_YYYY-MM-DD/
├── day_1_月/
│   ├── s1_tarot.md         # 07:00 タロット
│   ├── s2_tips.md          # 12:00 Tips
│   ├── s3_eng.md           # 15:00 ENG
│   ├── s4_zodiac.md        # 19:00 星座
│   ├── s5_note_cta.md      # 22:00 note誘導
│   └── note_article.md     # noteフル記事（500-900字）
├── day_2_火/
│   ├── s1_zodiac.md
│   ├── s2_tips.md
│   ├── s3_eng.md
│   ├── s4_tarot.md
│   ├── s5_story.md
│   └── note_article.md
├── day_3_水/ ... day_7_日/  （同構造）
└── meta.json
```

各 `post.md` の先頭に以下のフロントマターを付与:

```yaml
---
slot: S1
time: "07:00"
category: タロット
type: 型1-A
tarot_card: 塔
psychology: 認知的再評価（Lazarus）
char_count: 380
topic_tag: タロット占い
---
```

**カテゴリ別 topic_tag デフォルト値**:

topic_tag は自由文字列（1〜50字、ピリオド・アンパサンド不可）。日本語可。

| カテゴリ | topic_tag |
|---------|-----------|
| タロット | `タロット占い` |
| 星座 | `星座占い` |
| Tips | `自己理解` |
| ENG | `自己理解` |
| note誘導 | `自己理解` |
| Story | `自己理解` |

### Step 5: 状態更新

```python
state["total_posts"] += 35
state["total_note_articles"] += 7
state["note_count"] += 7

# カード履歴・星座ローテーション・テーマカウント更新
for day in weekly_plan:
    for slot in day["slots"]:
        if "tarot_card" in slot:
            state["tarot_card_history"].append(slot["tarot_card"])
        if "zodiac_sign" in slot:
            state["zodiac_rotation"] += 1
        if "theme" in slot:
            state["recent_themes"].append(slot["theme"])
            state["theme_use_counts"][slot["theme"]] += 1
        state["type_rotation"][slot["category"]] += 1

state["used_material_ids"].extend(all_used_ids)

# note_mode チェック
if state["note_mode"] == "free" and state["note_count"] >= state["note_paid_threshold"]:
    # 有料移行ガイドを最終報告に含める（自動切り替えはしない）
    pass
```

### Step 6: 結果報告

```
7日分の下書き生成完了（2026-03-31 〜 2026-04-06）

  Threads投稿: 35本
  note記事:     7本（無料モード、累計 3/10本）
  使用カード:   塔, 愚者, 魔術師, 恋人, 星, 世界, 月, 力
  使用星座:     天秤座, 蠍座, 牡羊座, 射手座, 双子座, 水瓶座

  カテゴリ内訳:
    タロット   8本  星座   6本  Tips    7本
    ENG        7本  note誘導 4本  Story  3本

保存先: creator/mitsuki/drafts/week_2026-03-31/

次のアクション:
  → 下書きを確認して修正
  → /mitsuki-publish 2026-03-31  （スロット別に投稿）
```

## meta.json（7日分）

```json
{
  "week_start": "2026-03-31",
  "week_end": "2026-04-06",
  "status": "draft",
  "note_mode": "free",
  "note_count_before": 0,
  "note_count_after": 7,
  "total_threads_posts": 35,
  "total_note_articles": 7,
  "days": [
    {
      "day": "月",
      "date": "2026-03-31",
      "slots": [
        {
          "slot": "S1", "time": "07:00", "category": "タロット", "type": "型1-A",
          "tarot_card": "塔", "psychology": "認知的再評価（Lazarus）",
          "file": "day_1_月/s1_tarot.md", "char_count": 380,
          "posted_at": null, "permalink": null
        },
        {
          "slot": "S2", "time": "12:00", "category": "Tips", "type": "型3-A", "theme": "TI1",
          "file": "day_1_月/s2_tips.md", "char_count": 420,
          "posted_at": null, "permalink": null
        },
        {
          "slot": "S3", "time": "15:00", "category": "ENG", "type": "型4",
          "file": "day_1_月/s3_eng.md", "char_count": 250,
          "posted_at": null, "permalink": null
        },
        {
          "slot": "S4", "time": "19:00", "category": "星座", "type": "型2",
          "zodiac_sign": "天秤座", "psychology": "均衡欲求・愛着理論",
          "file": "day_1_月/s4_zodiac.md", "char_count": 350,
          "posted_at": null, "permalink": null
        },
        {
          "slot": "S5", "time": "22:00", "category": "note誘導", "type": "型3-D",
          "file": "day_1_月/s5_note_cta.md", "char_count": 300,
          "posted_at": null, "permalink": null
        }
      ],
      "note": {
        "theme": "タロット解説（塔）", "mode": "free",
        "file": "day_1_月/note_article.md", "char_count": 650,
        "published_at": null, "permalink": null
      }
    }
  ]
}
```

## 注意事項

- 投稿文生成時は必ず mitsuki-writer スキルを参照すること（`.claude/skills/mitsuki-writer/SKILL.md`）
- **全 Threads 投稿文は 500 文字以内**（Threads API 制限）
- タロットカード × 心理学マッピングは `posting_algorithm.md` Section 6 を参照
- 星座 × 心理学マッピングは `posting_algorithm.md` Section 7 を参照
- 素材の text が空の場合はスキップして別素材を取得（またはマッピングテーブルから生成）
- note記事は Threads投稿と連動させる（当日のカード・星座を深掘りする構成）
- NGワード（「スピリチュアル」「波動」「絶対」「〜すべき」等）は `persona.md` を参照
