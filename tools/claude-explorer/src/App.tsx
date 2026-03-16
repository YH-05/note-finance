/**
 * Root application component.
 *
 * Integrates the graph data, filter state, and all layout / grid components.
 * Manages the Grid/Graph view toggle and the detail panel selection state.
 * Filter state is shared between both views.
 */

import { useCallback, useState } from "react";
import { useGraphData } from "@/hooks/useGraphData";
import { useFilter } from "@/hooks/useFilter";
import { Header } from "@/components/layout/Header";
import { Sidebar } from "@/components/layout/Sidebar";
import { FilterBar } from "@/components/grid/FilterBar";
import { CardGrid } from "@/components/grid/CardGrid";
import { DependencyGraph } from "@/components/graph/DependencyGraph";
import { DetailPanel } from "@/components/detail/DetailPanel";
import type { ViewMode } from "@/lib/constants";

function App() {
  const { data, components, componentMap, stats, categories } = useGraphData();
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
  const [selectedId, setSelectedId] = useState<string | null>(null);

  const selectedComponent = selectedId
    ? (componentMap.get(selectedId) ?? null)
    : null;

  const handleSelect = useCallback((id: string) => {
    setSelectedId(id);
  }, []);

  const handleClose = useCallback(() => {
    setSelectedId(null);
  }, []);

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

        <main className="flex-1 flex flex-col overflow-hidden">
          <FilterBar
            activeTypes={activeTypes}
            onToggleType={toggleType}
            stats={stats}
          />

          {viewMode === "grid" ? (
            <div className="flex-1 overflow-y-auto">
              <CardGrid
                components={filteredComponents}
                onSelect={handleSelect}
              />
            </div>
          ) : (
            <div className="flex-1">
              <DependencyGraph
                components={filteredComponents}
                edges={data.edges}
                onNodeClick={handleSelect}
              />
            </div>
          )}
        </main>
      </div>

      {/* Detail panel (slides in from right) */}
      <DetailPanel
        component={selectedComponent}
        edges={data.edges}
        componentMap={componentMap}
        onSelect={handleSelect}
        onClose={handleClose}
      />
    </div>
  );
}

export default App;
