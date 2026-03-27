# kuroto-draft: 7日分の投稿下書き一括生成

玄人領域アカウントの **7日分（35 Threads投稿 + 7 note記事 = 42コンテンツ）** を一括生成するコマンド。

## 引数

- 開始日（任意）: 週の開始日を指定（デフォルト: 次の月曜日）
- `--days N`: 生成日数を変更（デフォルト: 7）

## 日次スロット（5投稿/日）

| スロット | 時間 | カテゴリ | 文字数目安 |
|---------|------|---------|----------|
| S1 | 07:30 | 哲学的基盤 | 300-450字 |
| S2 | 12:00 | 思考フレームワーク | 300-450字 |
| S3 | 18:00 | 海外メソッド翻訳 | 300-450字 |
| S4 | 20:00 | 内向型戦略 | 300-450字 |
| S5 | 21:30 | 書籍紹介 / 補強 / note誘導 | 250-400字 |

**全投稿文は 500 文字以内**（Threads API 制限）。

## 曜日計算（必須）

ディレクトリ名・`day` フィールド・カレンダー表示の曜日は、**開始日から実際の曜日を計算**して使うこと。
ハードコードしてはならない。

```python
from datetime import date, timedelta

start = date.fromisoformat(start_date)  # 例: "2026-03-31"
WEEKDAY_JA = ["月", "火", "水", "木", "金", "土", "日"]

for day_offset in range(7):
    d = start + timedelta(days=day_offset)
    ja = WEEKDAY_JA[d.weekday()]   # 0=月, 6=日
    dir_name = f"day_{day_offset + 1}_{ja}"   # "day_1_月"
    day_label = ja                              # "月"
```

## 処理フロー

### Step 0: 状態読み込み

`creator/kuroto_area/posting_state.json` を読み込む。
アルゴリズム詳細は `creator/kuroto_area/posting_algorithm.md` を参照。

note_mode を確認:
- `"free"` かつ `note_count >= note_paid_threshold(10)`: メンバーシップ移行を促すメッセージを表示
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

        if category == "哲学":
            theme = select_theme(state, "哲学")  # 重み付き巡回、直近5件除外
            detail = {"theme": theme["id"], "concept": theme["concept"],
                      "author": theme["author"], "type": "型1"}

        elif category == "FW":
            theme = select_theme(state, "FW")
            detail = {"theme": theme["id"], "concept": theme["concept"],
                      "author": theme["author"], "type": "型2"}

        elif category == "海外メソッド":
            theme = select_theme(state, "海外メソッド")
            detail = {"theme": theme["id"], "concept": theme["concept"],
                      "author": theme["author"], "type": "型3"}

        elif category == "内向型Story":
            theme = select_theme(state, "内向型Story")
            detail = {"theme": theme["id"], "concept": theme["concept"],
                      "keywords": theme.get("keywords", []), "type": "型4"}

        elif category == "書籍紹介":
            detail = {"type": "型5", "book_tier": "tier1"}

        elif category == "補強":
            # 当日の S1-S4 から最も深掘り価値のあるものを選択
            base_slot = select_reinforcement_base(day_plan["slots"])
            detail = {"type": base_slot["type"] + "-deep",
                      "base_concept": base_slot.get("concept", ""),
                      "category_ref": base_slot.get("theme", "")}

        elif category == "note誘導":
            detail = {"type": "型2-CTA", "cta_target": "note_article"}

        day_plan["slots"].append({"slot": slot_key, "category": category, **detail})

    weekly_plan.append(day_plan)
```

決定結果を週間カレンダー形式で提示してから、即座に Step 2 へ進む（確認待ちなし）:

```
7日分の投稿計画（2026-03-31 〜 2026-04-06）note: 無料記事モード（0/10本）

月 07:30 S1  哲学/型1       PH1 制御二分法（Epictetus）
   12:00 S2  FW/型2         FW1 習慣スタッキング（James Clear）
   18:00 S3  海外メソッド/型3 MT1 睡眠最適化（Huberman）
   20:00 S4  内向型/型4      IN1 社会的比較
   21:30 S5  書籍紹介/型5    Atomic Habits

