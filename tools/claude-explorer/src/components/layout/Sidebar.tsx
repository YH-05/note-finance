/**
 * Sidebar component with type and category filter checkboxes.
 */

import type { ComponentType } from "@/types";
import { TYPE_COLORS } from "@/lib/colors";
import { COMPONENT_TYPES } from "@/lib/constants";

interface SidebarProps {
  activeTypes: Set<ComponentType>;
  onToggleType: (type: ComponentType) => void;
  categories: string[];
  activeCategories: Set<string>;
  onToggleCategory: (category: string) => void;
  onResetFilters: () => void;
}

export function Sidebar({
  activeTypes,
  onToggleType,
  categories,
  activeCategories,
  onToggleCategory,
  onResetFilters,
}: SidebarProps) {
  const hasActiveFilters = activeTypes.size > 0 || activeCategories.size > 0;

  return (
    <aside className="w-56 flex-shrink-0 bg-white border-r border-gray-200 p-4 overflow-y-auto">
      {/* Reset button */}
      {hasActiveFilters && (
        <button
          onClick={onResetFilters}
          className="w-full mb-4 px-3 py-1.5 text-xs font-medium text-gray-600
                     bg-gray-100 rounded-md hover:bg-gray-200 transition-colors"
        >
          Reset Filters
        </button>
      )}

      {/* Type filters */}
      <div className="mb-6">
        <h3 className="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-2">
          Types
        </h3>
        <div className="space-y-1">
          {COMPONENT_TYPES.map((type) => {
            const colors = TYPE_COLORS[type];
            const isActive = activeTypes.has(type);
            return (
              <label
                key={type}
                className="flex items-center gap-2 px-2 py-1.5 rounded cursor-pointer
                           hover:bg-gray-50 transition-colors"
              >
                <input
                  type="checkbox"
                  checked={isActive}
                  onChange={() => onToggleType(type)}
                  className="h-3.5 w-3.5 rounded border-gray-300"
                />
                <span
                  className={`w-2 h-2 rounded-full ${colors.bgSolid}`}
                />
                <span className="text-sm text-gray-700">{colors.label}</span>
              </label>
            );
          })}
        </div>
      </div>

      {/* Category filters */}
      <div>
        <h3 className="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-2">
          Categories
        </h3>
        <div className="space-y-1">
          {categories.map((cat) => {
            const isActive = activeCategories.has(cat);
            return (
              <label
                key={cat}
                className="flex items-center gap-2 px-2 py-1.5 rounded cursor-pointer
                           hover:bg-gray-50 transition-colors"
              >
                <input
                  type="checkbox"
                  checked={isActive}
                  onChange={() => onToggleCategory(cat)}
                  className="h-3.5 w-3.5 rounded border-gray-300"
                />
                <span className="text-sm text-gray-700 truncate">{cat}</span>
              </label>
            );
          })}
        </div>
      </div>
    </aside>
  );
}
