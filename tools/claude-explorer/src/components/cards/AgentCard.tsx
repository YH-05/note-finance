/**
 * Agent card — blue border, model/color badges, skills/tools pills.
 */

import type { AgentComponent } from "@/types";

interface AgentCardProps {
  component: AgentComponent;
}

export function AgentCard({ component }: AgentCardProps) {
  return (
    <div className="border-l-4 border-blue-400 bg-white rounded-lg shadow-sm p-4 hover:shadow-md transition-shadow">
      {/* Header row */}
      <div className="flex items-start justify-between gap-2">
        <h3 className="text-sm font-semibold text-gray-900 leading-tight truncate">
          {component.name}
        </h3>
        <span className="flex-shrink-0 text-[10px] font-medium px-1.5 py-0.5 rounded bg-blue-50 text-blue-600">
          Agent
        </span>
      </div>

      {/* Description */}
      <p className="mt-1.5 text-xs text-gray-500 line-clamp-2">
        {component.description}
      </p>

      {/* Model & color badges */}
      <div className="mt-2 flex items-center gap-1.5">
        {component.model && (
          <span className="inline-flex items-center px-2 py-0.5 text-[10px] font-medium rounded-full bg-gray-100 text-gray-600">
            {component.model}
          </span>
        )}
        {component.color && (
          <span className="inline-flex items-center px-2 py-0.5 text-[10px] font-medium rounded-full bg-gray-100 text-gray-600">
            {component.color}
          </span>
        )}
        {component.category && (
          <span className="inline-flex items-center px-2 py-0.5 text-[10px] font-medium rounded-full bg-blue-50 text-blue-600">
            {component.category}
          </span>
        )}
      </div>

      {/* Skills pills */}
      {component.skills.length > 0 && (
        <div className="mt-2">
          <span className="text-[10px] text-gray-400 uppercase tracking-wider">
            Skills
          </span>
          <div className="mt-0.5 flex flex-wrap gap-1">
            {component.skills.map((s) => (
              <span
                key={s}
                className="px-1.5 py-0.5 text-[10px] rounded bg-purple-50 text-purple-600"
              >
                {s}
              </span>
            ))}
          </div>
        </div>
      )}

      {/* Tools pills */}
      {component.tools.length > 0 && (
        <div className="mt-2">
          <span className="text-[10px] text-gray-400 uppercase tracking-wider">
            Tools
          </span>
          <div className="mt-0.5 flex flex-wrap gap-1">
            {component.tools.map((t) => (
              <span
                key={t}
                className="px-1.5 py-0.5 text-[10px] rounded bg-gray-100 text-gray-600"
              >
                {t}
              </span>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
