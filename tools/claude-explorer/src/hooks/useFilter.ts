/**
 * Hook to manage filter state for the component explorer.
 *
 * Tracks active component types and categories. Search is now handled
 * externally by `useSearch` (Fuse.js fuzzy search) and passed in as
 * `matchedIds`. Components are visible when they match ALL active filters:
 *   - type is in activeTypes (or activeTypes is empty = all)
 *   - category is in activeCategories (or activeCategories is empty = all)
 *   - id is in matchedIds (if search is active, i.e. matchedIds !== null)
 */

import { useCallback, useMemo, useState } from "react";
import type { Component, ComponentType } from "@/types";

export interface UseFilterReturn {
  /** Currently active type filters. Empty = all types shown. */
  activeTypes: Set<ComponentType>;
  /** Currently active category filters. Empty = all categories shown. */
  activeCategories: Set<string>;
  /** Toggle a type on/off. */
  toggleType: (type: ComponentType) => void;
  /** Toggle a category on/off. */
  toggleCategory: (category: string) => void;
  /** Reset all filters (type + category only; search is managed externally). */
  resetFilters: () => void;
  /**
   * Filter a list of components using the current type/category state
   * plus an optional set of fuzzy-search-matched IDs.
   *
   * @param components - Full component list.
   * @param matchedIds - IDs from fuzzy search, or null if search inactive.
   */
  filterComponents: (
    components: Component[],
    matchedIds: Set<string> | null,
  ) => Component[];
}

export function useFilter(): UseFilterReturn {
  const [activeTypes, setActiveTypes] = useState<Set<ComponentType>>(new Set());
  const [activeCategories, setActiveCategories] = useState<Set<string>>(
    new Set(),
  );

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
  }, []);

  const filterComponents = useMemo(() => {
    return (
      components: Component[],
      matchedIds: Set<string> | null,
    ): Component[] => {
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

        // Fuzzy search filter (from useSearch hook)
        if (matchedIds !== null && !matchedIds.has(c.id)) {
          return false;
        }

        return true;
      });
    };
  }, [activeTypes, activeCategories]);

  return {
    activeTypes,
    activeCategories,
    toggleType,
    toggleCategory,
    resetFilters,
    filterComponents,
  };
}
