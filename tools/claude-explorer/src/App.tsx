/**
 * Root application component.
 *
 * Integrates the graph data, fuzzy search, filter state, deep linking,
 * keyboard shortcuts, error boundary, and all layout / grid components.
 *
 * - Search: Fuse.js fuzzy search with 300ms debounce (useSearch)
 * - Deep link: URL hash <-> selected component ID sync (useDeepLink)
 * - Keyboard: Escape (close), / (search focus), 1/2 (view toggle)
 * - Filter: type + category + search results shared between both views
 */

import { lazy, Suspense, useCallback, useMemo, useRef, useState } from "react";
import { useGraphData } from "@/hooks/useGraphData";
import { useFilter } from "@/hooks/useFilter";
import { useSearch } from "@/hooks/useSearch";
import { useDeepLink } from "@/hooks/useDeepLink";
import { useKeyboardShortcuts } from "@/hooks/useKeyboardShortcuts";
import { Header } from "@/components/layout/Header";
import { Sidebar } from "@/components/layout/Sidebar";
import { FilterBar } from "@/components/grid/FilterBar";
import { CardGrid } from "@/components/grid/CardGrid";
import { DetailPanel } from "@/components/detail/DetailPanel";
import { ErrorBoundary } from "@/components/ErrorBoundary";
import { LoadingSpinner } from "@/components/LoadingSpinner";
import type { ViewMode } from "@/lib/constants";

const DependencyGraph = lazy(() =>
  import("@/components/graph/DependencyGraph").then((m) => ({
    default: m.DependencyGraph,
  })),
);

function App() {
  const { data, components, componentMap, stats, categories } = useGraphData();

  // Build a set of valid IDs for deep link validation.
  const validIds = useMemo(
    () => new Set(components.map((c) => c.id)),
    [components],
  );

  // Fuzzy search state (debounced Fuse.js).
  const { searchQuery, setSearchQuery, matchedIds, isSearching } =
    useSearch(components);

  // Type / category filter state.
  const {
    activeTypes,
    activeCategories,
    toggleType,
    toggleCategory,
    resetFilters,
    filterComponents,
  } = useFilter();

  // View mode (grid / graph).
  const [viewMode, setViewMode] = useState<ViewMode>("grid");

  // Deep-linked selection state (synced with URL hash).
  const { selectedId, setSelectedId } = useDeepLink(validIds);

  const selectedComponent = selectedId
    ? (componentMap.get(selectedId) ?? null)
    : null;

  const handleSelect = useCallback(
    (id: string) => {
      setSelectedId(id);
    },
    [setSelectedId],
  );

  const handleClose = useCallback(() => {
    setSelectedId(null);
  }, [setSelectedId]);

  // Search input element captured via useRef.
  const searchInputRef = useRef<HTMLInputElement>(null);

  // Keyboard shortcuts.
  useKeyboardShortcuts(
    useMemo(
      () => ({
        onClosePanel: handleClose,
        onFocusSearch: () => {
          searchInputRef.current?.focus();
        },
        onViewModeChange: setViewMode,
      }),
      [handleClose, setViewMode],
    ),
  );

  // Reset filters including search query.
  const handleResetAll = useCallback(() => {
    resetFilters();
    setSearchQuery("");
  }, [resetFilters, setSearchQuery]);

  // Apply all filters (type + category + fuzzy search).
  const filteredComponents = useMemo(
    () => filterComponents(components, matchedIds),
    [filterComponents, components, matchedIds],
  );

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
        searchInputRef={searchInputRef}
        isSearching={isSearching}
      />

      <div className="flex flex-1 overflow-hidden">
        <Sidebar
          activeTypes={activeTypes}
          onToggleType={toggleType}
          categories={categories}
          activeCategories={activeCategories}
          onToggleCategory={toggleCategory}
          onResetFilters={handleResetAll}
        />

        <main className="flex-1 flex flex-col overflow-hidden">
          <FilterBar
            activeTypes={activeTypes}
            onToggleType={toggleType}
            stats={stats}
          />

          <ErrorBoundary>
            {viewMode === "grid" ? (
              <div className="flex-1 overflow-y-auto">
                <CardGrid
                  components={filteredComponents}
                  onSelect={handleSelect}
                />
              </div>
            ) : (
              <div className="flex-1">
                <Suspense
                  fallback={
                    <LoadingSpinner message="Loading graph..." />
                  }
                >
                  <DependencyGraph
                    components={filteredComponents}
                    edges={data.edges}
                    onNodeClick={handleSelect}
                  />
                </Suspense>
              </div>
            )}
          </ErrorBoundary>
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
