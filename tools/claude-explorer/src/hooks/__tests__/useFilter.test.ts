import { describe, it, expect } from "vitest";
import { renderHook, act } from "@testing-library/react";
import { useFilter } from "../useFilter";
import type { Component } from "@/types";

/** Factory for minimal test components. */
function makeAgent(id: string, category = "General"): Component {
  return {
    id,
    type: "agent",
    name: id,
    slug: id.replace("agent:", ""),
    description: "",
    filePath: `.claude/agents/${id}.md`,
    source: ".claude",
    content: "",
    model: "unknown",
    color: "gray",
    skills: [],
    tools: [],
    category,
  };
}

function makeSkill(id: string): Component {
  return {
    id,
    type: "skill",
    name: id,
    slug: id.replace("skill:", ""),
    description: "",
    filePath: `.claude/skills/${id}/SKILL.md`,
    source: ".claude",
    content: "",
    allowedTools: [],
    skills: [],
    subFiles: [],
  };
}

function makeCommand(id: string): Component {
  return {
    id,
    type: "command",
    name: id,
    slug: id.replace("command:", ""),
    description: "",
    filePath: `.claude/commands/${id}.md`,
    source: ".claude",
    content: "",
  };
}

function makeRule(id: string): Component {
  return {
    id,
    type: "rule",
    name: id,
    slug: id.replace("rule:", ""),
    description: "",
    filePath: `.claude/rules/${id}.md`,
    source: ".claude",
    content: "",
  };
}

const testComponents: Component[] = [
  makeAgent("agent:alpha", "Finance"),
  makeAgent("agent:beta", "News"),
  makeSkill("skill:search"),
  makeCommand("command:deploy"),
  makeRule("rule:coding"),
];

describe("useFilter", () => {
  describe("initial state", () => {
    it("starts with empty activeTypes", () => {
      const { result } = renderHook(() => useFilter());
      expect(result.current.activeTypes.size).toBe(0);
    });

    it("starts with empty activeCategories", () => {
      const { result } = renderHook(() => useFilter());
      expect(result.current.activeCategories.size).toBe(0);
    });
  });

  describe("filterComponents with no filters", () => {
    it("returns all components when no filters are active", () => {
      const { result } = renderHook(() => useFilter());
      const filtered = result.current.filterComponents(testComponents, null);
      expect(filtered).toHaveLength(testComponents.length);
    });
  });

  describe("type filter", () => {
    it("filters by a single type", () => {
      const { result } = renderHook(() => useFilter());

      act(() => {
        result.current.toggleType("agent");
      });

      const filtered = result.current.filterComponents(testComponents, null);
      expect(filtered).toHaveLength(2);
      expect(filtered.every((c) => c.type === "agent")).toBe(true);
    });

    it("filters by multiple types", () => {
      const { result } = renderHook(() => useFilter());

      act(() => {
        result.current.toggleType("agent");
        result.current.toggleType("skill");
      });

      const filtered = result.current.filterComponents(testComponents, null);
      expect(filtered).toHaveLength(3);
      expect(filtered.every((c) => c.type === "agent" || c.type === "skill")).toBe(true);
    });

    it("toggles off a type when toggled again", () => {
      const { result } = renderHook(() => useFilter());

      act(() => {
        result.current.toggleType("agent");
      });
      expect(result.current.activeTypes.has("agent")).toBe(true);

      act(() => {
        result.current.toggleType("agent");
      });
      expect(result.current.activeTypes.has("agent")).toBe(false);

      const filtered = result.current.filterComponents(testComponents, null);
      expect(filtered).toHaveLength(testComponents.length);
    });
  });

  describe("category filter", () => {
    it("filters agents by category", () => {
      const { result } = renderHook(() => useFilter());

      act(() => {
        result.current.toggleCategory("Finance");
      });

      const filtered = result.current.filterComponents(testComponents, null);
      // Only the agent with category "Finance" should pass
      expect(filtered).toHaveLength(1);
      expect(filtered[0]!.id).toBe("agent:alpha");
    });

    it("excludes non-agent types when category filter is active", () => {
      const { result } = renderHook(() => useFilter());

      act(() => {
        result.current.toggleCategory("Finance");
      });

      const filtered = result.current.filterComponents(testComponents, null);
      // Skills, commands, and rules have no category, so they are excluded
      expect(filtered.every((c) => c.type === "agent")).toBe(true);
    });

    it("toggles off a category when toggled again", () => {
      const { result } = renderHook(() => useFilter());

      act(() => {
        result.current.toggleCategory("Finance");
      });
      expect(result.current.activeCategories.has("Finance")).toBe(true);

      act(() => {
        result.current.toggleCategory("Finance");
      });
      expect(result.current.activeCategories.has("Finance")).toBe(false);
    });
  });

  describe("matchedIds filter (search)", () => {
    it("filters by matchedIds when search is active", () => {
      const { result } = renderHook(() => useFilter());

      const matchedIds = new Set(["agent:alpha", "skill:search"]);
      const filtered = result.current.filterComponents(testComponents, matchedIds);
      expect(filtered).toHaveLength(2);
      expect(filtered.map((c) => c.id).sort()).toEqual(["agent:alpha", "skill:search"]);
    });

    it("returns empty array when matchedIds is empty", () => {
      const { result } = renderHook(() => useFilter());

      const filtered = result.current.filterComponents(testComponents, new Set());
      expect(filtered).toHaveLength(0);
    });

    it("returns all components when matchedIds is null", () => {
      const { result } = renderHook(() => useFilter());

      const filtered = result.current.filterComponents(testComponents, null);
      expect(filtered).toHaveLength(testComponents.length);
    });
  });

  describe("combined filters", () => {
    it("applies type + matchedIds together", () => {
      const { result } = renderHook(() => useFilter());

      act(() => {
        result.current.toggleType("agent");
      });

      const matchedIds = new Set(["agent:alpha", "skill:search"]);
      const filtered = result.current.filterComponents(testComponents, matchedIds);
      // Only agent:alpha matches both type=agent AND is in matchedIds
      expect(filtered).toHaveLength(1);
      expect(filtered[0]!.id).toBe("agent:alpha");
    });

    it("applies type + category together", () => {
      const { result } = renderHook(() => useFilter());

      act(() => {
        result.current.toggleType("agent");
        result.current.toggleCategory("News");
      });

      const filtered = result.current.filterComponents(testComponents, null);
      expect(filtered).toHaveLength(1);
      expect(filtered[0]!.id).toBe("agent:beta");
    });

    it("applies type + category + matchedIds together", () => {
      const { result } = renderHook(() => useFilter());

      act(() => {
        result.current.toggleType("agent");
        result.current.toggleCategory("Finance");
      });

      const matchedIds = new Set(["agent:alpha", "agent:beta"]);
      const filtered = result.current.filterComponents(testComponents, matchedIds);
      expect(filtered).toHaveLength(1);
      expect(filtered[0]!.id).toBe("agent:alpha");
    });
  });

  describe("resetFilters", () => {
    it("clears all type and category filters", () => {
      const { result } = renderHook(() => useFilter());

      act(() => {
        result.current.toggleType("agent");
        result.current.toggleCategory("Finance");
      });
      expect(result.current.activeTypes.size).toBe(1);
      expect(result.current.activeCategories.size).toBe(1);

      act(() => {
        result.current.resetFilters();
      });
      expect(result.current.activeTypes.size).toBe(0);
      expect(result.current.activeCategories.size).toBe(0);
    });
  });
});
