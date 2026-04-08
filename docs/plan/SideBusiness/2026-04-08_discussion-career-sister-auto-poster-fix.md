# 議論メモ: career_sister 定期投稿ストップの調査・修正

**日付**: 2026-04-08
**参加**: ユーザー + AI

## 背景・コンテキスト

mac miniのlaunchdで実行しているcareer_sisterのThreads/インスタ定期投稿が4/5以降ストップしていた。
ログでは毎回 `skipped (already posted): 1 slots` と表示されており、「投稿済み」と誤認識していると思われた。

## 議論のサマリー

### 調査手順
1. `launchctl list | grep career` → 登録済み、exit code 0（正常終了）
2. ログ確認 → `skipped (already posted): 1 slots` が毎回出ている
3. `posting_state.json` → 最後の投稿は2026-04-04夜（Instagram失敗あり）
4. `meta.json` → 全スロットが `posted_at: null` で未投稿のはず
5. コード調査 → `skipped` の実体は `slot_file_not_found`（紛らわしいログ）
6. `get_slot_file` のロジック → `DAY_DIR_MAP_CAREER_SISTER` が月曜始まり固定

### 根本原因
`week_2026-04-05` が**土曜始まり**の週として生成されたため、フォルダ構造が：
```
day_1_sat, day_2_sun, day_3_mon, day_4_tue...
```
となっていた。しかし `DAY_DIR_MAP_CAREER_SISTER` は月曜始まり固定で `"火" → "day_2_tue"` と解決するため、実際の `day_4_tue` が見つからず `slot_file_not_found` でスキップされていた。

### 副次問題
`_print_dry_run` でも `get_slot_file` に `meta=meta` が渡されておらず、dry-runで常に「（なし）」と表示されていた。

## 決定事項

1. `get_slot_file` の曜日ディレクトリ解決を動的インデックス方式に変更（固定マッピング廃止）
   - `meta.json` の `days[]` の順序（インデックス）から通し番号を計算
   - `day_{N}_{英語曜日}` を動的生成することで任意の週開始曜日に対応
2. `_print_dry_run` の `get_slot_file` 呼び出しに `meta=meta` を追加

## アクションアイテム

- [ ] 週次ドラフト作成タイミングを毎週決まった曜日（例: 月曜）に統一する (優先度: 低)

## 参考情報

- 修正コミット: `fix(auto_poster): career_sisterのday_dir解決を動的インデックス方式に修正` (5eae69e)
- 修正コミット: `fix(auto_poster): _print_dry_runのget_slot_fileにmeta引数を追加` (52e55f6)
- 修正ファイル: `scripts/auto_poster.py` L742-L764, L2085