火 07:30 S1  哲学/型1       PH2 memento mori（Marcus Aurelius）
   12:00 S2  FW/型2         FW2 2分間ルール（James Clear）
   18:00 S3  海外メソッド/型3 MT2 Digital Minimalism（Cal Newport）
   20:00 S4  内向型/型4      IN2 完璧主義の罠
   21:30 S5  補強/型2-deep   FW1深掘り

...（以下7日分）
```

### Step 2: 素材取得（全スロット分）

**哲学・FW・海外メソッド・内向型**: `posting_algorithm.md` のテーマテーブルを直接参照。

**追加素材**: creator-neo4j から一括取得。

```cypher
MATCH (content)-[:IN_GENRE]->(g:Genre {name: 'self-development'})
WHERE (content:Story OR content:Tip OR content:Fact)
RETURN labels(content)[0] AS type, content.name AS name, content.text AS text,
       elementId(content) AS id
ORDER BY rand()
LIMIT 30
```

使用済み素材（`state.used_material_ids`）を除外。素材が枯渇した場合は
`posting_algorithm.md` のテーマテーブルからAIで生成する。

| スロット | 優先素材タイプ | 理由 |
|---------|--------------|------|
| S1 哲学 | Fact + Tip | 哲学的知見 + 実践的解釈 |
| S2 FW | Tip | 具体的なフレームワーク手順 |
| S3 海外メソッド | Fact + Tip | 科学的知見 + 実践方法 |
| S4 内向型 | Story | 変革体験 + 共感フック |
| S5 書籍 | Fact | 書籍の要点・名言 |

### Step 3: 全コンテンツ一括生成

**kuroto-writer スキルを読み込んでから**投稿文を生成する。
`.claude/skills/kuroto-writer/SKILL.md` を参照。

**確認なしで全37コンテンツを連続生成する。**

生成順序:
1. Day 1（月）のS1〜S5 + note記事（該当日のみ）
2. Day 2（火）のS1〜S5
3. ...
4. Day 7（日）のS1〜S5 + note記事（該当日のみ）

#### Threadsスロット別の生成ルール

**S1（哲学的基盤）— 型1**
```
型1（哲学一言 → 現代的解釈 → 今日の問い）:
  「{著者名}は言った。『{名言/概念}』」
  → 現代の行動科学・心理学での裏付け（50-100字）
  → 「今日、〜してみてください」or「〜ではないでしょうか」
  300-450字
```

**S2（思考フレームワーク）— 型2**
```
型2（問題提起 → FW紹介 → 第一歩）:
  よくある悩み・問題を1-2行で提起
  → フレームワークの紹介 + 著者名（50-100字）
  → 「今日、1つだけ。〜してみましょう」
  300-450字
```

**S3（海外メソッド翻訳）— 型3**
```
型3（海外知見 → 日本語実践 → 一行まとめ）:
  海外の研究者・実践者の知見紹介（1-2行）
  → 日本語での実践方法に翻訳（50-100字）
  → 一行要約「〜の問題です」「〜しましょう」
  300-450字
```

**S4（内向型戦略）— 型4**
```
型4（共感フック → 問題の本質 → 方向性）:
  内向型あるあるの悩み・感情を描写（1-2行）
  → 心理学的な本質の解説（50-100字）
  → 解決の方向性（押し付けず提案型）
  300-450字
```

**S5（書籍紹介）— 型5（月・水・金）**
```
型5（書籍要約 → 一つの型 → 参考文献）:
  書籍名と一言感想
  → この本から学んだ最も重要な1つの概念（50-100字）
  → 「参考文献はコメント欄に」
  250-400字
```

**S5（補強投稿）— 型X-deep（火・木・土）**
```
当日S1-S4のいずれかを深掘り:
  元投稿の概念を別角度から解説
  → 追加の研究・事例（50-100字）
  → 実践のヒント
  300-450字
```

**S5（note誘導）— 型2-CTA（日のみ）**
```
思考FW型の投稿 + note CTA:
  FWの紹介（独立した価値あり）
  → 「より深く体系的に学びたい方は、noteで書いています」
  250-400字
