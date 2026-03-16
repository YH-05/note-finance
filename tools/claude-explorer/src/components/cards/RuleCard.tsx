/**
 * Rule card — gray border, minimal card.
 */

import type { RuleComponent } from "@/types";

interface RuleCardProps {
  component: RuleComponent;
}

export function RuleCard({ component }: RuleCardProps) {
  return (
    <div className="border-l-4 border-gray-400 bg-white rounded-lg shadow-sm p-4 hover:shadow-md transition-shadow">
      {/* Header row */}
      <div className="flex items-start justify-between gap-2">
        <h3 className="text-sm font-semibold text-gray-900 leading-tight truncate">
          {component.name}
        </h3>
        <span className="flex-shrink-0 text-[10px] font-medium px-1.5 py-0.5 rounded bg-gray-100 text-gray-600">
          Rule
        </span>
      </div>

      {/* Description */}
      <p className="mt-1.5 text-xs text-gray-500 line-clamp-2">
        {component.description}
      </p>

      {/* File path */}
      <p className="mt-2 text-[10px] text-gray-400 font-mono truncate">
        {component.filePath}
      </p>
    </div>
  );
}
