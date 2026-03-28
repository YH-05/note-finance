# 議論メモ: auto_poster.py 3バグ修正 & career_sister 夜スロット手動投稿

**日付**: 2026-03-28
**参加**: ユーザー + AI

## 背景・コンテキスト

career_sister のlaunchd自動投稿(07:30/12:30/20:30)が登録済みだったが、20:30の夜スロットが投稿されていなかった。
ログには `posted: 0, skipped: 0, failed: 0` と出力されており、エラーなく何もしない状態だった。

## 議論のサマリー

lauchd設定・スクリプト・ログを調査し、3つのバグを特定・修正した。

### Bug 1: `_detect_week_dir` が来週を選択する

**場所**: `scripts/auto_poster.py` L621-633

**原因**:
- 次週の下書きフォルダ `week_2026-03-31` が既に作成済み
- `_detect_week_dir(None)` が「名前順で最新」を選ぶため来週を選択
- 来週の meta.json には今日(2026-03-28)が存在しない → `day_label` 空 → `slot_file` None → スキップ

**修正**: `week_start <= today_str` フィルタを追加

```python
# 修正前
candidates = sorted([d for d in ... if d.name.startswith("week_")], ...)

# 修正後
today_str = datetime.now(tz=JST).strftime("%Y-%m-%d")
candidates = sorted([
    d for d in ...
    if d.is_dir()
    and re.fullmatch(r"week_\d{4}-\d{2}-\d{2}", d.name)
    and d.name[5:] <= today_str  # week_start <= today
], ...)
```

### Bug 2: NASマウント時に `creator/` パスが見つからない

**場所**: `scripts/auto_poster.py` L1740, L1470

**原因**:
- `.env` に `DATA_ROOT=/Volumes/NeoData/note-finance-data` が設定されている
- `uv run` が `.env` を自動読み込みするため、`get_data_root()` が NAS パスを返す
- `get_path("..") = /Volumes/NeoData/note-finance-data/..` = `/Volumes/NeoData/`
- `creator_root = /Volumes/NeoData/creator/career_sister` → 存在しない
- `DraftReader._detect_week_dir`: `if not self._drafts_root.exists(): return None` → None → 早期 return

**修正**: `get_path("..")` → `get_project_root()` に変更（`creator/` と `logs/` の両方）

```python
# 修正前
creator_root = get_path("..") / "creator" / account
log_path = get_path("..") / "logs" / "auto_poster.jsonl"

# 修正後
creator_root = get_project_root() / "creator" / account
log_path = get_project_root() / "logs" / "auto_poster.jsonl"
```

### Bug 3: `_print_dry_run` で `SLOT_TIME_MAP` 未定義 NameError

**場所**: `scripts/auto_poster.py` L2046

**原因**:
- `SLOT_TIME_MAP` という変数は未定義
- 実際には `SLOT_TIME_MAP_CAREER_SISTER` / `SLOT_TIME_MAP_MITSUKI` / `SLOT_TIME_MAP_KUROTO_AREA` が定義されている
- dry-run 時にクラッシュしていたが、エラーが標準エラーに出力されず見えていなかった

**修正**: `_get_slot_time_map(account)` に変更（`_print_dry_run` は `account` を引数で受け取っている）

```python
# 修正前
time_str = SLOT_TIME_MAP.get(slot_name, "?:??")

# 修正後
slot_time_map = _get_slot_time_map(account)
time_str = slot_time_map.get(slot_name, "?:??")
```

## 決定事項

1. `_detect_week_dir` の週選択を「名前順最新」から「`week_start <= today` の最新」に変更
2. `creator/` と `logs/` のパス解決を `get_project_root()` で固定（DATA_ROOT に依存しない）
3. `_print_dry_run` のスロット時刻マップを `_get_slot_time_map(account)` で取得

## アクションアイテム

- なし（全バグ修正済み・投稿完了）

## 結果

- 修正後、`--force-slot S3` で夜スロットを手動投稿
- threads_permalink: https://www.threads.com/@career_sister/post/DWbgSpXGJWR
- 翌日からの自動投稿(07:30/12:30/20:30)に修正が反映される

## 次回の議論トピック

- 来週(week_2026-03-31)の自動投稿が正常に動作するか確認
- kuroto_area / mitsuki にも同じバグがないか確認（同じコードを使用しているため影響なし）