```

#### note記事の生成ルール（無料モード）

**1日1本（7本/週）**。文字数目安: 1,000-3,000字（Threadsより体系的な解説）

| 曜日 | テーマ | 構成 |
|------|--------|------|
| 月 | 哲学実践ガイド（S1の概念を深掘り） | 概念説明 → 心理学との接点 → 実践ステップ → まとめ |
| 火 | 哲学実践ガイド（S1の概念を深掘り） | 概念説明 → 心理学との接点 → 実践ステップ → まとめ |
| 水 | FW実践ガイド（週前半のFW深掘り） | 概念紹介 → 具体的な手順 → よくある躓き → 最初の一歩 |
| 木 | 哲学×行動科学（S1の概念を深掘り） | 哲学的問い → 科学的裏付け → 内向型向け実践法 → まとめ |
| 金 | 行動設計ガイド（S4/S3テーマを深掘り） | 概念説明 → 内向型との相性 → 実践設計 → まとめ |
| 土 | 哲学×行動科学（週のテーマを統合） | 哲学的問い → 科学的裏付け → 内向型向け実践法 → まとめ |
| 日 | 週次振り返りガイド（週の総括） | 振り返りの意義 → 実践手順 → 来週への問い → まとめ |

**フォーマット**: note.com での読みやすさ重視。見出し（##）を使う。
**ハッシュタグ**: #自己啓発 #思考法 #内向型 #習慣化

### Step 4: 下書き保存

```
creator/kuroto_area/drafts/week_YYYY-MM-DD/
├── day_1_{曜日}/              ← 開始日の実際の曜日
│   ├── s1_philosophy.md      # 07:30 哲学
│   ├── s2_framework.md       # 12:00 思考FW
│   ├── s3_overseas.md        # 18:00 海外メソッド
│   ├── s4_introvert.md       # 20:00 内向型
│   └── s5_book.md            # 21:30 書籍紹介
├── day_2_{曜日}/
│   ├── s1_philosophy.md
│   ├── s2_framework.md
│   ├── s3_overseas.md
│   ├── s4_introvert.md
│   └── s5_reinforcement.md   # 21:30 補強
├── day_3_{曜日}/
│   ├── s1_philosophy.md
│   ├── s2_framework.md
│   ├── s3_overseas.md
│   ├── s4_introvert.md
│   ├── s5_book.md            # 21:30 書籍紹介
│   └── note_article.md       # note記事（FW実践ガイド）
├── day_4_{曜日}/ ... day_5_{曜日}/ ... day_6_{曜日}/
│   └── note_article.md       # note記事（哲学×行動科学）
├── day_7_{曜日}/
│   ├── s1_philosophy.md
│   ├── s2_framework.md
│   ├── s3_overseas.md
│   ├── s4_introvert.md
│   └── s5_note_cta.md        # 21:30 note誘導
└── meta.json
```

各 `post.md` の先頭に以下のフロントマターを付与:

```yaml
---
slot: S1
time: "07:30"
category: 哲学
type: 型1
theme_id: PH1
concept: 制御二分法
author: Epictetus
char_count: 380
topic_tag: 自己啓発
---
```

**カテゴリ別 topic_tag デフォルト値**:

| カテゴリ | topic_tag |
|---------|-----------|
| 哲学 | `自己啓発` |
| FW | `思考法` |
| 海外メソッド | `自己啓発` |
| 内向型Story | `内向型` |
| 書籍紹介 | `読書` |
| 補強 | 元カテゴリに準ずる |
| note誘導 | `自己啓発` |

### Step 5: 状態更新

```python
state["total_posts"] += 35
state["total_note_articles"] += 2

# テーマ巡回・カウント更新
for day in weekly_plan:
    for slot in day["slots"]:
        if "theme_id" in slot:
            state["recent_themes"].append(slot["theme_id"])
            state["theme_use_counts"][slot["theme_id"]] += 1
        state["type_rotation"][slot["category"]] += 1

