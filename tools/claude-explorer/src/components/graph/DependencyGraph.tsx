/**
 * Main dependency graph view powered by React Flow + dagre.
 *
 * Wraps ReactFlow with custom node types, edge styles, minimap,
 * background, and the GraphControls panel. Recomputes the dagre
 * layout whenever the filtered components, edges, or layout options
 * change.
 *
 * Node clicks propagate to the parent via `onNodeClick` so that
 * the DetailPanel can display the selected component.
 */

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  ReactFlow,
  Background,
  MiniMap,
  useReactFlow,
  ReactFlowProvider,
} from "@xyflow/react";
import type { NodeMouseHandler, NodeTypes } from "@xyflow/react";
import "@xyflow/react/dist/style.css";

import type { Component, DependencyEdge } from "@/types";
import {
  computeGraphLayout,
  type GraphNodeData,
  type LayoutDirection,
} from "@/lib/graph-layout";
import { CustomNode } from "./CustomNode";
import { GraphControls } from "./GraphControls";

// ---------------------------------------------------------------------------
// Props
// ---------------------------------------------------------------------------

interface DependencyGraphProps {
  /** Components (already filtered by the shared filter state). */
  components: Component[];
  /** All dependency edges from graph data. */
  edges: DependencyEdge[];
  /** Callback when a node is clicked (opens DetailPanel). */
  onNodeClick: (componentId: string) => void;
}

// ---------------------------------------------------------------------------
// Node type registry (must be defined outside render to avoid re-mounts)
// ---------------------------------------------------------------------------

const nodeTypes: NodeTypes = {
  custom: CustomNode,
};

// ---------------------------------------------------------------------------
// Inner component (must be wrapped by ReactFlowProvider)
// ---------------------------------------------------------------------------

function DependencyGraphInner({
  components,
  edges: dependencyEdges,
  onNodeClick,
}: DependencyGraphProps) {
  const { fitView } = useReactFlow();

  const [direction, setDirection] = useState<LayoutDirection>("LR");
  const [hideIsolated, setHideIsolated] = useState(true);
  const [showMinimap, setShowMinimap] = useState(true);

  const fitViewTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  // Compute layout
  const { nodes, edges } = useMemo(
    () =>
      computeGraphLayout(components, dependencyEdges, {
        direction,
        hideIsolated,
      }),
    [components, dependencyEdges, direction, hideIsolated],
  );

  // Handle node click -> pass component ID up
  const handleNodeClick: NodeMouseHandler = useCallback(
    (_event, node) => {
      const data = node.data as GraphNodeData;
      onNodeClick(data.component.id);
    },
    [onNodeClick],
  );

  // Fit view handler
  const handleFitView = useCallback(() => {
    fitView({ padding: 0.2, duration: 300 });
  }, [fitView]);

  // Direction change -> also re-fit
  const handleDirectionChange = useCallback(
    (dir: LayoutDirection) => {
      setDirection(dir);
      if (fitViewTimerRef.current !== null) {
        clearTimeout(fitViewTimerRef.current);
      }
      fitViewTimerRef.current = setTimeout(() => {
        fitView({ padding: 0.2, duration: 300 });
        fitViewTimerRef.current = null;
      }, 50);
    },
    [fitView],
  );

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      if (fitViewTimerRef.current !== null) {
        clearTimeout(fitViewTimerRef.current);
      }
    };
  }, []);

  return (
    <div className="relative w-full h-full" style={{ minHeight: 400 }}>
      <GraphControls
        direction={direction}
        onDirectionChange={handleDirectionChange}
        onFitView={handleFitView}
        showMinimap={showMinimap}
        onToggleMinimap={() => setShowMinimap((v) => !v)}
        hideIsolated={hideIsolated}
        onToggleIsolated={() => setHideIsolated((v) => !v)}
      />

      <ReactFlow
        nodes={nodes}
        edges={edges}
        nodeTypes={nodeTypes}
        onNodeClick={handleNodeClick}
        fitView
        fitViewOptions={{ padding: 0.2 }}
        minZoom={0.1}
        maxZoom={2}
        proOptions={{ hideAttribution: true }}
        defaultEdgeOptions={{
          type: "smoothstep",
        }}
      >
        <Background color="#e5e7eb" gap={16} size={1} />
        {showMinimap && (
          <MiniMap
            nodeStrokeWidth={3}
            pannable
            zoomable
            style={{
              backgroundColor: "#f9fafb",
              border: "1px solid #e5e7eb",
              borderRadius: 8,
            }}
          />
        )}
      </ReactFlow>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Public component (with provider)
// ---------------------------------------------------------------------------

/**
 * Dependency graph view with React Flow.
 *
 * Must be used inside a parent that provides sufficient height
 * (the graph fills its container).
 */
export function DependencyGraph(props: DependencyGraphProps) {
  return (
    <ReactFlowProvider>
      <DependencyGraphInner {...props} />
    </ReactFlowProvider>
  );
}
