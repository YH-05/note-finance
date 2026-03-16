/**
 * Dependency list component for the detail panel.
 *
 * Displays two sections:
 * - "Depends On" — outgoing edges (this component depends on others)
 * - "Used By" — incoming edges (other components depend on this one)
 *
 * Each item is clickable and navigates the detail panel to the target.
 */

import { useMemo } from "react";
import type { Component, DependencyEdge } from "@/types";
import { EDGE_STYLES } from "@/lib/constants";

interface DependencyListProps {
  /** ID of the currently selected component. */
  componentId: string;
  /** All edges in the graph. */
  edges: DependencyEdge[];
  /** Component lookup map for resolving names. */
  componentMap: Map<string, Component>;
  /** Callback when a dependency item is clicked. */
  onSelect: (id: string) => void;
}

interface DependencyItemProps {
  id: string;
  name: string;
  edgeType: DependencyEdge["type"];
  broken: boolean;
  onSelect: (id: string) => void;
}

function DependencyItem({
  id,
  name,
  edgeType,
  broken,
  onSelect,
}: DependencyItemProps) {
  const style = EDGE_STYLES[edgeType];

  return (
    <button
      type="button"
      onClick={() => !broken && onSelect(id)}
      disabled={broken}
      className={`flex items-center gap-2 w-full text-left px-2 py-1.5 rounded text-xs transition-colors ${
        broken
          ? "text-gray-400 cursor-not-allowed"
          : "text-gray-700 hover:bg-gray-100 cursor-pointer"
      }`}
    >
      {/* Edge type indicator dot */}
      <span
        className="w-2 h-2 rounded-full flex-shrink-0"
        style={{ backgroundColor: style.color }}
        title={style.label}
      />

      {/* Name */}
      <span className={`truncate ${broken ? "line-through" : ""}`}>
        {name}
      </span>

      {/* Edge type label */}
      <span className="ml-auto text-[10px] text-gray-400 flex-shrink-0">
        {style.label}
      </span>

      {/* Broken indicator */}
      {broken && (
        <span className="text-[10px] text-red-400 flex-shrink-0" title="Target not found">
          (broken)
        </span>
      )}
    </button>
  );
}

export function DependencyList({
  componentId,
  edges,
  componentMap,
  onSelect,
}: DependencyListProps) {
  // Outgoing: this component depends on target
  const dependsOn = useMemo(
    () => edges.filter((e) => e.source === componentId),
    [edges, componentId],
  );
  // Incoming: source depends on this component
  const usedBy = useMemo(
    () => edges.filter((e) => e.target === componentId),
    [edges, componentId],
  );

  if (dependsOn.length === 0 && usedBy.length === 0) {
    return (
      <p className="text-xs text-gray-400 italic">No dependencies found.</p>
    );
  }

  return (
    <div className="space-y-4">
      {/* Depends On (outgoing edges) */}
      {dependsOn.length > 0 && (
        <div>
          <h4 className="text-[10px] font-medium text-gray-400 uppercase tracking-wider mb-1">
            Depends On ({dependsOn.length})
          </h4>
          <div className="space-y-0.5">
            {dependsOn.map((edge) => {
              const target = componentMap.get(edge.target);
              return (
                <DependencyItem
                  key={`${edge.target}-${edge.type}`}
                  id={edge.target}
                  name={target?.name ?? edge.target}
                  edgeType={edge.type}
                  broken={edge.broken}
                  onSelect={onSelect}
                />
              );
            })}
          </div>
        </div>
      )}

      {/* Used By (incoming edges) */}
      {usedBy.length > 0 && (
        <div>
          <h4 className="text-[10px] font-medium text-gray-400 uppercase tracking-wider mb-1">
            Used By ({usedBy.length})
          </h4>
          <div className="space-y-0.5">
            {usedBy.map((edge) => {
              const source = componentMap.get(edge.source);
              return (
                <DependencyItem
                  key={`${edge.source}-${edge.type}`}
                  id={edge.source}
                  name={source?.name ?? edge.source}
                  edgeType={edge.type}
                  broken={edge.broken}
                  onSelect={onSelect}
                />
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}