state["used_material_ids"].extend(all_used_ids)
```

### Step 6: 結果報告

```
7日分の下書き生成完了（2026-03-31 〜 2026-04-06）

  Threads投稿: 35本
  note記事:     2本（無料モード、累計 0/10本）

  カテゴリ内訳:
    哲学       7本  FW      7本  海外メソッド  7本
    内向型     7本  書籍紹介 3本  補強          3本
    note誘導   1本

  テーマ消化:
    哲学:       PH1, PH2, PH3, PH4, PH5, PH1, PH2
    FW:         FW1, FW2, FW3, FW4, FW5, FW1, FW2
    海外:       MT1, MT2, MT3, MT4, MT5, MT1, MT2
    内向型:     IN1, IN2, IN3, IN4, IN5, IN1, IN2

保存先: creator/kuroto_area/drafts/week_2026-03-31/

次のアクション:
  → 下書きを確認して修正
  → /kuroto-publish 2026-03-31  （スロット別に投稿）
```

## meta.json（7日分）

```json
{
  "week_start": "2026-03-31",
  "week_end": "2026-04-06",
  "status": "draft",
  "note_mode": "free",
  "note_count_before": 0,
  "note_count_after": 2,
  "total_threads_posts": 35,
  "total_note_articles": 2,
  "days": [
    {
      "day": "月",
      "date": "2026-03-31",
      "slots": [
        {
          "slot": "S1", "time": "07:30", "category": "哲学", "type": "型1",
          "theme_id": "PH1", "concept": "制御二分法", "author": "Epictetus",
          "file": "day_1_月/s1_philosophy.md", "char_count": 380,
          "posted_at": null, "permalink": null
        },
        {
          "slot": "S2", "time": "12:00", "category": "FW", "type": "型2",
          "theme_id": "FW1", "concept": "習慣スタッキング", "author": "James Clear",
          "file": "day_1_月/s2_framework.md", "char_count": 420,
          "posted_at": null, "permalink": null
        },
        {
          "slot": "S3", "time": "18:00", "category": "海外メソッド", "type": "型3",
          "theme_id": "MT1", "concept": "睡眠最適化", "author": "Andrew Huberman",
          "file": "day_1_月/s3_overseas.md", "char_count": 350,
          "posted_at": null, "permalink": null
        },
        {
          "slot": "S4", "time": "20:00", "category": "内向型Story", "type": "型4",
          "theme_id": "IN1", "concept": "社会的比較",
          "file": "day_1_月/s4_introvert.md", "char_count": 400,
          "posted_at": null, "permalink": null
        },
        {
          "slot": "S5", "time": "21:30", "category": "書籍紹介", "type": "型5",
          "file": "day_1_月/s5_book.md", "char_count": 350,
          "posted_at": null, "permalink": null
        }
      ],
      "note": null
    }
  ]
}
```

## 文字数制限（必須）

**Threads API のテキスト上限は 500 文字。** 全投稿文は必ず 500 文字以内で生成すること。

| スロット | 文字数目安 | 上限 |
|---------|-----------|------|
| S1 哲学 | 300-450字 | 500字 |
| S2 FW | 300-450字 | 500字 |
| S3 海外メソッド | 300-450字 | 500字 |
| S4 内向型 | 300-450字 | 500字 |
| S5 書籍/補強/CTA | 250-400字 | 500字 |

生成後に `len(text)` で文字数を検証し、500文字を超える場合は短縮してから保存すること。

## 注意事項

- 投稿文生成時は必ず kuroto-writer スキルを参照すること（`.claude/skills/kuroto-writer/SKILL.md`）
- **全投稿文は 500 文字以内**（Threads API 制限）。超過すると投稿時に 500 エラーになる
- テーマ選択は `posting_algorithm.md` Section 4 のテーマテーブルを参照
- 素材の text が空の場合はスキップして別素材を取得（またはテーマテーブルから生成）
- note記事は Threads投稿と連動させる（週のテーマを深掘りする構成）
- NGワード（「今すぐ」「爆速」「俺」「根性」等）は `persona.md` を参照
- **口調は必ず「です・ます」調**。タメ口（career_sister）や温かい語りかけ（mitsuki）と混同しない
- 7日分の生成はコンテキストが大きくなるため、1日ずつ順番に生成する
