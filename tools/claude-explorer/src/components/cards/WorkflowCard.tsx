/**
 * Workflow card — orange border.
 */
import type { WorkflowComponent } from "@/types";
import { getColorScheme } from "@/lib/colors";
import { CardHeader } from "./CardHeader";

interface WorkflowCardProps {
  component: WorkflowComponent;
}

export function WorkflowCard({ component }: WorkflowCardProps): JSX.Element {
  const colors = getColorScheme("workflow");
  return (
    <div className={`border-l-4 ${colors.border} bg-white rounded-lg shadow-sm p-4 hover:shadow-md transition-shadow`}>
      <CardHeader name={component.name} type="workflow" description={component.description} />
      <p className="mt-2 text-[10px] text-gray-400 font-mono truncate">{component.filePath}</p>
    </div>
  );
}
