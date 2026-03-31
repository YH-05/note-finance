# キャリアお姉さん 投稿スケジューリングアルゴリズム

## 概要

**Threads 3投稿/日 + Instagram 1投稿/日** の半自動パイプライン。
10投稿サイクル制でカテゴリ比率を保証し、日次スロットで投稿タイミングを管理する。

## 1. 日次スケジュール（3 Threads + 1 Instagram）

| スロット | 時間帯 | プラットフォーム | 狙い |
|---------|--------|---------------|------|
| 朝 | 7:00-8:00 | Threads | 通勤中のビジネスパーソンに有益情報 |
| 昼 | 12:00-13:00 | Threads | 昼休みにエンゲージメント |
| 夜 | 20:00-21:00 | Threads + Instagram | リラックスタイムにじっくり読むコンテンツ |

- **朝**: 常に有益投稿（短め、すぐ読める Tips 系）
- **昼**: カテゴリローテーション（有益 or ENG or 収益化）
- **夜**: 常に有益投稿（ストーリー系、じっくり読める）
- **Instagram**: 夜の投稿をカルーセル化（ストーリー系は画像映えする）

## 2. 10投稿サイクル（カテゴリ比率 7:2:1）

1サイクル = 10投稿 = 約3.3日分（3投稿/日）。

10投稿のカテゴリ配列:
```
Position:  1    2    3    4    5    6    7    8    9    10
Category: 有益  有益  ENG  有益  有益  有益  有益  ENG  収益  有益
```

日次スロットへのマッピング:
```
Day 1:
  朝 → Position 1 (有益)
  昼 → Position 2 (有益)
  夜 → Position 3 (ENG)     ← Instagram もこれをカルーセル化

Day 2:
  朝 → Position 4 (有益)
  昼 → Position 5 (有益)
  夜 → Position 6 (有益)    ← Instagram

Day 3:
  朝 → Position 7 (有益)
  昼 → Position 8 (ENG)
  夜 → Position 9 (収益化)  ← Instagram

Day 4 (新サイクル開始):
  朝 → Position 10 (有益)
  昼 → Position 1 (有益)    ← 次サイクル
  夜 → Position 2 (有益)    ← Instagram
```

## 3. 型ローテーション

各カテゴリ内で型を順番に使う。同じ型が連続しない。

```
有益投稿（7/10）:
  型1（結論→ストーリー→問いかけ）→ 型2（あるある→解決策）
  → 型5（市場データ→インサイト）→ 型4（データ→意外性）
  → 型3（失敗談→学び）→ 型5 → 型1 に戻る
  ※ 型5 は週最低3回使用すること（T9/T10テーマと組み合わせ）

エンゲージメント投稿（2/10）:
  型1-A（問いかけ + 選択肢）→ 型1-B（問いかけ + 自由回答）→ 型1-A に戻る

収益化投稿（1/10）:
  型3（失敗談→学び→解決したツール紹介）固定
```

### スロット × 型の推奨組み合わせ

| スロット | 推奨型 | 理由 |
|---------|--------|------|
| 朝 | 型2（あるある→解決策） or 型4（データ） | 短く読めてすぐ役立つ |
| 昼 | 型1（問いかけ）or ENG | 昼休みにコメントしやすい |
| 夜 | 型1（ストーリー）or 型3（失敗談） | じっくり読む長文向き |

## 4. テーマ選択アルゴリズム

### 4.1 テーマプール（8テーマ）

