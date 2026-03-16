/**
 * Skill card — purple border, allowed-tools list.
 */

import type { SkillComponent } from "@/types";

interface SkillCardProps {
  component: SkillComponent;
}

export function SkillCard({ component }: SkillCardProps) {
  return (
    <div className="border-l-4 border-purple-400 bg-white rounded-lg shadow-sm p-4 hover:shadow-md transition-shadow">
      {/* Header row */}
      <div className="flex items-start justify-between gap-2">
        <h3 className="text-sm font-semibold text-gray-900 leading-tight truncate">
          {component.name}
        </h3>
        <span className="flex-shrink-0 text-[10px] font-medium px-1.5 py-0.5 rounded bg-purple-50 text-purple-600">
          Skill
        </span>
      </div>

      {/* Description */}
      <p className="mt-1.5 text-xs text-gray-500 line-clamp-2">
        {component.description}
      </p>

      {/* Allowed tools */}
      {component.allowedTools.length > 0 && (
        <div className="mt-2">
          <span className="text-[10px] text-gray-400 uppercase tracking-wider">
            Allowed Tools
          </span>
          <div className="mt-0.5 flex flex-wrap gap-1">
            {component.allowedTools.map((tool) => (
              <span
                key={tool}
                className="px-1.5 py-0.5 text-[10px] rounded bg-gray-100 text-gray-600"
              >
                {tool}
              </span>
            ))}
          </div>
        </div>
      )}

      {/* Sub-files count */}
      {component.subFiles.length > 0 && (
        <div className="mt-2">
          <span className="text-[10px] text-gray-400">
            {component.subFiles.length} auxiliary file
            {component.subFiles.length > 1 ? "s" : ""}
          </span>
        </div>
      )}
    </div>
  );
}
