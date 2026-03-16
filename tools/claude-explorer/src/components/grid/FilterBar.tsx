/**
 * Compact filter bar with type toggle pills.
 *
 * Displayed above the card grid as a quick alternative to the sidebar
 * type checkboxes.
 */

import type { ComponentType } from "@/types";
import { TYPE_COLORS } from "@/lib/colors";
import { COMPONENT_TYPES } from "@/lib/constants";

interface FilterBarProps {
  activeTypes: Set<ComponentType>;
  onToggleType: (type: ComponentType) => void;
  stats: Record<ComponentType, number>;
}

export function FilterBar({ activeTypes, onToggleType, stats }: FilterBarProps) {
  return (
    <div className="flex items-center gap-2 px-4 py-2 bg-gray-50 border-b border-gray-200">
      <span className="text-xs font-medium text-gray-500 mr-1">Filter:</span>
      {COMPONENT_TYPES.map((type) => {
        const colors = TYPE_COLORS[type];
        const isActive = activeTypes.size === 0 || activeTypes.has(type);
        return (
          <button
            key={type}
            onClick={() => onToggleType(type)}
            className={`inline-flex items-center gap-1 px-3 py-1 text-xs font-medium rounded-full
                        transition-all ${
                          isActive
                            ? `${colors.bgSolid} text-white shadow-sm`
                            : "bg-gray-200 text-gray-500 hover:bg-gray-300"
                        }`}
          >
            {colors.label}
            <span className={isActive ? "opacity-80" : "opacity-50"}>
              {stats[type]}
            </span>
          </button>
        );
      })}
    </div>
  );
}
