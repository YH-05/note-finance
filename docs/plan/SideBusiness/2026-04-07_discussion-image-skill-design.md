# 議論メモ: 画像生成スキルの改善とデザイン探索

**日付**: 2026-04-07
**参加**: ユーザー + AI

## 背景・コンテキスト

株投資ラボの記事画像（表・概念図）の品質向上を目的に、generate-table-imageの改善と新スキルgenerate-concept-imageの作成を行った。

## 議論のサマリー

### Phase 1: generate-table-image 改善

- フォントサイズ 15→20px に拡大
- セルパディング縮小（12px 20px → 14px 16px）
- `white-space: nowrap` 削除 → 自動折り返し
- ビューポートを固定幅 620px に変更（note.comコンテンツ幅最適化）
- 列数上限 3 を追加（超過でValueError）

### Phase 2: generate-concept-image 新規作成

4レイアウト（grid/matrix/comparison/steps）のHTML/CSS+Playwright概念図スキルを作成。

### Phase 3: デザイン探索（試行錯誤）

以下のデザインを順に試行したが、いずれも「AIっぽい」と評価された:

1. **初期版**: 白背景+薄グレーカード+絵文字アイコン → AIっぽい
2. **絵文字削除版**: アクセントカラーボーダーのみ → まだAIっぽい
3. **Pencil MCP版**: Soft Bento + Carbon Frost → Pencilの制約で差別化困難
4. **ボールドカラー型**: セルをアクセントカラーで塗りつぶし+白文字 → AIっぽい
5. **ミニマル型**: Zen Kaku Gothic New + 罫線のみ → シンプルすぎ
6. **データコントラスト型**: 大きな番号+3段階フォントウェイト → 改善されたが採用見送り
7. **note.com参考型**: 濃紺ヘッダーバー+水色背景+白カード枠線 → note.com実例に近いが不採用

### Phase 4: 結論

概念図スキルは不採用。記事内の図解は全てgenerate-table-image（表）で統一する方針に決定。

## 決定事項

1. **generate-table-image改善**: フォント20px、固定幅620px、列数上限3、自動折り返し
2. **generate-concept-image不採用**: AIっぽいデザインから脱却できず、表で統一
3. **出典非記載ルール**: 表内（caption含む）に出典・データソースを記載しない。記事本文で対応

## デザイン調査で得た知見

note.com/Instagram金融系アカウントの調査から得られた「AIっぽくない」デザインの原則:

- グラデーション背景を使わない（ベタ塗り）
- box-shadow は最小限（0 1px 3px のみ or なし）
- フォントウェイトの差を大きく（900 vs 400 vs 300）
- 色数 3色以内
- 余白に不均一さを入れる
- border-radius を要素ごとに変える
- 1要素だけ「はみ出し」を作る

## 変更ファイル

- `scripts/generate_table_image.py` — デフォルト値・バリデーション・ビューポート
- `scripts/templates/table.html` — CSS改善
- `scripts/generate_concept_image.py` — 新規作成（不採用だが残存）
- `scripts/templates/concept.html` — 新規作成（不採用だが残存）
- `.claude/skills/generate-table-image/SKILL.md` — ドキュメント更新
- `.claude/skills/generate-concept-image/SKILL.md` — 新規作成

## 次回の議論トピック

- generate-concept-imageを削除するか、将来のデザイン改善に備えて残すか
- Figma MCP導入でデザインの自由度を上げるかの検討
- BLK記事の投稿判断
