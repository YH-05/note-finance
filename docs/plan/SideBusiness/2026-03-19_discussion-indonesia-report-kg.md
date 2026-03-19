# 議論メモ: Indonesia Equity Strategy レポートの KG 投入

**日付**: 2026-03-19
**参加**: ユーザー + AI

## 背景・コンテキスト

ASEAN市場調査の一環として、Nomura の "Indonesia Equity Strategy - Turning over a new leaf" (2025-12-06, 96ページ) を research-neo4j にナレッジグラフとして投入する作業を実施。

## 処理フロー

### Phase 1: PDF → Markdown (LlamaParse)

- **入力**: `/Volumes/personal_folder/Equity_Research/M_ASEAN-market/Anchor report - Indonesia.pdf`
- **ツール**: LlamaParse REST API (Agentic tier, 10 credits/page)
- **消費クレジット**: 960 (96ページ × 10)
- **出力**: `Anchor report - Indonesia_c8bec1af/report.md` (318,806文字)
- **所要時間**: 約5分

### Phase 2: Knowledge Extraction

- **自動パイプライン (pdf-extraction) 失敗**: `ClaudeCodeProvider.extract_knowledge` → `claude_agent_sdk` に `extract_knowledge` 属性なし
- **代替パス**: サブエージェント (knowledge-extractor) でレポート全文を読み取り、web-research 形式の入力 JSON を生成
- **抽出結果**: 109 Facts, 72 Entities, 4 Topics

### Phase 3: Graph-Queue 生成

```bash
uv run python scripts/emit_graph_queue.py --command web-research --input .tmp/indonesia-report-input.json
```

### Phase 4: Neo4j 投入 (research-neo4j, bolt://localhost:7688)

MCP ツール (`mcp__neo4j-research__research-write_neo4j_cypher`) で MERGE 投入。

## 投入統計

| 項目 | 件数 |
|------|------|
| Source ノード | 1 |
| Topic ノード | 4 |
| Entity ノード | 72 (Company: 34, Macro: 11, Sector: 10, Commodity: 6, Org: 6, Index: 3, Country: 2) |
| Fact ノード | 109 |
| STATES_FACT | 109 |
| TAGGED | 440 |
| RELATES_TO | 184 |
| EXTRACTED_FROM | 109 |
| **合計ノード** | **186** |
| **合計リレーション** | **842** |

## 抽出されたエンティティ（主要）

### 個別銘柄 (Top Picks 9銘柄 + 関連)
AMRT, KLBF, CMRY, AKRA, ARCI, NCKL, AUTO, ASSA, MIDI, BBCA, BMRI, BBRI, BBNI, BRIS, TLKM, ISAT, MYOR, ICBP, INDF, MLBI, SMSM, AADI, MEDC, TAPG, PWON, CTRA, AVIA, ARNA, HEAL, MIKA, JPFA, CPIN, MDKA, INCO

### セクター
Banking, Telco, Auto, FMCG, Commodities, Property, Healthcare, Poultry, Retail, Textile & Apparel

### マクロ指標
GDP, Inflation, Labor Market, Household Spending, Consumer Confidence, Credit Growth, Current Account, Sovereign Bonds, IDR

### コモディティ
Crude Oil, Coal, Nickel, Gold, Copper, CPO

## 決定事項

1. **セルサイドレポートの変換にはLlamaParse Agentic tierを使用する** — 96ページ級の複雑なレイアウトに対応するため
2. **pdf-extraction CLI失敗時はweb-researchパイプラインを代替パスとして使用する** — ClaudeCodeProviderのエラー回避

## アクションアイテム

- [ ] `ClaudeCodeProvider.extract_knowledge` の `claude_agent_sdk` エラーを修正する (優先度: 中)
- [ ] ASEAN市場の他レポート（Malaysia, Thailand, Philippines等）も同様にKG投入する (優先度: 低)

## 成果物パス

| 成果物 | パス |
|--------|------|
| Markdown変換結果 | `/Volumes/personal_folder/Equity_Research/M_ASEAN-market/Anchor report - Indonesia_c8bec1af/report.md` |
| メタデータ | `/Volumes/personal_folder/Equity_Research/M_ASEAN-market/Anchor report - Indonesia_c8bec1af/metadata.json` |
| チャンク | `/Volumes/personal_folder/Equity_Research/M_ASEAN-market/Anchor report - Indonesia_c8bec1af/chunks.json` |
| 入力JSON | `.tmp/indonesia-report-input.json` |
