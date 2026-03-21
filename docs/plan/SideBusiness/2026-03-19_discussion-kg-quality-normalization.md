# 議論メモ: KG品質チェック + Source Chain v2正規化

**日付**: 2026-03-19
**参加**: ユーザー + AI

## 背景・コンテキスト

research-neo4j の KG 品質を `/kg-quality-check` で計測。Overall 60.7/B だが、
accuracy カテゴリの Source Grounding が 0.000 という致命的な問題を発見。

## 議論のサマリー

### 問題の特定

- 20件のサンプル全てで `source_url = null` → Source Grounding = 0.000
- 原因: サンプリングクエリが `Fact ← STATES_FACT ← Chunk ← CONTAINS_CHUNK ← Source` チェーンを参照
- 実際のデータ: `Fact → EXTRACTED_FROM → Source`（632件が非v2パス）

### 計測基準を変えるか、データを変えるか

ユーザーの重要な指摘: 「計測方式を変えてスコアを上げるのはデータスヌーピング」

→ **計測基準は固定し、データをv2スキーマに合わせる** ことで合意。

### 正規化の実行

1. `scripts/normalize_source_chain.py` を作成（graph-queue JSON 生成）
2. `/save-to-graph` パイプライン経由で投入（neo4j-write-rules 準拠）
3. 旧 `EXTRACTED_FROM(Fact→Source)` 632件をrepair削除

## 決定事項

1. **計測基準の不変性**: KG品質の計測クエリを変更してスコアを上げることは禁止。データをスキーマに合わせる。
2. **パイプライン経由の正規化**: normalize_source_chain.py → graph-queue JSON → /save-to-graph で実行。

## 正規化結果

| 操作 | 件数 |
|------|------|
| Chunk 新規作成 | +145 |
| CONTAINS_CHUNK (Source→Chunk) | +145 |
| EXTRACTED_FROM (Fact/Claim→Chunk) | +826 |
| STATES_FACT 追加 | +254 |
| MAKES_CLAIM 追加 | +12 |
| 旧 EXTRACTED_FROM (→Source) 削除 | -632 |
| 孤立 Chunk 削除 | -140 (MCP params truncation で誤作成) |

### 構造指標の変化

| 指標 | Before | After |
|------|--------|-------|
| ノード数 | 5,610 | 5,755 (+145) |
| リレーション数 | 38,282 | 38,887 (+605) |
| orphan_ratio | 0.0020 | 0.0019 |
| avg_path_length | 3.70 | 3.55 |
| path_diversity | 0.031 | 0.048 (+57%) |

### 創発的発見（Phase 3）

1. **AI DC投資→エネルギー補助金→通信規制**: 3ドメイン横断仮説
2. **ISAT vs TLKM 戦略的分岐**: AI TechCo vs 資産軽量化の矛盾
3. **親会社レイヤーの構造的盲点**: CK Hutchison/Ooredoo(91トピック) のFact欠落
4. **学術↔金融クラスタの断絶**: Category Theory と金融分析が別の島

## アクションアイテム

- [ ] kg_quality_metrics.py の accuracy キャッシュ読み取り修正 (優先度: 高)
- [ ] Stance content 補完 — 74件全null (優先度: 中)
- [ ] 親会社データ補完 — CK Hutchison/Ooredoo/Axiata (優先度: 中)
- [ ] Coverage Span 拡大 — fetched_at 23/1651件のみ (優先度: 低)

## 技術的な学び

- MCP ツール経由で大量パラメータ(145件)を渡すとtruncateされる場合がある
  → Python 直接バッチ(`uv run python`)が確実
- graph-queue の `extracted_from_fact` は Fact→Chunk、`source_fact` は Source→Fact(STATES_FACT)
- `EXTRACTED_FROM` の方向: v2 スキーマでは Fact→Chunk が正、Fact→Source は非準拠

## 関連ファイル

| ファイル | 説明 |
|---------|------|
| `scripts/normalize_source_chain.py` | Source Chain 正規化スクリプト |
| `data/processed/kg_quality/snapshot_20260319.json` | 品質スナップショット |
| `data/processed/kg_quality/discovery_report_20260319.json` | 創発的発見レポート |
| `data/processed/kg_quality/accuracy_cache.json` | LLM-as-Judge 評価キャッシュ |
