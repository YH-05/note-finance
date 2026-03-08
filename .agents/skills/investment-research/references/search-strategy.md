# リサーチ検索戦略

参照: `.agents/skills/web-search/SKILL.md`（Web検索ツール選択基準）

## テーマ種別ごとのソース優先順位

### 個別銘柄テーマ（例: "NVIDIA AI需要"）
1. SEC Edgar（10-K, 10-Q, 8-K）
2. WebSearch（決算レポート、アナリスト分析）
3. RSS（登録済み金融フィード）
4. Reddit（r/stocks, r/investing の議論）

### マクロ経済テーマ（例: "日銀利上げ影響"）
1. WebSearch（中銀発表、経済分析）
2. RSS（マクロ経済フィード）
3. Reddit（r/economics, r/investing の議論）
4. SEC Edgar（使用しない）

### セクターテーマ（例: "半導体サプライチェーン"）
1. WebSearch（業界分析、サプライチェーンニュース）
2. SEC Edgar（主要企業の filing）
3. RSS（セクター別フィード）
4. Reddit（r/semiconductors 等の専門サブ）

### 投資戦略テーマ（例: "バリュー投資 2026"）
1. WebSearch（戦略分析、パフォーマンス比較）
2. Reddit（r/investing, r/Bogleheads の議論）
3. RSS（投資戦略フィード）
4. SEC Edgar（使用しない）

## 深さ別クエリ予算

| 深度 | 合計検索回数 | Web検索 | RSS | Reddit | SEC Edgar |
|------|------------|---------|-----|--------|-----------|
| quick | 5-8 | 3-5 | 1-2 | 1 | 0-1 |
| standard | 12-18 | 6-10 | 2-3 | 2-3 | 1-2 |
| deep | 20-30 | 10-15 | 3-5 | 3-5 | 2-5 |

## クエリ構築ルール

1. テーマキーワードを英語/日本語に変換
2. `.agents/resources/search-templates/` から適切なテンプレートを選択
3. プレースホルダを実際の値に置換
4. 時間範囲を depth に応じて設定:
   - quick: 過去1週間
   - standard: 過去1ヶ月
   - deep: 過去3ヶ月
