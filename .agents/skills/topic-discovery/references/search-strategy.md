# トレンドリサーチ検索戦略

## クエリ配分（合計 8-12回）

| カテゴリ | 回数 | テンプレート参照 | 目的 |
|---------|------|----------------|------|
| 市場トレンド | 3 | `.claude/resources/search-templates/index-market.md` | 主要指数の動向、Bull/Bear判定 |
| セクター動向 | 2 | `.claude/resources/search-templates/sectors.md` | セクターローテーション、注目セクター |
| AI・テクノロジー | 2 | `.claude/resources/search-templates/ai-tech.md` | AI関連ニュース、半導体需要 |
| 日本市場 | 2 | `.claude/resources/search-templates/japan-market.md` | 国内市場、新NISA、個人投資家 |
| コンテンツギャップ | 1-3 | `.claude/resources/search-templates/competitor-content.md` | note.com の競合状況 |

## 検索実行ルール

1. **プレースホルダの置換**: `{YYYY}` → 現在の年、`{PERIOD}` → "this week" / "今週" 等
2. **言語選択**: グローバル情報は英語、国内情報は日本語
3. **フォールバック**: 結果が少ない場合はクエリを一般化（`"S&P 500 weekly January 2026"` → `"stock market this week"`）
4. **重複排除**: 同じソースが複数回出た場合は1件にまとめる

## 検索結果の処理

1. 各検索結果からキートピック・テーマを抽出
2. トピックの頻出度をカウント（複数ソースで言及 = 関心度高）
3. 既存 articles/ との重複チェック
4. トピック候補リストを作成し、Phase 3 に渡す
