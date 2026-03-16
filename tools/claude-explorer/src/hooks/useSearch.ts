/**
 * Hook for debounced fuzzy search over components.
 */
import { useCallback, useMemo, useState } from "react";
import type { Component } from "@/types";
import { buildSearchIndex, searchComponents } from "@/lib/search";
import { useDebounce } from "./useDebounce";

const DEBOUNCE_MS = 300;

export interface UseSearchReturn {
  searchQuery: string;
  setSearchQuery: (query: string) => void;
  matchedIds: Set<string> | null;
  isSearching: boolean;
}

export function useSearch(components: Component[]): UseSearchReturn {
  const [searchQuery, setSearchQuery] = useState("");

  const { debouncedValue: debouncedQuery, isPending: isSearching } =
    useDebounce(searchQuery, DEBOUNCE_MS);

  const searchIndex = useMemo(
    () => buildSearchIndex(components),
    [components],
  );

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
