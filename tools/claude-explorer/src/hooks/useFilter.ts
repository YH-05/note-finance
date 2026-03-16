/**
 * Hook to manage filter state for the component explorer.
 *
 * Tracks active component types and categories, plus a search query.
 * Components are visible when they match ALL active filters:
 *   - type is in activeTypes (or activeTypes is empty = all)
 *   - category is in activeCategories (or activeCategories is empty = all)
 *   - name/description matches searchQuery (if non-empty)
 */

import { useCallback, useMemo, useState } from "react";
import type { Component, ComponentType } from "@/types";

export interface UseFilterReturn {
  /** Currently active type filters. Empty = all types shown. */
  activeTypes: Set<ComponentType>;
  /** Currently active category filters. Empty = all categories shown. */
  activeCategories: Set<string>;
  /** Free-text search query. */
  searchQuery: string;
  /** Toggle a type on/off. */
  toggleType: (type: ComponentType) => void;
  /** Toggle a category on/off. */
  toggleCategory: (category: string) => void;
  /** Set the search query. */
  setSearchQuery: (query: string) => void;
  /** Reset all filters. */
  resetFilters: () => void;
  /** Filter a list of components using the current state. */
  filterComponents: (components: Component[]) => Component[];
}

export function useFilter(): UseFilterReturn {
  const [activeTypes, setActiveTypes] = useState<Set<ComponentType>>(new Set());
  const [activeCategories, setActiveCategories] = useState<Set<string>>(
    new Set(),
  );
  const [searchQuery, setSearchQuery] = useState("");

  const toggleType = useCallback((type: ComponentType) => {
    setActiveTypes((prev) => {
      const next = new Set(prev);
      if (next.has(type)) {
        next.delete(type);
      } else {
        next.add(type);
      }
      return next;
    });
  }, []);

  const toggleCategory = useCallback((category: string) => {
    setActiveCategories((prev) => {
      const next = new Set(prev);
      if (next.has(category)) {
        next.delete(category);
      } else {
        next.add(category);
      }
      return next;
    });
  }, []);

  const resetFilters = useCallback(() => {
    setActiveTypes(new Set());
    setActiveCategories(new Set());
    setSearchQuery("");
  }, []);

  const filterComponents = useMemo(() => {
    const lowerQuery = searchQuery.toLowerCase();

    return (components: Component[]): Component[] => {
      return components.filter((c) => {
        // Type filter
        if (activeTypes.size > 0 && !activeTypes.has(c.type)) {
          return false;
        }

        // Category filter (only agents have categories)
        if (activeCategories.size > 0) {
          if (c.type === "agent") {
            if (!activeCategories.has(c.category)) {
              return false;
            }
          }
          // Non-agent types pass category filter if no type restriction,
          // but are hidden if category filter is active (they have no category)
          else {
            return false;
          }
        }

        // Search filter
        if (lowerQuery) {
          const nameMatch = c.name.toLowerCase().includes(lowerQuery);
          const descMatch = c.description.toLowerCase().includes(lowerQuery);
          const slugMatch = c.slug.toLowerCase().includes(lowerQuery);
          if (!nameMatch && !descMatch && !slugMatch) {
            return false;
          }
        }

        return true;
      });
    };
  }, [activeTypes, activeCategories, searchQuery]);

  return {
    activeTypes,
    activeCategories,
    searchQuery,
    toggleType,
    toggleCategory,
    setSearchQuery,
    resetFilters,
    filterComponents,
  };
}
