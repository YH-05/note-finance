# career-sister-draft: 1週間分の投稿下書き一括生成

career_sister アカウントの **1週間分（Threads 21本 + Instagram 7本）** の下書きを一括生成するコマンド。

## 引数

- 開始日（任意）: 週の開始日を指定（デフォルト: 明日）
- `--days N`: 生成日数を変更（デフォルト: 7）

## 日次スケジュール（1日あたり）

| スロット | 時間帯 | Threads | Instagram | 文字数目安 |
|---------|--------|---------|-----------|-----------|
| 朝 | 7:00 | 短め有益 | - | 200-300字 |
| 昼 | 12:00 | ENG/有益 | - | 250-400字 |
| 夜 | 20:00 | じっくり有益 | カルーセル化 | 350-500字 |

## 処理フロー

### Step 0: 状態読み込み + 1週間分のパラメータ一括決定

`creator/career_sister/posting_state.json` を読み込む。
アルゴリズム詳細は `creator/career_sister/posting_algorithm.md` を参照。

**21投稿分のパラメータを一括決定:**

```python
schedule = state["cycle_schedule"]  # 10投稿サイクル
pos = state["cycle_position"]
days = 7
weekly_plan = []

for day in range(days):
    daily_themes = []  # 同日テーマ重複排除用
    day_slots = []

    for slot_idx, slot_name in enumerate(["朝", "昼", "夜"]):
        i = day * 3 + slot_idx
        # 1. カテゴリ決定（10投稿サイクルの位置から）
        category = schedule[(pos + i) % 10]

        # 2. 型決定（カテゴリ内ローテーション）
        seq = state["type_sequence"][category]
        type_count = state["type_rotation"][category] + sum(
            1 for s in day_slots + [s for d in weekly_plan for s in d["slots"]]
            if s["category"] == category
        )
        post_type = seq[type_count % len(seq)]

        # 3. テーマ決定（直近5件 + 同日重複を除外 + 均等分散 + 重み付き）
        recent = state["recent_themes"][-5:]
        used_in_week = [s["theme"] for d in weekly_plan for s in d["slots"]]
        exclude = recent + daily_themes  # 同日テーマは必ず除外
        available = [t for t in themes if t["id"] not in exclude]
        if not available:  # テーマ8個 < 除外数の場合、同日のみ除外
            available = [t for t in themes if t["id"] not in daily_themes]
        theme = weighted_select(available, state["theme_use_counts"])
        daily_themes.append(theme["id"])

        day_slots.append({
            "slot": slot_name, "category": category,
            "type": post_type, "theme": theme["id"]
        })

    # Instagram候補選択（型4 > 型2 > 型1 > 型3）
    ig_priority = ["型4", "型2", "型1", "型3"]
    ig_slot = max(day_slots, key=lambda s: ig_priority.index(s["type"]) if s["type"] in ig_priority else 99)

    weekly_plan.append({"day": day, "slots": day_slots, "instagram_slot": ig_slot["slot"]})
```

決定結果をユーザーに週間カレンダー形式で提示:

```
📅 1週間の投稿計画（2026-03-24 〜 2026-03-30）

Day 1 (月):
  朝  有益/型2  T2 職務経歴書
  昼  有益/型4  T3 年収交渉
  夜  ENG/型1-A T7 メンタル        📷 IG

Day 2 (火):
  朝  有益/型1  T4 キャリアチェンジ
  昼  有益/型2  T1 面接対策
  夜  有益/型4  T8 スキル翻訳       📷 IG

Day 3 (水):
  朝  有益/型3  T6 退職タイミング
  昼  ENG/型1-B T7 メンタル
  夜  収益/型3  T5 エージェント     📷 IG

Day 4 (木):
  朝  有益/型1  T2 職務経歴書
  ...
```

### Step 1: 素材取得（21投稿分）

