/**
 * Application-wide constants for the Claude Explorer.
 */

import type { ComponentType, EdgeType } from "@/types";

/**
 * Category prefix mapping — maps agent name prefixes to display categories.
 */
export const CATEGORY_PREFIX_MAP: Record<string, string> = {
  wr: "Weekly Report",
  "finance-news": "News",
  "finance-article": "Finance",
  reddit: "Reddit",
  pr: "PR Review",
  "ai-research": "AI Research",
  "asset-management": "Asset Management",
  "case-study": "Case Study",
  "experience-db": "Experience DB",
  market: "Market",
  research: "Research",
  test: "Testing",
};

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
