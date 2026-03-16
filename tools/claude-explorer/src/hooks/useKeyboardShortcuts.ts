/**
 * Hook for global keyboard shortcuts in Claude Explorer.
 *
 * Shortcuts:
 *   - Escape: Close the detail panel
 *   - `/`:    Focus the search input
 *   - `1`:    Switch to Grid view
 *   - `2`:    Switch to Graph view
 *
 * Shortcuts are disabled when the user is typing in an input or textarea
 * to avoid interfering with normal text entry.
 */

import { useEffect } from "react";
import type { ViewMode } from "@/lib/constants";

export interface KeyboardShortcutHandlers {
  /** Close the detail panel. */
  onClosePanel: () => void;
  /** Focus the search input element. */
  onFocusSearch: () => void;
  /** Change the view mode. */
  onViewModeChange: (mode: ViewMode) => void;
}

/**
 * Registers global keyboard event listeners for the application.
 *
 * @param handlers - Callback functions for each shortcut action.
 */
export function useKeyboardShortcuts(handlers: KeyboardShortcutHandlers): void {
  useEffect(() => {
    const handleKeyDown = (event: KeyboardEvent) => {
      // Skip when user is typing in an input, textarea, or contentEditable
      const target = event.target as HTMLElement;
      const tagName = target.tagName.toLowerCase();
      const isEditable =
        tagName === "input" ||
        tagName === "textarea" ||
        target.isContentEditable;

      // Escape works even in input fields (to dismiss/close)
      if (event.key === "Escape") {
        event.preventDefault();
        // If focused in search input, blur it first
        if (isEditable) {
          target.blur();
        }
        handlers.onClosePanel();
        return;
      }

      // Other shortcuts only fire outside editable elements
      if (isEditable) {
        return;
      }

      // Don't handle shortcuts when meta/ctrl keys are held (OS shortcuts)
      if (event.metaKey || event.ctrlKey || event.altKey) {
        return;
      }

      switch (event.key) {
        case "/":
          event.preventDefault();
          handlers.onFocusSearch();
          break;
        case "1":
          event.preventDefault();
          handlers.onViewModeChange("grid");
          break;
        case "2":
          event.preventDefault();
          handlers.onViewModeChange("graph");
          break;
      }
    };

    window.addEventListener("keydown", handleKeyDown);
    return () => {
      window.removeEventListener("keydown", handleKeyDown);
    };
  }, [handlers]);
}
