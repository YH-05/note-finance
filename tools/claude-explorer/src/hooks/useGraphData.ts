/**
 * Hook to fetch and memoize the graph-data.json.
 *
 * The JSON is statically imported (bundled by Vite) so there is no
 * network request at runtime.  `useMemo` ensures derived structures
 * (maps, category lists) are recomputed only when the data changes.
 */

import { useMemo } from "react";
import { z } from "zod";
import type { Component, ComponentType, GraphData } from "@/types";
import rawData from "@/data/graph-data.json";

// ---------------------------------------------------------------------------
// Zod schemas for runtime validation
// ---------------------------------------------------------------------------

const ComponentSchema = z
  .object({
    id: z.string(),
    type: z.enum(["agent", "command", "skill", "rule", "workflow"]),
    name: z.string(),
    slug: z.string(),
    description: z.string(),
    content: z.string(),
    filePath: z.string(),
  })
  .passthrough();

const EdgeSchema = z.object({
  source: z.string(),
  target: z.string(),
  type: z.enum(["skills", "skill_preload", "subagent_type", "path_ref", "inline_ref"]),
  broken: z.boolean(),
});

const GraphDataSchema = z.object({
  components: z.array(ComponentSchema),
  edges: z.array(EdgeSchema),
  stats: z.record(z.string(), z.number()),
  generatedAt: z.string(),
});

/**
 * Validated graph data parsed through Zod schema.
 * The parse validates structural integrity; we cast to GraphData
 * because passthrough() preserves extra fields that the discriminated
 * union Component type expects (model, skills, category, etc.).
 */
const graphData = GraphDataSchema.parse(rawData) as unknown as GraphData;

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
