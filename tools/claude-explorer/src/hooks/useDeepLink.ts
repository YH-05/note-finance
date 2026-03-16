/**
 * Hook to synchronize the selected component ID with the URL hash.
 *
 * Hash format: `#agent:code-simplifier` (matches the component ID).
 *
 * - On mount, reads the current URL hash and returns the initial selection.
 * - When `setSelectedId` is called, updates the URL hash (without navigation).
 * - Listens for browser `popstate` and `hashchange` events to support
 *   back/forward navigation.
 */

import { useCallback, useEffect, useRef, useState } from "react";

/** Allowed characters in component IDs: type:slug format. */
const VALID_HASH_RE = /^[a-z]+:[a-zA-Z0-9_-]+$/;

/**
 * Parse the URL hash into a component ID.
 *
 * Strips the leading "#", validates format, and returns the ID or null.
 */
function parseHash(): string | null {
  const hash = window.location.hash.slice(1); // remove "#"
  if (hash.length === 0) return null;
  const decoded = decodeURIComponent(hash);
  return VALID_HASH_RE.test(decoded) ? decoded : null;
}

/**
 * Write a component ID to the URL hash (or clear it).
 */
function writeHash(id: string | null): void {
  if (id) {
    window.history.replaceState(null, "", `#${encodeURIComponent(id)}`);
  } else {
    // Remove hash without triggering a scroll
    window.history.replaceState(null, "", window.location.pathname + window.location.search);
  }
}

export interface UseDeepLinkReturn {
  /** Currently selected component ID (synced with URL hash). */
  selectedId: string | null;
  /** Select a component (updates URL hash). */
  setSelectedId: (id: string | null) => void;
}

/**
 * Manages bidirectional sync between selected component ID and URL hash.
 *
 * @param validIds - Optional set of valid component IDs for hash validation.
 */
export function useDeepLink(validIds?: Set<string>): UseDeepLinkReturn {
  const [selectedId, setSelectedIdState] = useState<string | null>(() => {
    const initial = parseHash();
    // Validate against known IDs if provided
    if (initial && validIds && !validIds.has(initial)) {
      return null;
    }
    return initial;
  });

  // Update URL hash when selection changes programmatically.
  const setSelectedId = useCallback((id: string | null) => {
    setSelectedIdState(id);
    writeHash(id);
  }, []);

  // Keep a ref to avoid re-registering listeners on every selectedId change.
  const selectedIdRef = useRef(selectedId);
  useEffect(() => {
    selectedIdRef.current = selectedId;
  }, [selectedId]);

  // Listen for hash changes from browser navigation (back/forward).
  useEffect(() => {
    const handleHashChange = () => {
      const newId = parseHash();
      if (newId !== selectedIdRef.current) {
        // Validate against known IDs if provided
        if (newId && validIds && !validIds.has(newId)) {
          setSelectedIdState(null);
        } else {
          setSelectedIdState(newId);
        }
      }
    };

    window.addEventListener("hashchange", handleHashChange);
    window.addEventListener("popstate", handleHashChange);

    return () => {
      window.removeEventListener("hashchange", handleHashChange);
      window.removeEventListener("popstate", handleHashChange);
    };
  }, [validIds]);

  return {
    selectedId,
    setSelectedId,
  };
}
