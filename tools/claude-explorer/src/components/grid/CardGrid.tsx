/**
 * Responsive CSS grid for component cards.
 *
 * Adapts from 1 column on small screens to 4 columns on xl screens.
 */

import type { Component } from "@/types";
import { ComponentCard } from "@/components/cards/ComponentCard";

interface CardGridProps {
  components: Component[];
}

export function CardGrid({ components }: CardGridProps) {
  if (components.length === 0) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-center">
          <p className="text-lg text-gray-500">No components match the current filters.</p>
          <p className="text-sm text-gray-400 mt-1">
            Try adjusting your search or filter criteria.
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4 p-4">
      {components.map((component) => (
        <ComponentCard key={component.id} component={component} />
      ))}
    </div>
  );
}
