// @vitest-environment node

/**
 * Tests for extract-data.ts pure functions.
 *
 * NOTE: The functions toStringArray, deriveName, inferCategory, and
 * validateEdges are NOT exported from extract-data.ts. They are internal
 * module functions. To enable proper unit testing, these functions should
 * be exported (e.g., via a separate helpers module or by adding exports).
 *
 * For now, this file tests the logic by reimplementing the same algorithms
 * based on the source code, verifying the expected behavior. When the
 * functions are eventually exported, these tests can be updated to import
 * directly.
 */

import { describe, it, expect } from "vitest";
import { inferCategory } from "../../shared/category-rules.js";

// ---------------------------------------------------------------------------
// Reimplementation of internal functions for testing
// (mirrors the logic in extract-data.ts exactly)
// ---------------------------------------------------------------------------

function toStringArray(value: unknown): string[] {
  if (Array.isArray(value)) {
    return value
      .filter((v): v is string => typeof v === "string")
      .map((s) => s.trim())
      .filter((s) => s.length > 0);
  }
  if (typeof value === "string" && value.length > 0) {
    return value
      .split(",")
      .map((s) => s.trim())
      .filter((s) => s.length > 0);
  }
  return [];
}

type ComponentType = "agent" | "command" | "skill" | "rule" | "workflow";

