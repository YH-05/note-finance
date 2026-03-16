// ============================================================
// 銘柄横断比較クエリ集（Metric マスター活用）
// 対象DB: research-neo4j (bolt://localhost:7688)
// ============================================================

// --- 1. 任意の2銘柄×全指標の比較テーブル ---
// ticker1, ticker2 を変えれば任意のペアで使える
MATCH (met:Metric)<-[:MEASURES]-(dp)-[:RELATES_TO]->(e:Entity),
      (dp)-[:FOR_PERIOD]->(fp:FiscalPeriod)
WHERE e.ticker IN ['ISAT IJ', 'TLKM IJ']
WITH met.display_name AS metric, met.category AS cat,
     fp.period_label AS period, e.ticker AS ticker, dp.value AS val
ORDER BY cat, metric, period
RETURN metric, cat, period,
       reduce(s = '', x IN collect(ticker + '=' + toString(val)) | s + x + '  ') AS comparison;

// --- 2. 特定指標の時系列比較（例: EBITDA Margin） ---
MATCH (met:Metric {canonical_name: 'ebitda_margin'})<-[:MEASURES]-(dp)-[:RELATES_TO]->(e:Entity),
      (dp)-[:FOR_PERIOD]->(fp:FiscalPeriod)
WHERE e.ticker IN ['ISAT IJ', 'TLKM IJ']
RETURN e.ticker AS ticker, fp.period_label AS period, dp.value AS value
ORDER BY fp.period_label, e.ticker;

// --- 3. 両銘柄で比較可能な指標の一覧 ---
MATCH (met:Metric)<-[:MEASURES]-(:FinancialDataPoint)-[:RELATES_TO]->(e1:Entity {ticker: 'ISAT IJ'})
MATCH (met)<-[:MEASURES]-(:FinancialDataPoint)-[:RELATES_TO]->(e2:Entity {ticker: 'TLKM IJ'})
RETURN met.display_name AS metric, met.canonical_name, met.category, met.unit_standard
ORDER BY met.category, met.display_name;

// --- 4. カテゴリ別の指標カバレッジ ---
MATCH (met:Metric)<-[:MEASURES]-(dp)-[:RELATES_TO]->(e:Entity)
WHERE e.ticker IN ['ISAT IJ', 'TLKM IJ']
RETURN met.category AS category, met.display_name AS metric,
       collect(DISTINCT e.ticker) AS covered_tickers,
       count(dp) AS data_points
ORDER BY met.category, met.display_name;

// --- 5. 未分類 FinancialDataPoint（Metricに紐づいていない） ---
MATCH (dp:FinancialDataPoint)
WHERE NOT (dp)-[:MEASURES]->(:Metric)
OPTIONAL MATCH (dp)-[:RELATES_TO]->(e:Entity)
RETURN dp.metric_name, dp.value, dp.unit, e.ticker
ORDER BY dp.metric_name;

// --- 6. 全銘柄横断: 指定Metricのランキング ---
// 例: EBITDA Margin の直近比較
MATCH (met:Metric {canonical_name: 'ebitda_margin'})<-[:MEASURES]-(dp)-[:RELATES_TO]->(e:Entity),
      (dp)-[:FOR_PERIOD]->(fp:FiscalPeriod {period_label: 'FY2024'})
RETURN e.name, e.ticker, dp.value AS ebitda_margin
ORDER BY dp.value DESC;

// --- 7. ISAT↔TLKM 全接続サブグラフ（Metric経由を含む可視化） ---
MATCH (isat:Entity {ticker: 'ISAT IJ'}),
      (tlkm:Entity {ticker: 'TLKM IJ'})
MATCH path = (isat)<-[:RELATES_TO|MEASURES*1..2]-(bridge)-[:RELATES_TO|MEASURES*1..2]->(tlkm)
RETURN path
LIMIT 100;

// --- 8. 同一Metric + 同一Period で並べて可視化 ---
MATCH (met:Metric)<-[:MEASURES]-(dp_i)-[:RELATES_TO]->(isat:Entity {ticker: 'ISAT IJ'}),
      (met)<-[:MEASURES]-(dp_t)-[:RELATES_TO]->(tlkm:Entity {ticker: 'TLKM IJ'}),
      (dp_i)-[:FOR_PERIOD]->(fp:FiscalPeriod)<-[:FOR_PERIOD]-(dp_t)
RETURN met.display_name AS metric, fp.period_label AS period,
       dp_i.value AS ISAT, dp_t.value AS TLKM,
       CASE WHEN dp_t.value <> 0 THEN round((dp_i.value / dp_t.value - 1) * 100, 1) ELSE null END AS diff_pct
ORDER BY met.canonical_name, fp.period_label;
