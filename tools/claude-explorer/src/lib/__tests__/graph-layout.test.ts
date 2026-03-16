import { describe, it, expect } from "vitest";
import { computeGraphLayout } from "../graph-layout";
import type { Component, DependencyEdge } from "@/types";

/** Factory for minimal Component objects. */
function makeComponent(id: string, type: Component["type"] = "agent"): Component {
  const slug = id.replace(`${type}:`, "");
  const base = {
    id,
    type,
    name: slug,
    slug,
    description: "",
    filePath: `.claude/${type}s/${slug}.md`,
    source: ".claude" as const,
    content: "",
  };

  switch (type) {
    case "agent":
      return { ...base, type: "agent", model: "unknown", color: "gray", skills: [], tools: [], category: "General" };
    case "command":
      return { ...base, type: "command" };
    case "skill":
      return { ...base, type: "skill", allowedTools: [], skills: [], subFiles: [] };
    case "rule":
      return { ...base, type: "rule" };
    case "workflow":
      return { ...base, type: "workflow" };
  }
}

function makeEdge(
  source: string,
  target: string,
  type: DependencyEdge["type"] = "skills",
  broken = false,
): DependencyEdge {
  return { source, target, type, broken };
}

describe("computeGraphLayout", () => {
  it("returns empty arrays for empty input", () => {
    const result = computeGraphLayout([], [], { direction: "LR", hideIsolated: true });
    expect(result.nodes).toEqual([]);
    expect(result.edges).toEqual([]);
  });

  it("hides all isolated nodes when hideIsolated=true", () => {
    const components = [
      makeComponent("agent:a"),
      makeComponent("agent:b"),
      makeComponent("agent:c"),
    ];
    const result = computeGraphLayout(components, [], { direction: "LR", hideIsolated: true });
    expect(result.nodes).toHaveLength(0);
    expect(result.edges).toHaveLength(0);
  });

  it("shows all nodes when hideIsolated=false", () => {
    const components = [
      makeComponent("agent:a"),
      makeComponent("agent:b"),
      makeComponent("agent:c"),
    ];
    const result = computeGraphLayout(components, [], { direction: "LR", hideIsolated: false });
    expect(result.nodes).toHaveLength(3);
  });

  it("shows only connected nodes when hideIsolated=true", () => {
    const components = [
      makeComponent("agent:a"),
      makeComponent("skill:b", "skill"),
      makeComponent("agent:c"),
    ];
    const edges = [makeEdge("agent:a", "skill:b")];

    const result = computeGraphLayout(components, edges, { direction: "LR", hideIsolated: true });
    expect(result.nodes).toHaveLength(2);
    const nodeIds = result.nodes.map((n) => n.id);
    expect(nodeIds).toContain("agent:a");
    expect(nodeIds).toContain("skill:b");
    expect(nodeIds).not.toContain("agent:c");
  });

  it("excludes broken edges from the layout", () => {
    const components = [
      makeComponent("agent:a"),
      makeComponent("skill:b", "skill"),
      makeComponent("agent:c"),
    ];
    const edges = [
      makeEdge("agent:a", "skill:b", "skills", false),
      makeEdge("agent:a", "agent:c", "subagent_type", true), // broken
    ];

    const result = computeGraphLayout(components, edges, { direction: "LR", hideIsolated: true });
    // Only non-broken edge connects a and b
    expect(result.nodes).toHaveLength(2);
    expect(result.edges).toHaveLength(1);
    expect(result.edges[0]!.source).toBe("agent:a");
    expect(result.edges[0]!.target).toBe("skill:b");
  });

  it("assigns positions to nodes (LR direction)", () => {
    const components = [
      makeComponent("agent:a"),
      makeComponent("skill:b", "skill"),
    ];
    const edges = [makeEdge("agent:a", "skill:b")];

    const result = computeGraphLayout(components, edges, { direction: "LR", hideIsolated: false });
    expect(result.nodes).toHaveLength(2);
    for (const node of result.nodes) {
      expect(typeof node.position.x).toBe("number");
      expect(typeof node.position.y).toBe("number");
    }
  });

  it("produces different node positions for LR vs TB direction", () => {
    const components = [
      makeComponent("agent:a"),
      makeComponent("skill:b", "skill"),
    ];
    const edges = [makeEdge("agent:a", "skill:b")];

    const resultLR = computeGraphLayout(components, edges, { direction: "LR", hideIsolated: false });
    const resultTB = computeGraphLayout(components, edges, { direction: "TB", hideIsolated: false });

    // Positions should differ between LR and TB layouts
    const posLR = resultLR.nodes.map((n) => `${n.position.x},${n.position.y}`).sort();
    const posTB = resultTB.nodes.map((n) => `${n.position.x},${n.position.y}`).sort();
    expect(posLR).not.toEqual(posTB);
  });

  it("sets correct node data fields", () => {
    const comp = makeComponent("agent:a");
    const result = computeGraphLayout([comp], [], { direction: "LR", hideIsolated: false });

    expect(result.nodes).toHaveLength(1);
    const node = result.nodes[0]!;
    expect(node.id).toBe("agent:a");
    expect(node.type).toBe("custom");
    expect(node.data.label).toBe("a");
    expect(node.data.componentType).toBe("agent");
    expect(node.data.component).toEqual(comp);
  });

  it("sets animated=true for skills and skill_preload edge types", () => {
    const components = [
      makeComponent("agent:a"),
      makeComponent("skill:b", "skill"),
      makeComponent("command:c", "command"),
    ];
    const edges = [
      makeEdge("agent:a", "skill:b", "skills"),
      makeEdge("command:c", "skill:b", "skill_preload"),
    ];

    const result = computeGraphLayout(components, edges, { direction: "LR", hideIsolated: false });
    const skillsEdge = result.edges.find((e) => e.source === "agent:a");
    const preloadEdge = result.edges.find((e) => e.source === "command:c");

    expect(skillsEdge?.animated).toBe(true);
    expect(preloadEdge?.animated).toBe(true);
  });

  it("sets animated=false for non-skills edge types", () => {
    const components = [
      makeComponent("agent:a"),
      makeComponent("agent:b"),
    ];
    const edges = [makeEdge("agent:a", "agent:b", "path_ref")];

    const result = computeGraphLayout(components, edges, { direction: "LR", hideIsolated: false });
    expect(result.edges[0]?.animated).toBe(false);
  });
});
