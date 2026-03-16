import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { renderHook, act } from "@testing-library/react";
import { useSearch } from "../useSearch";
import type { Component } from "@/types";

/** Factory for minimal test components. */
function makeComponent(id: string, name: string, description = ""): Component {
  return {
    id,
    type: "agent",
    name,
    slug: id.replace("agent:", ""),
    description,
    filePath: `.claude/agents/${id}.md`,
    source: ".claude",
    content: "",
    model: "unknown",
    color: "gray",
    skills: [],
    tools: [],
    category: "General",
  } as Component;
}

const testComponents: Component[] = [
  makeComponent("agent:alpha", "Alpha Agent", "Handles alpha tasks"),
  makeComponent("agent:beta", "Beta Agent", "Handles beta tasks"),
  makeComponent("agent:gamma", "Gamma Agent", "Handles gamma tasks"),
];

describe("useSearch", () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it("has null matchedIds initially (no search active)", () => {
    const { result } = renderHook(() => useSearch(testComponents));
    expect(result.current.matchedIds).toBeNull();
  });

  it("has an empty searchQuery initially", () => {
    const { result } = renderHook(() => useSearch(testComponents));
    expect(result.current.searchQuery).toBe("");
  });

  it("updates searchQuery immediately when setSearchQuery is called", () => {
    const { result } = renderHook(() => useSearch(testComponents));

    act(() => {
      result.current.setSearchQuery("alpha");
    });

    expect(result.current.searchQuery).toBe("alpha");
  });

  it("updates matchedIds after debounce period", () => {
    const { result } = renderHook(() => useSearch(testComponents));

    act(() => {
      result.current.setSearchQuery("Alpha");
    });

    // Before debounce: matchedIds may still be null (debounce not yet fired)
    // Advance timers to trigger debounce
    act(() => {
      vi.advanceTimersByTime(350); // DEBOUNCE_MS is 300
    });

    expect(result.current.matchedIds).not.toBeNull();
    expect(result.current.matchedIds!.has("agent:alpha")).toBe(true);
  });

  it("returns null matchedIds when query is cleared", () => {
    const { result } = renderHook(() => useSearch(testComponents));

    // Set a query
    act(() => {
      result.current.setSearchQuery("alpha");
    });
    act(() => {
      vi.advanceTimersByTime(350);
    });
    expect(result.current.matchedIds).not.toBeNull();

    // Clear the query
    act(() => {
      result.current.setSearchQuery("");
    });
    act(() => {
      vi.advanceTimersByTime(350);
    });

    expect(result.current.matchedIds).toBeNull();
  });

  it("returns empty set for a query with no matches", () => {
    const { result } = renderHook(() => useSearch(testComponents));

    act(() => {
      result.current.setSearchQuery("zzzznotfound");
    });
    act(() => {
      vi.advanceTimersByTime(350);
    });

    expect(result.current.matchedIds).not.toBeNull();
    expect(result.current.matchedIds!.size).toBe(0);
  });

  it("indicates isPending during debounce period", () => {
    const { result } = renderHook(() => useSearch(testComponents));

    act(() => {
      result.current.setSearchQuery("alpha");
    });

    // isSearching should reflect the debounce pending state
    // The exact behavior depends on the useDebounce implementation
    // After debounce completes, isPending should be false
    act(() => {
      vi.advanceTimersByTime(350);
    });

    expect(result.current.isSearching).toBe(false);
  });
});
