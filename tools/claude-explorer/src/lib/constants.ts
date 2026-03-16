/**
 * Application-wide constants for the Claude Explorer.
 *
 * Category prefix rules are defined in shared/category-rules.ts and used
 * at build time by extract-data.ts. The runtime app reads pre-computed
 * categories from graph-data.json, so no prefix map is needed here.
 */

import type { ComponentType, EdgeType } from "@/types";

/**
 * Edge style definitions for dependency visualization.
 */
export const EDGE_STYLES: Record<
  EdgeType,
  { color: string; label: string; dashed: boolean }
> = {
  skills: {
    color: "#6366f1",
    label: "skills",
    dashed: false,
  },
  skill_preload: {
    color: "#8b5cf6",
    label: "skill-preload",
    dashed: false,
  },
  subagent_type: {
    color: "#3b82f6",
    label: "subagent",
    dashed: true,
  },
  path_ref: {
    color: "#64748b",
    label: "path-ref",
    dashed: true,
  },
  inline_ref: {
    color: "#94a3b8",
    label: "inline-ref",
    dashed: true,
  },
};

/**
 * All component types in display order.
 */
export const COMPONENT_TYPES: ComponentType[] = [
  "agent",
  "command",
  "skill",
  "rule",
  "workflow",
];

/**
 * View modes for the application.
 */
export type ViewMode = "grid" | "graph";