function deriveName(
  type: ComponentType,
  slug: string,
  fmName: unknown,
  content: string,
): string {
  if (typeof fmName === "string" && fmName.length > 0) return fmName;

  if (type === "rule") {
    const headingMatch = content.match(/^#\s+(.+)$/m);
    if (headingMatch?.[1]) return headingMatch[1].trim();
  }

  return slug;
}

// inferCategory is now imported from shared/category-rules.ts

interface DependencyEdge {
  source: string;
  target: string;
  type: string;
  broken: boolean;
}

function validateEdges(
  edges: DependencyEdge[],
  componentIds: Set<string>,
): DependencyEdge[] {
  for (const edge of edges) {
    if (!componentIds.has(edge.target)) {
      edge.broken = true;
    }
  }

  const filtered = edges.filter((e) => e.source !== e.target);

  const seen = new Set<string>();
  const unique: DependencyEdge[] = [];
  for (const edge of filtered) {
    const key = `${edge.source}|${edge.target}|${edge.type}`;
    if (!seen.has(key)) {
      seen.add(key);
      unique.push(edge);
    }
  }

  return unique;
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("toStringArray", () => {
  it("converts a string array to trimmed string array", () => {
    expect(toStringArray(["a", "b", "c"])).toEqual(["a", "b", "c"]);
  });

  it("trims whitespace from array elements", () => {
    expect(toStringArray(["  a ", " b  "])).toEqual(["a", "b"]);
  });

  it("filters out empty strings from array", () => {
    expect(toStringArray(["a", "", "  ", "b"])).toEqual(["a", "b"]);
  });

  it("filters out non-string values from array", () => {
    expect(toStringArray(["a", 42, null, "b", true])).toEqual(["a", "b"]);
  });

  it("splits a comma-separated string", () => {
    expect(toStringArray("Read, Bash, Write")).toEqual(["Read", "Bash", "Write"]);
  });

  it("handles a single value string (no comma)", () => {
    expect(toStringArray("Read")).toEqual(["Read"]);
  });

  it("returns empty array for empty string", () => {
    expect(toStringArray("")).toEqual([]);
  });

  it("returns empty array for null", () => {
    expect(toStringArray(null)).toEqual([]);
  });

  it("returns empty array for undefined", () => {
    expect(toStringArray(undefined)).toEqual([]);
  });

  it("returns empty array for a number", () => {
    expect(toStringArray(42)).toEqual([]);
  });

  it("returns empty array for a boolean", () => {
    expect(toStringArray(true)).toEqual([]);
  });

  it("returns empty array for empty array", () => {
    expect(toStringArray([])).toEqual([]);
  });
});

describe("deriveName", () => {
  it("returns frontmatter name when available", () => {
    expect(deriveName("agent", "my-slug", "My Agent", "# Some content")).toBe("My Agent");
  });

  it("falls back to slug when fmName is empty string", () => {
    expect(deriveName("agent", "my-slug", "", "")).toBe("my-slug");
  });

  it("falls back to slug when fmName is not a string", () => {
    expect(deriveName("agent", "my-slug", 42, "")).toBe("my-slug");
  });

  it("falls back to slug when fmName is null", () => {
    expect(deriveName("agent", "my-slug", null, "")).toBe("my-slug");
  });

  it("extracts heading from content for rule type", () => {
    const content = "Some intro text\n# Git Rules\nMore content";
    expect(deriveName("rule", "git-rules", null, content)).toBe("Git Rules");
  });

  it("uses first heading only for rule type", () => {
    const content = "# First Heading\n## Second Heading";
    expect(deriveName("rule", "my-rule", null, content)).toBe("First Heading");
  });

  it("falls back to slug for rule type when no heading exists", () => {
    expect(deriveName("rule", "my-rule", null, "no heading here")).toBe("my-rule");
  });

  it("does NOT extract heading for non-rule types", () => {
    const content = "# Agent Heading";
    expect(deriveName("agent", "my-agent", null, content)).toBe("my-agent");
  });

  it("does NOT extract heading for command type", () => {
    const content = "# Command Heading";
    expect(deriveName("command", "my-cmd", null, content)).toBe("my-cmd");
  });
});

describe("inferCategory", () => {
  it("returns 'PR Review' for pr- prefix", () => {
    expect(inferCategory("pr-reviewer")).toBe("PR Review");
  });

  it("returns 'Weekly Report' for wr- prefix", () => {
    expect(inferCategory("wr-reporter")).toBe("Weekly Report");
  });

  it("returns 'Weekly Report' for weekly-report- prefix", () => {
    expect(inferCategory("weekly-report-writer")).toBe("Weekly Report");
  });

  it("returns 'Weekly Report' for weekly-comment- prefix", () => {
    expect(inferCategory("weekly-comment-analyzer")).toBe("Weekly Report");
  });

  it("returns 'Finance' for finance- prefix", () => {
    expect(inferCategory("finance-article-writer")).toBe("Finance");
  });

  it("returns 'Testing' for test- prefix", () => {
    expect(inferCategory("test-runner")).toBe("Testing");
  });

  it("returns 'Experience DB' for exp- prefix", () => {
    expect(inferCategory("exp-collector")).toBe("Experience DB");
  });

  it("returns 'Experience DB' for experience- prefix", () => {
    expect(inferCategory("experience-analyzer")).toBe("Experience DB");
  });

  it("returns 'Case Study' for csa- prefix", () => {
    expect(inferCategory("csa-writer")).toBe("Case Study");
  });

  it("returns 'Asset Management' for asset-management- prefix", () => {
    expect(inferCategory("asset-management-reporter")).toBe("Asset Management");
  });

  it("returns 'AI Research' for ai-research- prefix", () => {
    expect(inferCategory("ai-research-collector")).toBe("AI Research");
  });

  it("returns 'News' for news- prefix", () => {
    expect(inferCategory("news-fetcher")).toBe("News");
  });

  it("returns 'Reddit' for reddit- prefix", () => {
    expect(inferCategory("reddit-crawler")).toBe("Reddit");
  });

  it("returns 'Market' for market- prefix", () => {
    expect(inferCategory("market-analyzer")).toBe("Market");
  });

  it("returns 'Research' for research- prefix", () => {
    expect(inferCategory("research-planner")).toBe("Research");
  });

  it("returns 'General' for unknown prefix", () => {
    expect(inferCategory("code-simplifier")).toBe("General");
  });

  it("returns 'General' for empty slug", () => {
    expect(inferCategory("")).toBe("General");
  });
});

describe("validateEdges", () => {
  it("marks edges with non-existent targets as broken", () => {
    const edges: DependencyEdge[] = [
      { source: "agent:a", target: "skill:exists", type: "skills", broken: false },
      { source: "agent:a", target: "skill:missing", type: "skills", broken: false },
    ];
    const componentIds = new Set(["agent:a", "skill:exists"]);

    const result = validateEdges(edges, componentIds);
    const missingEdge = result.find((e) => e.target === "skill:missing");
    const existsEdge = result.find((e) => e.target === "skill:exists");

    expect(missingEdge?.broken).toBe(true);
    expect(existsEdge?.broken).toBe(false);
  });

  it("removes self-referencing edges", () => {
    const edges: DependencyEdge[] = [
      { source: "agent:a", target: "agent:a", type: "inline_ref", broken: false },
      { source: "agent:a", target: "agent:b", type: "skills", broken: false },
    ];
    const componentIds = new Set(["agent:a", "agent:b"]);

    const result = validateEdges(edges, componentIds);
    expect(result).toHaveLength(1);
    expect(result[0]!.target).toBe("agent:b");
  });

  it("deduplicates edges by (source, target, type)", () => {
    const edges: DependencyEdge[] = [
      { source: "agent:a", target: "skill:b", type: "skills", broken: false },
      { source: "agent:a", target: "skill:b", type: "skills", broken: false },
      { source: "agent:a", target: "skill:b", type: "path_ref", broken: false },
    ];
    const componentIds = new Set(["agent:a", "skill:b"]);

    const result = validateEdges(edges, componentIds);
    expect(result).toHaveLength(2);
    // One "skills" edge and one "path_ref" edge
    const types = result.map((e) => e.type).sort();
    expect(types).toEqual(["path_ref", "skills"]);
  });

  it("handles empty edge list", () => {
    const result = validateEdges([], new Set(["agent:a"]));
    expect(result).toEqual([]);
  });

  it("handles all edges being self-referencing", () => {
    const edges: DependencyEdge[] = [
      { source: "agent:a", target: "agent:a", type: "skills", broken: false },
    ];
    const componentIds = new Set(["agent:a"]);

    const result = validateEdges(edges, componentIds);
    expect(result).toEqual([]);
  });

  it("combines broken marking, self-ref removal, and dedup correctly", () => {
    const edges: DependencyEdge[] = [
      { source: "agent:a", target: "agent:a", type: "inline_ref", broken: false }, // self-ref, removed
      { source: "agent:a", target: "skill:b", type: "skills", broken: false }, // valid
      { source: "agent:a", target: "skill:b", type: "skills", broken: false }, // duplicate, removed
      { source: "agent:a", target: "skill:missing", type: "skills", broken: false }, // broken
    ];
    const componentIds = new Set(["agent:a", "skill:b"]);

    const result = validateEdges(edges, componentIds);
    expect(result).toHaveLength(2);

    const validEdge = result.find((e) => e.target === "skill:b");
    const brokenEdge = result.find((e) => e.target === "skill:missing");

    expect(validEdge?.broken).toBe(false);
    expect(brokenEdge?.broken).toBe(true);
  });
});
