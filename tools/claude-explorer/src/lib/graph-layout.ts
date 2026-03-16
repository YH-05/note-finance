/**
 * dagre-based automatic graph layout for the dependency view.
 *
 * Converts the application's Component/DependencyEdge model into
 * React Flow Node/Edge arrays with positions computed by dagre.
 */

import dagre from "@dagrejs/dagre";
import type { Node as RFNode, Edge as RFEdge } from "@xyflow/react";
import type { Component, DependencyEdge, EdgeType } from "@/types";
import { EDGE_STYLES } from "@/lib/constants";

// ---------------------------------------------------------------------------
// Public types
// ---------------------------------------------------------------------------

/** Layout direction: left-to-right or top-to-bottom. */
export type LayoutDirection = "LR" | "TB";

export interface LayoutOptions {
  /** dagre rankdir (default "LR"). */
  direction: LayoutDirection;
  /** Hide nodes with zero connections (default true). */
  hideIsolated: boolean;
}

/** Data payload stored inside each React Flow node. */
export interface GraphNodeData {
  label: string;
  componentType: Component["type"];
  component: Component;
  [key: string]: unknown;
}

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const NODE_WIDTH = 200;
const NODE_HEIGHT = 80;

// ---------------------------------------------------------------------------
// Edge style mapping
// ---------------------------------------------------------------------------

function edgeStyle(type: EdgeType): Partial<RFEdge> {
  const style = EDGE_STYLES[type];
  const strokeDasharray = style.dashed ? "6 3" : undefined;

  // Use different dash patterns per type for clarity
  let dashArray = strokeDasharray;
  if (type === "path_ref") dashArray = "4 4";
  if (type === "inline_ref") dashArray = "2 4";

  return {
    style: {
      stroke: style.color,
      strokeWidth: 1.5,
      strokeDasharray: dashArray,
    },
    label: style.label,
    labelStyle: { fontSize: 10, fill: style.color },
    labelBgStyle: { fill: "white", fillOpacity: 0.8 },
  };
}

// ---------------------------------------------------------------------------
// Layout function
// ---------------------------------------------------------------------------

/**
 * Compute a dagre layout from components and dependency edges.
 *
 * @returns React Flow compatible `nodes` and `edges` arrays.
 */
export function computeGraphLayout(
  components: Component[],
  dependencyEdges: DependencyEdge[],
  options: LayoutOptions,
): { nodes: RFNode<GraphNodeData>[]; edges: RFEdge[] } {
  const { direction, hideIsolated } = options;

  // Build a set of IDs that participate in at least one edge
  const connectedIds = new Set<string>();
  for (const e of dependencyEdges) {
    if (!e.broken) {
      connectedIds.add(e.source);
      connectedIds.add(e.target);
    }
  }

  // Filter components
  const visibleComponents = hideIsolated
    ? components.filter((c) => connectedIds.has(c.id))
    : components;

  const visibleIdSet = new Set(visibleComponents.map((c) => c.id));

  // Create dagre graph
  const g = new dagre.graphlib.Graph();
  g.setGraph({
    rankdir: direction,
    nodesep: 40,
    ranksep: 80,
    marginx: 20,
    marginy: 20,
  });
  g.setDefaultEdgeLabel(() => ({}));

  // Add nodes
  for (const comp of visibleComponents) {
    g.setNode(comp.id, { width: NODE_WIDTH, height: NODE_HEIGHT });
  }

  // Add edges (skip broken edges and edges to/from invisible nodes)
  for (const e of dependencyEdges) {
    if (!e.broken && visibleIdSet.has(e.source) && visibleIdSet.has(e.target)) {
      g.setEdge(e.source, e.target);
    }
  }

  // Run layout
  dagre.layout(g);

  // Build React Flow nodes
  const nodes: RFNode<GraphNodeData>[] = visibleComponents.map((comp) => {
    const pos = g.node(comp.id);
    return {
      id: comp.id,
      type: "custom",
      position: {
        x: (pos?.x ?? 0) - NODE_WIDTH / 2,
        y: (pos?.y ?? 0) - NODE_HEIGHT / 2,
      },
      data: {
        label: comp.name,
        componentType: comp.type,
        component: comp,
      },
    };
  });

  // Build React Flow edges
  const edges: RFEdge[] = dependencyEdges
    .filter(
      (e) =>
        !e.broken && visibleIdSet.has(e.source) && visibleIdSet.has(e.target),
    )
    .map((e) => ({
      id: `edge-${e.source}-${e.target}-${e.type}`,
      source: e.source,
      target: e.target,
      type: "smoothstep",
      animated: e.type === "skills" || e.type === "skill_preload",
      ...edgeStyle(e.type),
    }));

  return { nodes, edges };
}