| ID | テーマ | neo4j キーワード | 重み |
|----|--------|-----------------|------|
| T1 | 面接対策 | 面接, 志望動機, 自己PR | 1.0 |
| T2 | 職務経歴書・書類 | 職務経歴書, 履歴書, 書類 | 1.0 |
| T3 | 年収・待遇交渉 | 年収, 給料, 交渉, 待遇 | 1.0 |
| T4 | キャリアチェンジ | 異業種, 未経験, キャリアチェンジ | 1.0 |
| T5 | 転職エージェント活用 | エージェント, 転職サイト, 求人 | 0.8 |
| T6 | 退職・転職タイミング | 退職, タイミング, 辞める | 0.8 |
| T7 | メンタル・マインドセット | 怖い, 不安, 悩む, 自信 | 1.2 |
| T8 | スキル・自己分析 | スキル, 強み, 翻訳, ポータブル | 1.0 |
| T9 | 転職市場データ | 求人数, 年収中央値, 有効求人倍率, 業界動向 | 1.5 |
| T10 | 業界別ルートマップ | SaaS, コンサル, メーカー→IT, 異業種ルート | 1.3 |

### 4.2 テーマ選択ルール

```python
def select_theme(state):
    # 1. 直近5投稿で使ったテーマを除外
    recent = state["recent_themes"][-5:]
    available = [t for t in THEMES if t["id"] not in recent]

    # 2. 使用回数が少ないテーマを優先（均等分散）
    counts = state["theme_use_counts"]
    min_count = min(counts[t["id"]] for t in available)
    candidates = [t for t in available if counts[t["id"]] <= min_count + 1]

    # 3. 重み付きランダム選択
    weights = [t["weight"] for t in candidates]
    return random.choices(candidates, weights=weights, k=1)[0]
```

### 4.3 同日テーマ重複ルール

1日3投稿で同じテーマが出ないよう、**日次テーマバッファ**を管理:
- 1日の最初の投稿: テーマ自由
- 2投稿目: 1投稿目と異なるテーマ
- 3投稿目: 1-2投稿目と異なるテーマ

## 5. 素材 ↔ 型のマッピング

| 投稿の型 | 優先素材タイプ | 理由 |
|---------|--------------|------|
| 型1（結論→ストーリー→問いかけ） | Tip + Story | ストーリーで共感→Tipで解決策 |
| 型2（あるある→解決策） | Tip | 具体的なHow-toが必要 |
| 型3（失敗談→学び） | Story | 実体験ベースが必須 |
| 型4（データ→意外性） | Fact | 数値データが必須 |
| 型5（市場データ→インサイト） | Fact + Tip | 求人トレンド・年収データ + 具体的な業界名・職種名が必須 |

素材選択時の重複排除:
- `used_material_ids` に記録済みの素材は除外
- 全素材の70%使用済みでリセット（再利用可能に）

## 6. Instagram カルーセル選択ルール

1日3本の Threads 投稿から1本を Instagram カルーセル化する。

**選択優先度**:
1. 型4（データ→意外性）: 数字がスライドで映える
2. 型2（あるある→解決策）: ステップ形式がカルーセル向き
3. 型1（結論→ストーリー→問いかけ）: ストーリーが読みやすい
4. 型3（失敗談→学び）: 感情的な共感がビジュアルで増幅
5. ENG / 収益化: テキストベースなのでカルーセル化しにくい → スキップ可

ENG / 収益化の日は、その日の有益投稿（朝 or 夜）をカルーセル化する。

## 7. 状態管理

`posting_state.json` で全状態を管理:

```json
{
  "current_cycle": 1,
  "cycle_position": 0,
  "total_posts": 0,
  "daily_schedule": {
    "slots": ["朝", "昼", "夜"],
    "today_themes": [],
    "today_posts": []
  },
  "type_rotation": {
    "有益": 0,
    "エンゲージメント": 0,
    "収益化": 0
  },
  "recent_themes": [],
  "theme_use_counts": {
    "T1": 0, "T2": 0, "T3": 0, "T4": 0,
    "T5": 0, "T6": 0, "T7": 0, "T8": 0
  },
  "used_material_ids": [],
  "post_history": []
}
```

## 8. /career-sister-draft の1週間分生成フロー

`/career-sister-draft` を1回実行すると、**1週間分（Threads 21本 + Instagram 7本）** を一括生成:

