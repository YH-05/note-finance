# investment-research スキル

特定の投資テーマについてマルチソースで深掘りリサーチし、記事素材を集めるスキル。

## パラメータ

| パラメータ | 必須 | デフォルト | 説明 |
|-----------|------|-----------|------|
| --theme | 必須 | - | リサーチテーマ（例: "NVIDIA AI需要", "日銀利上げ影響", "新NISA投資動向"） |
| --depth | - | standard | 調査深度。quick: 5-8検索, standard: 12-18検索, deep: 20-30検索 |
| --language | - | both | 検索言語。en: 英語のみ, ja: 日本語のみ, both: 両方 |

## 処理フロー

### Phase 1: マルチソース検索

参照: `references/search-strategy.md`（テーマ種別ごとのソース優先順位）
参照: `.agents/skills/web-search/SKILL.md`（Web検索ツール選択基準）

テーマの種別を判定し、最適なソース組み合わせで検索:

1. **Web検索**: 最新ニュース・分析記事を検索（ツール選択は web-search スキル参照）
   - 日本語テーマ → Gemini Search 推奨
   - 英語テーマ → Tavily MCP 推奨
   - `.agents/resources/search-templates/` のテンプレートを活用
2. **RSS MCP** (`mcp__rss__rss_search_items`): 登録済みフィードからテーマ関連記事を検索
   - ToolSearch でロード、利用不可時はスキップ
3. **Reddit MCP** (`mcp__reddit__*`): 投資家コミュニティの議論を収集
   - r/investing, r/stocks, r/wallstreetbets 等
   - ToolSearch でロード、利用不可時はスキップ
4. **SEC Edgar MCP** (`mcp__sec-edgar-mcp__*`): 個別銘柄テーマ時にSEC filingを参照
   - ToolSearch でロード、利用不可時はスキップ

### Phase 2: ファクト整理

参照: `references/source-reliability.md`（ソース信頼度）

1. 収集した情報を時系列で整理
2. 数値データ（株価、業績、経済指標等）を抽出
3. 専門家見解・アナリストコメントを分類
4. 各ファクトにソース信頼度（Tier 1-4）を付与

### Phase 3: 論点抽出

1. **ブル（強気）要因**: テーマに対するポジティブな見方・根拠
2. **ベア（弱気）要因**: テーマに対するネガティブな見方・根拠
3. **ニュートラル**: 中立的な視点・不確実性要因
4. 各論点にエビデンス（ソース付き）を紐づけ

### Phase 4: リサーチノート出力

参照: `references/output-format.md`（出力テンプレート）

`.tmp/investment-research/{theme_slug}_{YYYYMMDD-HHMM}.md` にリサーチノートを出力。

## MCP フォールバック戦略

参照: `.agents/skills/web-search/SKILL.md`（フォールバック戦略）

MCPツールは ToolSearch でロードを試みる。利用不可の場合:
- RSS MCP → Web検索で代替（フィードURLを直接検索）
- Reddit MCP → Web検索で `site:reddit.com` クエリ
- SEC Edgar MCP → Web検索で `site:sec.gov` クエリ

深度別の最低検索回数:
- quick: 5回以上
- standard: 10回以上
- deep: 15回以上
