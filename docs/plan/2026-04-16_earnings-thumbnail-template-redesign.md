# 議論メモ: 決算サムネイル Pencil テンプレート再設計

**日付**: 2026-04-16
**対象スキル**: `article-earnings-thumbnail`
**対象ファイル**: `/Users/yukihata/Desktop/new.pen`（フレーム `CAXCU` / `har1R`）

## 背景・コンテキスト

note.com アプリ上で決算プレビュー/レビューのサムネイル文字（企業名・ティッカー）が小さくて見えにくいという課題。視認性向上を目的にテンプレートを再設計した。

## 議論のサマリー

### 第1案（採用せず、元に戻し）

- 全テキスト要素を拡大＋同色 stroke で疑似的に太字化
- CompanyName 64→84px、Ticker/Subtitle/EarningsDate も同様に拡大
- グレー文字を黒系に濃色化
- **結果**: 試作してユーザーが「やっぱり元に戻して」と判断、リバート

### 第2案（採用）

- CompanyName と Ticker を**削除**（企業識別はロゴのみで担保）
- Subtitle を2行ヒーロー化: `"Q1 YYYY\n決算プレビュー/レビュー"` 72px Inter 900（fixed-width 600, lineHeight 1.1）
- EarningsDate を大型化: 56px Inter 700、色 #111827（ほぼ黒）
- ロゴ左・テキスト右のレイアウトは維持、Separator も維持

## 決定事項

1. **CompanyName/Ticker テキストノード削除**: 企業ロゴがあれば識別十分。テキストを削ることでサブタイトルを大きく見せる余白が生まれる
2. **Subtitle 2行構造**: `{fiscal_quarter}\n{label}` 形式。Q1 2026（上段）/ 決算プレビュー（下段）で情報階層と視覚インパクトを両立
3. **日付の大型化**: 28px→56px で note アプリ縮小表示時も可読性確保
4. **`/Users/yukihata/Desktop/new.pen` をテンプレのソースオブトゥルースとする**: SKILL.md の子ノード構造・リセット操作・呼び出し例を新仕様に同期

## アクションアイテム

- [ ] 実際の決算記事で `/article-earnings-thumbnail` を走らせて note アプリでの見え方を確認（優先度: 高）
- [ ] 長い企業名（UnitedHealth 等）でもロゴ表示のみで識別可能か確認、必要ならロゴのアスペクト比調整（優先度: 中）
- [ ] Brand Badge（右下）と EarningsDate の垂直ギャップ（現在 ~14px）が狭く感じる場合、Badge 位置を調整（優先度: 低）

## 変更ファイル

| ファイル | 変更点 |
|---------|-------|
| `/Users/yukihata/Desktop/new.pen` | CAXCU/har1R: `6g00c`,`CFBpG`,`psqPo`,`8Zjbx` 削除、`VbtEH`,`xUTDJ`,`mlUJ1`,`9z5hB` 更新 |
| `.claude/skills/article-earnings-thumbnail/SKILL.md` | subtitle 生成式変更、子ノード対応表/構造図/リセット操作/呼び出し例を新仕様化 |

## 次回の議論トピック

- 実機確認後のフィードバックに基づく微調整
- 他カテゴリ（macro / stock / asset 等）のサムネイルテンプレ統一化の検討
