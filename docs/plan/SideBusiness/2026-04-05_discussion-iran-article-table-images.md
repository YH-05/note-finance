# 議論メモ: イラン戦争記事 表画像生成 + generate_table_image 色指定機能追加

**日付**: 2026-04-05  
**参加**: ユーザー + AI

## 背景・コンテキスト

`articles/macro_economy/2026-04-04_iran-war-impact-japan-investors/` の記事に表画像が存在しなかった（`images/` ディレクトリ未作成）。記事内に「表は後工程で画像化予定」というプレースホルダーが2箇所あり、表画像を生成する必要があった。

## 実施内容

### 生成した表画像

1. **過去3回の石油危機の比較表** (`table_oil_crisis_comparison.png`)  
   1973年/1990年/2026年の原油価格変動を比較

2. **セクター別エネルギー価格影響表** (`table_sector_impact.png`)  
   航空・製造・電力ガス（負）/ 商社・防衛（正）/ 金融・保険（シナリオ依存）

### 発見した問題と修正

**問題1: 部分bold記法が失敗する**  
`"〜100ドル超 → **最高値126ドル**"` のようにセルの一部だけ `**...**` で囲んだ場合、`re.fullmatch` が失敗して `**` がそのまま表示される。  
→ JSONデータ設計を変更し、太字はセル全体を囲む場合のみ使用するルールを確立。

**問題2: セル単位の色指定機能がない**  
ユーザーから「▼ 負の影響」を赤、「▲ 正の影響」を緑にしたいという要求。  
→ `!!color!!text` 記法を新規追加。

## 決定事項

1. **`!!color!!text` 記法を `generate_table_image.py` に追加**（dec-2026-04-05-001）  
   - `_COLOR_MAP`: red/#dc2626, green/#16a34a, blue/#2563eb, orange/#ea580c  
   - `_parse_cell` で `re.fullmatch(r"!!(\w+|#[\da-fA-F]{3,6})!!(.*)", ...)` で検出  
   - `table.html` で `style="color: {{ cell.color }}; font-weight: 700;"` を inline 適用

2. **部分bold（`**...**` のセル内一部使用）は禁止**（dec-2026-04-05-002）  
   - `re.fullmatch` の仕様上、セル全体が `**...**` でないと失敗する  
   - JSONデータ設計時に必ずセル全体を太字または通常テキストに統一すること

3. **表画像のcaption（出典注記）は記載しない**（dec-2026-04-05-003）  
   - 根拠URLは記事本文のインラインリンクで表現する

## 変更ファイル

| ファイル | 変更内容 |
|---------|---------|
| `scripts/generate_table_image.py` | `!!color!!` 記法サポート追加、`_COLOR_MAP` 定義 |
| `scripts/templates/table.html` | `cell.color` が設定された場合の inline style 適用 |
| `articles/macro_economy/2026-04-04_iran-war-impact-japan-investors/03_published/article.md` | プレースホルダーを `![...](images/...)` 参照に置換 |
| `articles/macro_economy/2026-04-04_iran-war-impact-japan-investors/images/table_oil_crisis_comparison.png` | 新規生成 |
| `articles/macro_economy/2026-04-04_iran-war-impact-japan-investors/images/table_sector_impact.png` | 新規生成（赤/緑カラー適用） |

## 次のステップ

- 記事をnote.comに投稿する場合は `/article-publish` を使用
