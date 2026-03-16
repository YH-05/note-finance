/**
 * Rule card — gray border, minimal card.
 */
import type { RuleComponent } from "@/types";
import { getColorScheme } from "@/lib/colors";
import { CardHeader } from "./CardHeader";

interface RuleCardProps {
  component: RuleComponent;
}

export function RuleCard({ component }: RuleCardProps): JSX.Element {
  const colors = getColorScheme("rule");
  return (
    <div className={`border-l-4 ${colors.border} bg-white rounded-lg shadow-sm p-4 hover:shadow-md transition-shadow`}>
      <CardHeader name={component.name} type="rule" description={component.description} />
      <p className="mt-2 text-[10px] text-gray-400 font-mono truncate">{component.filePath}</p>
    </div>
  );
}
