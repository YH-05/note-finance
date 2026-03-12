// Neo4j constraints for PDF pipeline knowledge extraction nodes
// Run these once to set up unique constraints for Fact and Claim nodes

CREATE CONSTRAINT unique_fact_id IF NOT EXISTS
  FOR (f:Fact) REQUIRE f.fact_id IS UNIQUE;

CREATE CONSTRAINT unique_claim_id IF NOT EXISTS
  FOR (c:Claim) REQUIRE c.claim_id IS UNIQUE;
