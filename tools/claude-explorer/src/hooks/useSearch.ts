/**
 * Hook for debounced fuzzy search over components.
 *
 * Builds a Fuse.js index once (when components change) and applies
 * a 300ms debounced search to avoid excessive re-renders while typing.
 *
 * Returns the set of matching component IDs (or null when no search
 * is active), which can be used by both CardGrid and DependencyGraph
 * to filter their displayed components.
 */

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import type { Component } from "@/types";
import { buildSearchIndex, searchComponents } from "@/lib/search";

/** Debounce delay in milliseconds. */
const DEBOUNCE_MS = 300;

export interface UseSearchReturn {
  /** Current search query (updated immediately on keystroke). */
  searchQuery: string;
  /** Update the search query. */
  setSearchQuery: (query: string) => void;
  /** Set of component IDs matching the debounced query, or null if inactive. */
  matchedIds: Set<string> | null;
  /** Whether a debounced search is pending. */
  isSearching: boolean;
}

/**
 * Provides debounced fuzzy search over a list of components.
 *
 * @param components - All components to search over.
 */
export function useSearch(components: Component[]): UseSearchReturn {
  const [searchQuery, setSearchQuery] = useState("");
  const [debouncedQuery, setDebouncedQuery] = useState("");
  const [isSearching, setIsSearching] = useState(false);
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  // Build the search index (memoized on component list identity).
  const searchIndex = useMemo(
    () => buildSearchIndex(components),
    [components],
  );

  // Debounce the query update.
  useEffect(() => {
    if (searchQuery !== debouncedQuery) {
      setIsSearching(true);
    }

    timerRef.current = setTimeout(() => {
      setDebouncedQuery(searchQuery);
      setIsSearching(false);
    }, DEBOUNCE_MS);

    return () => {
      if (timerRef.current !== null) {
        clearTimeout(timerRef.current);
      }
    };
  }, [searchQuery, debouncedQuery]);

  // Compute matching IDs from the debounced query.
  const matchedIds = useMemo(
    () => searchComponents(searchIndex, debouncedQuery),
    [searchIndex, debouncedQuery],
  );

  const handleSetSearchQuery = useCallback((query: string) => {
    setSearchQuery(query);
  }, []);

  return {
    searchQuery,
    setSearchQuery: handleSetSearchQuery,
    matchedIds,
    isSearching,
  };
}
