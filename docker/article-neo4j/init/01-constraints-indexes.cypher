// Article Neo4j - 記事調査スキーマ初期化
// note記事・X投稿の調査情報専用の制約とインデックス

// === コンテンツノード ===
// Article: note記事
CREATE CONSTRAINT article_id IF NOT EXISTS FOR (a:Article) REQUIRE a.article_id IS UNIQUE;
// XPost: X投稿
CREATE CONSTRAINT xpost_id IF NOT EXISTS FOR (x:XPost) REQUIRE x.xpost_id IS UNIQUE;

// === 調査データノード（KG v2 準拠） ===
// Source: 調査ソース（ニュース記事、レポート、Reddit投稿等）
CREATE CONSTRAINT source_id IF NOT EXISTS FOR (s:Source) REQUIRE s.source_id IS UNIQUE;
// Chunk: テキストチャンク
CREATE CONSTRAINT chunk_id IF NOT EXISTS FOR (c:Chunk) REQUIRE c.chunk_id IS UNIQUE;
// Fact: 事実情報（数値、日時、統計等）
CREATE CONSTRAINT fact_id IF NOT EXISTS FOR (f:Fact) REQUIRE f.fact_id IS UNIQUE;
// Claim: 主張・見解・意見
CREATE CONSTRAINT claim_id IF NOT EXISTS FOR (cl:Claim) REQUIRE cl.claim_id IS UNIQUE;
// Entity: 企業・人物・組織等
CREATE CONSTRAINT entity_id IF NOT EXISTS FOR (e:Entity) REQUIRE e.entity_id IS UNIQUE;
// Topic: テーマ・トピック
CREATE CONSTRAINT topic_id IF NOT EXISTS FOR (t:Topic) REQUIRE t.topic_id IS UNIQUE;
CREATE CONSTRAINT topic_key IF NOT EXISTS FOR (t:Topic) REQUIRE t.topic_key IS UNIQUE;
// Insight: インサイト・洞察
CREATE CONSTRAINT insight_id IF NOT EXISTS FOR (i:Insight) REQUIRE i.insight_id IS UNIQUE;
// Quote: 引用文（ソースからの直接引用）
CREATE CONSTRAINT quote_id IF NOT EXISTS FOR (q:Quote) REQUIRE q.quote_id IS UNIQUE;

// === インデックス: Article ===
CREATE INDEX article_category IF NOT EXISTS FOR (a:Article) ON (a.category);
CREATE INDEX article_status IF NOT EXISTS FOR (a:Article) ON (a.status);
CREATE INDEX article_published IF NOT EXISTS FOR (a:Article) ON (a.published_at);
CREATE INDEX article_slug IF NOT EXISTS FOR (a:Article) ON (a.slug);

// === インデックス: XPost ===
CREATE INDEX xpost_article IF NOT EXISTS FOR (x:XPost) ON (x.article_id);
CREATE INDEX xpost_posted IF NOT EXISTS FOR (x:XPost) ON (x.posted_at);
CREATE INDEX xpost_status IF NOT EXISTS FOR (x:XPost) ON (x.status);

// === インデックス: Source ===
CREATE INDEX source_type_idx IF NOT EXISTS FOR (s:Source) ON (s.source_type);
CREATE INDEX source_published IF NOT EXISTS FOR (s:Source) ON (s.published_at);
CREATE INDEX source_domain IF NOT EXISTS FOR (s:Source) ON (s.domain);
CREATE INDEX source_url IF NOT EXISTS FOR (s:Source) ON (s.url);

// === インデックス: Fact/Claim ===
CREATE INDEX fact_type_idx IF NOT EXISTS FOR (f:Fact) ON (f.fact_type);
CREATE INDEX fact_date_idx IF NOT EXISTS FOR (f:Fact) ON (f.as_of_date);
CREATE INDEX claim_type_idx IF NOT EXISTS FOR (cl:Claim) ON (cl.claim_type);
CREATE INDEX claim_sentiment IF NOT EXISTS FOR (cl:Claim) ON (cl.sentiment);

// === インデックス: Entity ===
CREATE INDEX entity_type_idx IF NOT EXISTS FOR (e:Entity) ON (e.entity_type);
CREATE INDEX entity_name IF NOT EXISTS FOR (e:Entity) ON (e.name);

// === インデックス: Topic/Insight/Quote ===
CREATE INDEX topic_category IF NOT EXISTS FOR (t:Topic) ON (t.category);
CREATE INDEX insight_type IF NOT EXISTS FOR (i:Insight) ON (i.insight_type);
CREATE INDEX quote_source IF NOT EXISTS FOR (q:Quote) ON (q.source_id);
