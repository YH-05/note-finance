/**
 * Hook to fetch and memoize the graph-data.json.
 *
 * The JSON is statically imported (bundled by Vite) so there is no
 * network request at runtime.  `useMemo` ensures derived structures
 * (maps, category lists) are recomputed only when the data changes.
 */

import { useMemo } from "react";
import type { Component, ComponentType, GraphData } from "@/types";
import rawData from "@/data/graph-data.json";

/** Validated graph data cast from the JSON import. */
const graphData = rawData as unknown as GraphData;

export interface UseGraphDataReturn {
  /** Full graph data. */
  data: GraphData;
  /** All components. */
  components: Component[];
  /** Component lookup by ID. */
  componentMap: Map<string, Component>;
  /** Stats per type. */
  stats: Record<ComponentType, number>;
  /** Sorted unique categories derived from agents. */
  categories: string[];
}

/**
 * Provides access to graph data with memoized derived structures.
 */
export function useGraphData(): UseGraphDataReturn {
  const componentMap = useMemo(() => {
    const map = new Map<string, Component>();
    for (const c of graphData.components) {
      map.set(c.id, c);
    }
    return map;
  }, []);

  const categories = useMemo(() => {
    const cats = new Set<string>();
    for (const c of graphData.components) {
      if (c.type === "agent") {
        cats.add(c.category);
      }
    }
    return [...cats].sort();
  }, []);

  return {
    data: graphData,
    components: graphData.components,
    componentMap,
    stats: graphData.stats,
    categories,
  };
}
