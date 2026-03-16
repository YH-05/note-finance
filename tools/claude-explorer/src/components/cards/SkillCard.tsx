/**
 * Skill card — purple border, allowed-tools list.
 */
import type { SkillComponent } from "@/types";
import { getColorScheme } from "@/lib/colors";
import { CardHeader } from "./CardHeader";
import { PillList } from "./PillList";

interface SkillCardProps {
  component: SkillComponent;
}

export function SkillCard({ component }: SkillCardProps): JSX.Element {
  const colors = getColorScheme("skill");
  return (
    <div className={`border-l-4 ${colors.border} bg-white rounded-lg shadow-sm p-4 hover:shadow-md transition-shadow`}>
      <CardHeader name={component.name} type="skill" description={component.description} />
      <PillList label="Allowed Tools" items={component.allowedTools} colorClass="bg-gray-100 text-gray-600" />
      {component.subFiles.length > 0 && (
        <div className="mt-2">
          <span className="text-[10px] text-gray-400">
            {component.subFiles.length} auxiliary file{component.subFiles.length > 1 ? "s" : ""}
          </span>
        </div>
      )}
    </div>
  );
}
