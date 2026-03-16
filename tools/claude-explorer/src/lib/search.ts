/**
 * Fuse.js-based fuzzy search index for Claude Explorer components.
 *
 * Builds a weighted search index over component fields:
 *   - name:        weight 1.0 (exact match priority)
 *   - description: weight 0.7
 *   - slug:        weight 0.5
 *   - content:     weight 0.3 (broad content search)
 */

import Fuse from "fuse.js";
import type { IFuseOptions } from "fuse.js";
import type { Component } from "@/types";

/** Fuse.js configuration for component search. */
const FUSE_OPTIONS: IFuseOptions<Component> = {
  keys: [
    { name: "name", weight: 1.0 },
    { name: "description", weight: 0.7 },
    { name: "slug", weight: 0.5 },
    { name: "content", weight: 0.3 },
  ],
  /** Lower threshold = stricter matching. 0.4 balances recall vs precision. */
  threshold: 0.4,
  /** Include match score for potential ranking use. */
  includeScore: true,
  /** Ignore location of the match within the string. */
  ignoreLocation: true,
  /** Minimum number of characters before fuzzy matching kicks in. */
  minMatchCharLength: 2,
};

/**
 * Build a Fuse.js search index from a list of components.
 *
 * @param components - All components to index.
 * @returns A configured Fuse instance ready for searching.
 */
export function buildSearchIndex(components: Component[]): Fuse<Component> {
  return new Fuse(components, FUSE_OPTIONS);
}

/**
 * Search the index and return matching component IDs.
 *
 * When the query is empty or too short, returns null to indicate
 * "no search active" (as opposed to an empty result set).
 *
 * @param index - The Fuse.js search index.
 * @param query - The user's search string.
 * @returns Set of matching component IDs, or null if search is inactive.
 */
export function searchComponents(
  index: Fuse<Component>,
  query: string,
): Set<string> | null {
  const trimmed = query.trim();
  if (trimmed.length === 0) {
    return null;
  }

  const results = index.search(trimmed);
  return new Set(results.map((r) => r.item.id));
}
