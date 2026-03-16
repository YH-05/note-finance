/**
 * Agent card — blue border, model/color badges, skills/tools pills.
 */
import type { AgentComponent } from "@/types";
import { getColorScheme } from "@/lib/colors";
import { CardHeader } from "./CardHeader";
import { PillList } from "./PillList";

interface AgentCardProps {
  component: AgentComponent;
}

export function AgentCard({ component }: AgentCardProps): JSX.Element {
  const colors = getColorScheme("agent");
  return (
    <div className={`border-l-4 ${colors.border} bg-white rounded-lg shadow-sm p-4 hover:shadow-md transition-shadow`}>
      <CardHeader name={component.name} type="agent" description={component.description} />

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

      <PillList label="Skills" items={component.skills} colorClass="bg-purple-50 text-purple-600" />
      <PillList label="Tools" items={component.tools} colorClass="bg-gray-100 text-gray-600" />
    </div>
  );
}
