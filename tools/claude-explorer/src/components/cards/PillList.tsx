/**
 * Shared pill list for rendering arrays of tags/items.
 */
interface PillListProps {
  label: string;
  items: string[];
  colorClass: string;
}

export function PillList({ label, items, colorClass }: PillListProps): JSX.Element | null {
  if (items.length === 0) return null;
  return (
    <div className="mt-2">
      <span className="text-[10px] text-gray-400 uppercase tracking-wider">
        {label}
      </span>
      <div className="mt-0.5 flex flex-wrap gap-1">
        {items.map((item) => (
          <span key={item} className={`px-1.5 py-0.5 text-[10px] rounded ${colorClass}`}>
            {item}
          </span>
        ))}
      </div>
    </div>
  );
}
