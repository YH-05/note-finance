/**
 * Command card — green border, argument-hint, skill-preload badge.
 */
import type { CommandComponent } from "@/types";
import { getColorScheme } from "@/lib/colors";
import { CardHeader } from "./CardHeader";

interface CommandCardProps {
  component: CommandComponent;
}

export function CommandCard({ component }: CommandCardProps): JSX.Element {
  const colors = getColorScheme("command");
  return (
    <div className={`border-l-4 ${colors.border} bg-white rounded-lg shadow-sm p-4 hover:shadow-md transition-shadow`}>
      <CardHeader name={component.name} type="command" description={component.description} />

      {component.argumentHint && (
        <div className="mt-2">
          <span className="text-[10px] text-gray-400 uppercase tracking-wider">Arguments</span>
          <p className="mt-0.5 text-xs text-gray-600 font-mono bg-gray-50 px-2 py-1 rounded">
            {component.argumentHint}
          </p>
        </div>
      )}

      {component.skillPreload && (
        <div className="mt-2">
          <span className="inline-flex items-center gap-1 px-2 py-0.5 text-[10px] font-medium rounded-full bg-purple-50 text-purple-600">
            <svg className="w-2.5 h-2.5" fill="currentColor" viewBox="0 0 20 20">
              <path d="M11.3 1.046A1 1 0 0112 2v5h4a1 1 0 01.82 1.573l-7 10A1 1 0 018 18v-5H4a1 1 0 01-.82-1.573l7-10a1 1 0 011.12-.38z" />
            </svg>
            {component.skillPreload}
          </span>
        </div>
      )}
    </div>
  );
}
