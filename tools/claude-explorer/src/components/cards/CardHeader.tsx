/**
 * Shared card header — type badge + name + description.
 */
import type { ComponentType } from "@/types";
import { getColorScheme } from "@/lib/colors";

interface CardHeaderProps {
  name: string;
  type: ComponentType;
  description: string;
}

export function CardHeader({ name, type, description }: CardHeaderProps): JSX.Element {
  const colors = getColorScheme(type);
  return (
    <>
      <div className="flex items-start justify-between gap-2">
        <h3 className="text-sm font-semibold text-gray-900 leading-tight truncate">
          {name}
        </h3>
        <span className={`flex-shrink-0 text-[10px] font-medium px-1.5 py-0.5 rounded ${colors.bg} ${colors.text}`}>
          {colors.label}
        </span>
      </div>
      <p className="mt-1.5 text-xs text-gray-500 line-clamp-2">
        {description}
      </p>
    </>
  );
}
