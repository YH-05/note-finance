/**
 * Custom React Flow node for dependency graph visualization.
 *
 * Renders a colored rectangle based on component type, with a
 * name label and a small type badge. Clicking the node triggers
 * the DetailPanel via the onNodeClick handler in the parent.
 */

import { memo } from "react";
import { Handle, Position } from "@xyflow/react";
import type { NodeProps } from "@xyflow/react";
import { TYPE_COLORS } from "@/lib/colors";
import type { GraphNodeData } from "@/lib/graph-layout";

/**
 * Tailwind-compatible hex colors for node backgrounds.
 * These correspond to the TYPE_COLORS scheme but as inline styles
 * since React Flow nodes use absolute positioning outside Tailwind's scope.
 */
const NODE_BG_COLORS: Record<string, string> = {
  agent: "#eff6ff", // blue-50
  command: "#f0fdf4", // green-50
  skill: "#faf5ff", // purple-50
  rule: "#f9fafb", // gray-50
  workflow: "#fff7ed", // orange-50
};

const NODE_BORDER_COLORS: Record<string, string> = {
  agent: "#60a5fa", // blue-400
  command: "#4ade80", // green-400
  skill: "#c084fc", // purple-400
  rule: "#9ca3af", // gray-400
  workflow: "#fb923c", // orange-400
};

function CustomNodeComponent({ data }: NodeProps) {
  const nodeData = data as unknown as GraphNodeData;
  const { label, componentType } = nodeData;
  const colors = TYPE_COLORS[componentType];
  const bgColor = NODE_BG_COLORS[componentType] ?? "#f9fafb";
  const borderColor = NODE_BORDER_COLORS[componentType] ?? "#9ca3af";

  return (
    <div
      style={{
        width: 200,
        height: 80,
        backgroundColor: bgColor,
        borderColor: borderColor,
        borderWidth: 2,
        borderStyle: "solid",
        borderRadius: 8,
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        justifyContent: "center",
        padding: "8px 12px",
        cursor: "pointer",
        boxShadow: "0 1px 3px rgba(0,0,0,0.1)",
        transition: "box-shadow 0.15s ease",
      }}
      onMouseEnter={(e) => {
        e.currentTarget.style.boxShadow = "0 4px 12px rgba(0,0,0,0.15)";
      }}
      onMouseLeave={(e) => {
        e.currentTarget.style.boxShadow = "0 1px 3px rgba(0,0,0,0.1)";
      }}
    >
      {/* Type badge */}
      <span
        className={`${colors.bgSolid} text-white`}
        style={{
          fontSize: 9,
          fontWeight: 600,
          padding: "1px 6px",
          borderRadius: 9999,
          marginBottom: 4,
          letterSpacing: "0.05em",
          textTransform: "uppercase",
        }}
      >
        {colors.label}
      </span>

      {/* Name label */}
      <span
        style={{
          fontSize: 12,
          fontWeight: 600,
          color: "#1f2937",
          textAlign: "center",
          lineHeight: 1.3,
          overflow: "hidden",
          textOverflow: "ellipsis",
          whiteSpace: "nowrap",
          width: "100%",
        }}
        title={label}
      >
        {label}
      </span>

      {/* Handles for edges */}
      <Handle
        type="target"
        position={Position.Left}
        style={{
          width: 6,
          height: 6,
          background: borderColor,
          border: "none",
        }}
      />
      <Handle
        type="source"
        position={Position.Right}
        style={{
          width: 6,
          height: 6,
          background: borderColor,
          border: "none",
        }}
      />
    </div>
  );
}

export const CustomNode = memo(CustomNodeComponent);
