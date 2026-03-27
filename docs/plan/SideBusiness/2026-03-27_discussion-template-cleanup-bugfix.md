# 議論メモ: テンプレート整理・曜日計算バグ修正

**日付**: 2026-03-27
**参加**: ユーザー + AI
**Neo4j Discussion ID**: disc-2026-03-27-template-cleanup-bugfix

---

## 背景・コンテキスト

キャリアお姉さんの week_2026-03-24 下書き投稿作業中に、テンプレートファイルの散在と曜日ラベルの誤りが発覚した。

---

## 作業内容

### 1. テンプレートファイルの整理

**問題**: `templates/career_sister/carousel.html` と `creator/career_sister/templates/` の2箇所に分散していた。

**対応**:
- `templates/career_sister/carousel.html` → `creator/career_sister/templates/carousel.html` に移動
- `scripts/render_carousel.py:32` の `TEMPLATE_PATH` を新パスに更新
  - 変更前: `Path(__file__).parent.parent / "templates" / "career_sister" / "carousel.html"`
  - 変更後: `Path(__file__).parent.parent / "creator" / "career_sister" / "templates" / "carousel.html"`
- 旧 `templates/career_sister/` は `trash/templates_20260327/` に退避

**結果**: `.pen`（Pencilデザイン原案）と `.html`（レンダリング用）が `creator/career_sister/templates/` に統一。

---

### 2. キャリアお姉さん 3/27 夜スロット投稿完了

- カテゴリ: エンゲージメント / 型1-A / T4（キャリアチェンジ）
- Threads permalink: `https://www.threads.com/@career_sister/post/DWYeH5nkuUZ`
- meta.json のステータスを published に更新

---

### 3. meta.json 曜日ラベルバグ修正

**問題**: `week_2026-03-24/meta.json` の `day_label` が全7日間で1日ずれていた。
- 開始日 3/24（火曜）を月曜固定と仮定してハードコードしていたため。

**修正内容**:
| 日付 | 修正前 | 修正後 |
|------|--------|--------|
| 3/24 | 月 | 火 |
| 3/25 | 火 | 水 |
| 3/26 | 水 | 木 |
| 3/27 | 木 | 金 |
| 3/28 | 金 | 土 |
| 3/29 | 土 | 日 |
| 3/30 | 日 | 月 |

---

### 4. 3ドラフトコマンドの曜日計算バグ修正

**問題**: 以下の3コマンドがディレクトリ名・day_label を `mon` / `月` 固定でハードコードしていた。

- `.claude/commands/career-sister-draft.md`
- `.claude/commands/mitsuki-draft.md`
- `.claude/commands/kuroto-draft.md`

**修正**: 全3コマンドに「曜日計算（必須）」セクションを追加。

```python
from datetime import date, timedelta

start = date.fromisoformat(start_date)  # 例: "2026-03-24"
WEEKDAY_JA = ["月", "火", "水", "木", "金", "土", "日"]
WEEKDAY_EN = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]

for day_offset in range(7):
    d = start + timedelta(days=day_offset)
    ja = WEEKDAY_JA[d.weekday()]   # 0=月, 6=日
    en = WEEKDAY_EN[d.weekday()]
    dir_name = f"day_{day_offset + 1}_{en}"   # "day_1_tue"
    day_label = ja                              # "火"
```

---

## 決定事項

1. **テンプレートパス統一**: carousel.html は `creator/career_sister/templates/` に一元管理
   - Decision ID: `dec-2026-03-27-template-path-reorganization`

2. **曜日計算の標準化**: 全ドラフトコマンドで `date.weekday()` ベースの動的計算を義務付け
   - Decision ID: `dec-2026-03-27-weekday-calculation-standard`

---

## アクションアイテム

- [ ] キャリアお姉さん week_2026-03-24 残り9スロット（3/28・3/29・3/30）を投稿 (優先度: 高)
  - ActionItem ID: `act-2026-03-27-career-sister-remaining-posts`

---

## 次回の議論トピック

- 3/28〜3/30の下書きを投稿後、次週（week_2026-03-31）のドラフト一括生成
- みつき・玄人領域の初週ドラフト生成（`/mitsuki-draft`, `/kuroto-draft`）

## 参考情報

- `scripts/render_carousel.py`: carousel.html参照スクリプト
- `creator/career_sister/drafts/week_2026-03-24/meta.json`: 投稿スケジュール管理
