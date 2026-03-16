/**
 * Header component with search input, stats badges, and view toggle.
 */

import type { ComponentType } from "@/types";
import { TYPE_COLORS } from "@/lib/colors";
import { COMPONENT_TYPES } from "@/lib/constants";
import type { ViewMode } from "@/lib/constants";

interface HeaderProps {
  stats: Record<ComponentType, number>;
  searchQuery: string;
  onSearchChange: (query: string) => void;
  viewMode: ViewMode;
  onViewModeChange: (mode: ViewMode) => void;
  filteredCount: number;
  totalCount: number;
}

export function Header({
  stats,
  searchQuery,
  onSearchChange,
  viewMode,
  onViewModeChange,
  filteredCount,
  totalCount,
}: HeaderProps) {
  return (
    <header className="bg-white border-b border-gray-200 px-6 py-4">
      <div className="flex items-center justify-between">
        {/* Title and description */}
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Claude Explorer</h1>
          <p className="text-sm text-gray-500 mt-1">
            .claude/ configuration visualizer
            <span className="ml-2 text-gray-400">
              ({filteredCount}/{totalCount} components)
            </span>
          </p>
        </div>

        {/* View mode toggle */}
        <div className="flex items-center gap-2">
          <button
            onClick={() => onViewModeChange("grid")}
            className={`px-3 py-1.5 text-sm font-medium rounded-md transition-colors ${
              viewMode === "grid"
                ? "bg-gray-900 text-white"
                : "bg-gray-100 text-gray-600 hover:bg-gray-200"
            }`}
          >
            Grid
          </button>
          <button
            onClick={() => onViewModeChange("graph")}
            className={`px-3 py-1.5 text-sm font-medium rounded-md transition-colors ${
              viewMode === "graph"
                ? "bg-gray-900 text-white"
                : "bg-gray-100 text-gray-600 hover:bg-gray-200"
            }`}
          >
            Graph
          </button>
        </div>
      </div>

      {/* Search and stats row */}
      <div className="mt-3 flex items-center gap-4">
        {/* Search input */}
        <div className="relative flex-1 max-w-md">
          <input
            type="text"
            placeholder="Search components..."
            value={searchQuery}
            onChange={(e) => onSearchChange(e.target.value)}
            className="w-full pl-9 pr-4 py-2 text-sm border border-gray-300 rounded-lg
                       focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
          />
          <svg
            className="absolute left-3 top-2.5 h-4 w-4 text-gray-400"
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"
            />
          </svg>
        </div>

        {/* Stats badges */}
        <div className="flex items-center gap-2">
          {COMPONENT_TYPES.map((type) => {
            const colors = TYPE_COLORS[type];
            return (
              <span
                key={type}
                className={`inline-flex items-center gap-1 px-2.5 py-1 text-xs font-medium rounded-full ${colors.bg} ${colors.text}`}
              >
                {colors.label}
                <span className="font-bold">{stats[type]}</span>
              </span>
            );
          })}
        </div>
      </div>
    </header>
  );
}
