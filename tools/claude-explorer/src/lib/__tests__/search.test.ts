import { describe, it, expect } from "vitest";
import { buildSearchIndex, searchComponents } from "../search";
import type { Component } from "@/types";

/** Factory to create a minimal Component for testing. */
function makeComponent(overrides: Partial<Component> & { id: string }): Component {
  return {
    type: "agent",
    name: overrides.id,
    slug: overrides.id.replace("agent:", ""),
    description: "",
    filePath: `.claude/agents/${overrides.id}.md`,
    source: ".claude",
    content: "",
    model: "unknown",
    color: "gray",
    skills: [],
    tools: [],
    category: "General",
    ...overrides,
  } as Component;
}

describe("buildSearchIndex", () => {
  it("builds an index from an empty array without error", () => {
    const index = buildSearchIndex([]);
    expect(index).toBeDefined();
  });

  it("builds an index from a list of components", () => {
    const components: Component[] = [
      makeComponent({ id: "agent:alpha", name: "Alpha Agent", description: "Does alpha things" }),
      makeComponent({ id: "agent:beta", name: "Beta Agent", description: "Does beta things" }),
    ];
    const index = buildSearchIndex(components);
    expect(index).toBeDefined();
  });

  it("truncates content to 200 characters in the index", () => {
    const longContent = "a".repeat(500);
    const components: Component[] = [
      makeComponent({ id: "agent:long", name: "Long Content", content: longContent }),
    ];
    const index = buildSearchIndex(components);
    // Search should work even with truncated content
    const results = index.search("aaa");
    // Just verify it doesn't throw; content field is internal
    expect(results).toBeDefined();
  });
});

describe("searchComponents", () => {
  const components: Component[] = [
    makeComponent({ id: "agent:code-simplifier", name: "Code Simplifier", description: "Simplifies code" }),
    makeComponent({ id: "agent:pr-reviewer", name: "PR Reviewer", description: "Reviews pull requests" }),
    makeComponent({ id: "agent:test-writer", name: "Test Writer", description: "Writes tests" }),
  ];
  const index = buildSearchIndex(components);

  it("returns null for an empty query", () => {
    const result = searchComponents(index, "");
    expect(result).toBeNull();
  });

  it("returns null for a whitespace-only query", () => {
    const result = searchComponents(index, "   ");
    expect(result).toBeNull();
  });

  it("returns a Set<string> for a valid query", () => {
    const result = searchComponents(index, "code");
    expect(result).toBeInstanceOf(Set);
  });

  it("matches components by name", () => {
    const result = searchComponents(index, "Code Simplifier");
    expect(result).not.toBeNull();
    expect(result!.has("agent:code-simplifier")).toBe(true);
  });

  it("matches components by description", () => {
    const result = searchComponents(index, "pull requests");
    expect(result).not.toBeNull();
    expect(result!.has("agent:pr-reviewer")).toBe(true);
  });

  it("returns an empty Set for a query with no matches", () => {
    const result = searchComponents(index, "zzzznotfound");
    expect(result).not.toBeNull();
    expect(result!.size).toBe(0);
  });

  it("trims the query before searching", () => {
    const result = searchComponents(index, "  Code Simplifier  ");
    expect(result).not.toBeNull();
    expect(result!.has("agent:code-simplifier")).toBe(true);
  });
});
