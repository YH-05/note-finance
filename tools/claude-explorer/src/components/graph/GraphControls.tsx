/**
 * Control panel for the dependency graph view.
 *
 * Provides:
 *  - Layout direction toggle (LR / TB)
 *  - Fit-view button
 *  - Minimap toggle
 *  - Isolated node toggle
 */

import type { LayoutDirection } from "@/lib/graph-layout";

interface GraphControlsProps {
  /** Current layout direction. */
  direction: LayoutDirection;
  /** Callback to change layout direction. */
  onDirectionChange: (dir: LayoutDirection) => void;
  /** Trigger React Flow fitView. */
  onFitView: () => void;
  /** Whether the minimap is visible. */
  showMinimap: boolean;
  /** Toggle minimap visibility. */
  onToggleMinimap: () => void;
  /** Whether isolated (unconnected) nodes are hidden. */
  hideIsolated: boolean;
  /** Toggle isolated-node visibility. */
  onToggleIsolated: () => void;
}

export function GraphControls({
  direction,
  onDirectionChange,
  onFitView,
  showMinimap,
  onToggleMinimap,
  hideIsolated,
  onToggleIsolated,
}: GraphControlsProps) {
  return (
    <div className="absolute top-3 left-3 z-10 flex flex-col gap-1.5 bg-white/95 backdrop-blur rounded-lg shadow-md border border-gray-200 p-2">
      {/* Direction toggle */}
      <div className="flex gap-1">
        <button
          onClick={() => onDirectionChange("LR")}
          className={`px-2 py-1 text-xs font-medium rounded transition-colors ${
            direction === "LR"
              ? "bg-gray-800 text-white"
              : "bg-gray-100 text-gray-600 hover:bg-gray-200"
          }`}
          title="Left to Right layout"
        >
          LR
        </button>
        <button
          onClick={() => onDirectionChange("TB")}
          className={`px-2 py-1 text-xs font-medium rounded transition-colors ${
            direction === "TB"
              ? "bg-gray-800 text-white"
              : "bg-gray-100 text-gray-600 hover:bg-gray-200"
          }`}
          title="Top to Bottom layout"
        >
          TB
        </button>
      </div>

      {/* Fit view */}
      <button
        onClick={onFitView}
        className="px-2 py-1 text-xs font-medium text-gray-600 bg-gray-100 rounded hover:bg-gray-200 transition-colors"
        title="Fit graph to viewport"
      >
        <svg
          className="w-3.5 h-3.5 inline mr-1"
          fill="none"
          stroke="currentColor"
          viewBox="0 0 24 24"
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={2}
            d="M4 8V4m0 0h4M4 4l5 5m11-1V4m0 0h-4m4 0l-5 5M4 16v4m0 0h4m-4 0l5-5m11 5l-5-5m5 5v-4m0 4h-4"
          />
        </svg>
        Fit
      </button>

      {/* Minimap toggle */}
      <label className="flex items-center gap-1.5 px-1 py-0.5 cursor-pointer">
        <input
          type="checkbox"
          checked={showMinimap}
          onChange={onToggleMinimap}
          className="h-3 w-3 rounded border-gray-300"
        />
        <span className="text-xs text-gray-600">Minimap</span>
      </label>

      {/* Isolated nodes toggle */}
      <label className="flex items-center gap-1.5 px-1 py-0.5 cursor-pointer">
        <input
          type="checkbox"
          checked={hideIsolated}
          onChange={onToggleIsolated}
          className="h-3 w-3 rounded border-gray-300"
        />
        <span className="text-xs text-gray-600">Hide isolated</span>
      </label>
    </div>
  );
}
