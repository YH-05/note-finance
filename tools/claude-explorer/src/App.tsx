/**
 * Root application component.
 *
 * Integrates the graph data, filter state, and all layout / grid components.
 * Manages the Grid/Graph view toggle (Graph view is a future placeholder).
 */

import { useState } from "react";
import { useGraphData } from "@/hooks/useGraphData";
import { useFilter } from "@/hooks/useFilter";
import { Header } from "@/components/layout/Header";
import { Sidebar } from "@/components/layout/Sidebar";
import { FilterBar } from "@/components/grid/FilterBar";
import { CardGrid } from "@/components/grid/CardGrid";
import type { ViewMode } from "@/lib/constants";

function App() {
  const { components, stats, categories } = useGraphData();
  const {
    activeTypes,
    activeCategories,
    searchQuery,
    toggleType,
    toggleCategory,
    setSearchQuery,
    resetFilters,
    filterComponents,
  } = useFilter();

  const [viewMode, setViewMode] = useState<ViewMode>("grid");

  const filteredComponents = filterComponents(components);

  return (
    <div className="min-h-screen bg-gray-50 flex flex-col">
      <Header
        stats={stats}
        searchQuery={searchQuery}
        onSearchChange={setSearchQuery}
        viewMode={viewMode}
        onViewModeChange={setViewMode}
        filteredCount={filteredComponents.length}
        totalCount={components.length}
      />

      <div className="flex flex-1 overflow-hidden">
        <Sidebar
          activeTypes={activeTypes}
          onToggleType={toggleType}
          categories={categories}
          activeCategories={activeCategories}
          onToggleCategory={toggleCategory}
          onResetFilters={resetFilters}
        />

        <main className="flex-1 overflow-y-auto">
          <FilterBar
            activeTypes={activeTypes}
            onToggleType={toggleType}
            stats={stats}
          />

          {viewMode === "grid" ? (
            <CardGrid components={filteredComponents} />
          ) : (
            <div className="flex items-center justify-center h-64">
              <p className="text-gray-500">
                Graph view will be available in a future release.
              </p>
            </div>
          )}
        </main>
      </div>
    </div>
  );
}

export default App;
