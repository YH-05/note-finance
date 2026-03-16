// Research Neo4j - KG v2 スキーマ初期化
// 銘柄・マクロ調査専用の制約とインデックス

// === UNIQUE 制約 ===
CREATE CONSTRAINT source_id IF NOT EXISTS FOR (s:Source) REQUIRE s.source_id IS UNIQUE;
CREATE CONSTRAINT chunk_id IF NOT EXISTS FOR (c:Chunk) REQUIRE c.chunk_id IS UNIQUE;
CREATE CONSTRAINT fact_id IF NOT EXISTS FOR (f:Fact) REQUIRE f.fact_id IS UNIQUE;
CREATE CONSTRAINT claim_id IF NOT EXISTS FOR (cl:Claim) REQUIRE cl.claim_id IS UNIQUE;
CREATE CONSTRAINT entity_id IF NOT EXISTS FOR (e:Entity) REQUIRE e.entity_id IS UNIQUE;
CREATE CONSTRAINT entity_ticker IF NOT EXISTS FOR (e:Entity) REQUIRE e.ticker IS UNIQUE;
CREATE CONSTRAINT datapoint_id IF NOT EXISTS FOR (d:FinancialDataPoint) REQUIRE d.datapoint_id IS UNIQUE;
CREATE CONSTRAINT period_id IF NOT EXISTS FOR (p:FiscalPeriod) REQUIRE p.period_id IS UNIQUE;
CREATE CONSTRAINT topic_id IF NOT EXISTS FOR (t:Topic) REQUIRE t.topic_id IS UNIQUE;
CREATE CONSTRAINT topic_key IF NOT EXISTS FOR (t:Topic) REQUIRE t.topic_key IS UNIQUE;

// === インデックス ===
CREATE INDEX source_type_idx IF NOT EXISTS FOR (s:Source) ON (s.source_type);
CREATE INDEX source_published IF NOT EXISTS FOR (s:Source) ON (s.published_at);
CREATE INDEX source_domain IF NOT EXISTS FOR (s:Source) ON (s.domain);
CREATE INDEX fact_type_idx IF NOT EXISTS FOR (f:Fact) ON (f.fact_type);
CREATE INDEX fact_date_idx IF NOT EXISTS FOR (f:Fact) ON (f.as_of_date);
CREATE INDEX claim_type_idx IF NOT EXISTS FOR (cl:Claim) ON (cl.claim_type);
CREATE INDEX claim_sentiment IF NOT EXISTS FOR (cl:Claim) ON (cl.sentiment);
CREATE INDEX entity_type_idx IF NOT EXISTS FOR (e:Entity) ON (e.entity_type);
CREATE INDEX datapoint_metric IF NOT EXISTS FOR (d:FinancialDataPoint) ON (d.metric_name);
CREATE INDEX datapoint_estimate IF NOT EXISTS FOR (d:FinancialDataPoint) ON (d.is_estimate);
CREATE INDEX period_label_idx IF NOT EXISTS FOR (p:FiscalPeriod) ON (p.period_label);
CREATE INDEX topic_category IF NOT EXISTS FOR (t:Topic) ON (t.category);
CREATE INDEX insight_type IF NOT EXISTS FOR (i:Insight) ON (i.insight_type);
