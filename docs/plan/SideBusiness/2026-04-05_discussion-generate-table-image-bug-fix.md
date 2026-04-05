# 議論メモ: generate-table-image _parse_cell バグ修正

**日付**: 2026-04-05
**参加**: ユーザー + AI

## 背景・コンテキスト

VZ記事（`articles/stock_analysis/2026-03-08_tech-to-high-dividend-vz/`）の
table_01.png / table_02.png を確認したところ、セル内に `**` の文字がそのまま
表示されているものがあった。

## 原因

`scripts/generate_table_image.py` の `_parse_cell` 関数が `re.fullmatch` を使用。

```python
# 修正前: fullmatch では "**val**（補足）" 形式がマッチしない
bold_match = re.fullmatch(r"\*\*(.+?)\*\*", value.strip())
```

`"**1.1M**（2019年来最高）"` のように `**...**` の後ろに追加テキストがある場合、
fullmatch がマッチせず `**` がそのまま画像内に表示される。

## 影響箇所（JSON内）

| ファイル | 問題のあったセル |
|---------|----------------|
| `.tmp/table_vz_01.json` | `"**1.1M**（2019年来最高）"` |
| `.tmp/table_vz_01.json` | `"**$25B**（3年程度で実行）"` |
| `.tmp/table_vz_02.json` | `"**5.7M**（業界最大）"` |

## 決定事項

1. `_parse_cell` を `re.fullmatch` → `"**" in value` + `re.sub` 方式に変更。
   `**` が文字列のどこにあってもセル全体を太字にして `**` を除去する。

2. SKILL.md に `"**値**（補足説明）"` 形式の記法を追記。

## 修正内容

```python
# 修正後: ** が含まれればどこでも太字処理
if "**" in value:
    text = re.sub(r"\*\*(.+?)\*\*", r"\1", value.strip())
    return {"text": text, "bold": True, "align": "left", "color": None}
```

## 対応済み作業

- [x] `scripts/generate_table_image.py` の `_parse_cell` を修正
- [x] `.claude/skills/generate-table-image/SKILL.md` にセル記法を追記
- [x] VZ記事の `table_01.png` / `table_02.png` を修正後スクリプトで再生成
- [x] コミット `a64e93e` でプッシュ済み

## 次回の議論トピック

- JSON の `**` 記法で部分太字（複数 `**...**` が混在する場合）が必要になれば
  HTML テンプレート側で `<strong>` タグ展開に対応することを検討