```
┌─────────────────────────────────────────────────────┐
│ 1. posting_state.json 読み込み                        │
├─────────────────────────────────────────────────────┤
│ 2. 21投稿分（7日×3スロット）のパラメータを一括決定      │
│    Day1-7 × (朝/昼/夜) → カテゴリ → 型 → テーマ      │
│    （同日テーマ重複チェック + 週間テーマ均等分散）       │
│    → 週間カレンダーをユーザーに提示                     │
├─────────────────────────────────────────────────────┤
│ 3. 1日ずつ順番に素材取得 + テキスト生成                 │
│    → creator-neo4j から型に最適な素材取得              │
│    → career-sister-writer で Threads テキスト生成      │
│    → Instagram 候補選択 + カルーセル生成               │
│    （7日分を繰り返す）                                 │
├─────────────────────────────────────────────────────┤
│ 4. 下書き保存                                         │
│    drafts/week_YYYY-MM-DD/                           │
│    ├── day_1_mon/ ... day_7_sun/                     │
│    │   ├── slot_1_morning/threads_post.md            │
│    │   ├── slot_2_noon/threads_post.md               │
│    │   └── slot_3_evening/                           │
│    │       ├── threads_post.md                       │
│    │       ├── instagram_caption.md                  │
│    │       └── carousel/slide_*.png                  │
│    └── meta.json                                     │
├─────────────────────────────────────────────────────┤
│ 5. posting_state.json 更新                            │
│    cycle_position += 21                              │
│    recent_themes に21テーマ追加                        │
│    used_material_ids に使用素材追加                    │
└─────────────────────────────────────────────────────┘
```

## 9. meta.json（日次）

```json
{
  "date": "2026-03-24",
  "status": "draft",
  "cycle": 1,
  "cycle_positions": [1, 2, 3],
  "slots": [
    {
      "slot": "朝",
      "category": "有益",
      "type": "型2",
      "theme": "T2",
      "threads_post": "slot_1_morning/threads_post.md",
      "instagram": false,
      "posted_at": null,
      "threads_permalink": null
    },
    {
      "slot": "昼",
      "category": "有益",
      "type": "型4",
      "theme": "T3",
      "threads_post": "slot_2_noon/threads_post.md",
      "instagram": false,
      "posted_at": null,
      "threads_permalink": null
    },
    {
      "slot": "夜",
      "category": "ENG",
      "type": "型1-A",
      "theme": "T7",
      "threads_post": "slot_3_evening/threads_post.md",
      "instagram": true,
      "instagram_caption": "slot_3_evening/instagram_caption.md",
      "carousel_slides": 5,
      "posted_at": null,
      "threads_permalink": null,
      "instagram_permalink": null
    }
  ]
}
```

## 10. 素材枯渇予測

3投稿/日 × 30日 = 90投稿/月

| 素材タイプ | 在庫 | 月間消費 | 持続期間 |
|-----------|------|---------|---------|
| Fact | 261件 | ~25件 | ~10ヶ月 |
| Tip | 178件 | ~40件 | ~4.5ヶ月 |
| Story | 48件 | ~15件 | ~3ヶ月 |

**Story が最も早く枯渇する**（約3ヶ月）。対策:
- creator-enrichment で Story を継続追加（12%→25%目標）
- 1素材から複数の切り口で投稿を生成（同じ Story の別角度）
- used_material_ids の70%リセットルールで再利用

## 11. 将来拡張: フィードバックループ

Phase 2 で実装:
```
投稿24h後 → Threads/Instagram Insights API でメトリクス取得
  → テーマ × 型 × スロット のエンゲージメントマトリクス構築
  → 高エンゲージメント組み合わせの重みを上げる
  → 低エンゲージメント組み合わせを分析→改善
```

必要: App Review 承認後（threads_keyword_search / Instagram Public Content Access）