各投稿のテーマキーワードで creator-neo4j (bolt://localhost:7689) を一括検索。

**効率化**: 同じテーマの投稿はまとめて検索し、素材を分配する。

```cypher
MATCH (content)-[:IN_GENRE]->(g:Genre {name: '転職・副業'})
WHERE (content:Story OR content:Tip OR content:Fact)
  AND any(kw IN $keywords WHERE content.text CONTAINS kw)
RETURN labels(content)[0] AS type, content.name AS name, content.text AS text,
       elementId(content) AS id
ORDER BY rand()
LIMIT 30
```

| 型 | 優先素材 |
|----|---------|
| 型1 | Tip + Story |
| 型2 | Tip |
| 型3 | Story |
| 型4 | Fact |

使用済み素材（`state.used_material_ids`）を除外。
1週間で同じ素材を使わないよう、割り当て済み素材もトラッキング。

### Step 2: Threads 投稿文生成（21本）

**career-sister-writer スキルを読み込んでから**投稿文を生成する。
`.claude/skills/career-sister-writer/SKILL.md` と `references/post-examples.md` を参照。

**1日ずつ順番に生成する。** 1日分（3本）を生成したらユーザーに提示し、
問題なければ次の日に進む。重大な問題がなければ確認なしで7日分を一気に生成してもよい。

**スロット別の長さ目安:**
| スロット | 文字数 | 特徴 |
|---------|--------|------|
| 朝 | 200-300字 | 短く、すぐ読める |
| 昼 | 250-400字 | コメント誘導あり |
| 夜 | 350-500字 | じっくり読める長文 |

### Step 3: Instagram カルーセル生成（7本）

各日の Instagram 候補スロットの投稿をカルーセル化。

```bash
uv run --with playwright python scripts/render_carousel.py <slides.json> \
  --output-dir <draft_dir>/day_N/slot_M/carousel/
```

カルーセル JSON 形式:
```json
{
  "slides": [
    {"type": "title", "hook": "フック1行", "sub": "@career_sister"},
    {"type": "content", "heading": "見出し", "body": "本文", "number": "01"},
    {"type": "points", "heading": "まとめ", "items": ["ポイント1", "ポイント2"]},
    {"type": "cta", "message": "転職のリアルを\n毎日発信中", "account": "@career_sister"}
  ]
}
```

Instagram キャプション = Threads テキスト + ハッシュタグ（5-10個）

### Step 4: 下書き保存

```
creator/career_sister/drafts/week_YYYY-MM-DD/
├── day_1_mon/
│   ├── slot_1_morning/
│   │   ├── threads_post.md
│   │   └── material_source.json
│   ├── slot_2_noon/
│   │   ├── threads_post.md
│   │   └── material_source.json
│   └── slot_3_evening/
│       ├── threads_post.md
│       ├── instagram_caption.md
│       ├── slides.json
│       ├── carousel/slide_*.png
│       └── material_source.json
├── day_2_tue/
│   └── ...
├── ...
├── day_7_sun/
│   └── ...
└── meta.json
```

### Step 5: 状態更新

```python
total_new = days * 3  # 21
state["cycle_position"] = (state["cycle_position"] + total_new) % 10
state["total_posts"] += total_new
# 各カテゴリの型ローテーションを更新
for slot in all_slots:
    state["type_rotation"][slot["category"]] += 1
    state["recent_themes"].append(slot["theme"])
    state["theme_use_counts"][slot["theme"]] += 1
state["used_material_ids"].extend(all_used_ids)
state["current_cycle"] += total_new // 10
```

### Step 6: 結果報告

```
✅ 1週間分の下書き生成完了（2026-03-24 〜 2026-03-30）

  Threads:   21本（有益 15 / ENG 4 / 収益化 2）
  Instagram:  7本（カルーセル計 42スライド）
  サイクル:   2.1サイクル消化（サイクル1→3）

  テーマ分布:
    T1 面接対策:      3本
    T2 職務経歴書:    3本
    T3 年収交渉:      3本
    T4 キャリアチェンジ: 3本
    T5 エージェント:   2本
    T6 退職タイミング:  2本
    T7 メンタル:       3本
    T8 スキル翻訳:     2本

保存先: creator/career_sister/drafts/week_2026-03-24/

次のアクション:
  → 下書きを確認して修正
  → /career-sister-publish 2026-03-24  （1日ずつ投稿）
```

## meta.json（週次）

```json
{
  "week_start": "2026-03-24",
  "week_end": "2026-03-30",
  "status": "draft",
  "total_threads": 21,
  "total_instagram": 7,
  "cycles_consumed": 2.1,
  "days": [
    {
      "date": "2026-03-24",
      "day_label": "月",
      "status": "draft",
      "slots": [
        {
          "slot": "朝",
          "category": "有益",
          "type": "型2",
          "theme": "T2",
          "threads_char_count": 280,
          "instagram": false,
          "posted_at": null,
          "threads_permalink": null
        },
        {
          "slot": "昼",
          "category": "有益",
          "type": "型4",
          "theme": "T3",
          "threads_char_count": 350,
          "instagram": false,
          "posted_at": null
        },
        {
          "slot": "夜",
          "category": "エンゲージメント",
          "type": "型1-A",
          "theme": "T7",
          "threads_char_count": 400,
          "instagram": true,
          "carousel_slides": 5,
          "posted_at": null,
          "threads_permalink": null,
          "instagram_permalink": null
        }
      ]
    }
  ]
}
```

## 注意事項

- 投稿文生成時は必ず career-sister-writer スキルを参照すること
- 素材の text が空の場合はスキップして別の素材を取得
- Playwright が未インストールの場合は `uv run --with playwright playwright install chromium`
- カルーセル画像は 1080x1350px（Instagram推奨の4:5比率）
- 1週間分の生成はコンテキストが大きくなるため、1日ずつ順番に生成する
- アルゴリズム詳細は `creator/career_sister/posting_algorithm.md` を参照
