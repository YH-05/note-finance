import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { renderHook } from "@testing-library/react";
import { useKeyboardShortcuts } from "../useKeyboardShortcuts";

/**
 * Dispatch a keydown event on document.body so it bubbles to the
 * window listener with a proper event.target (HTMLElement with tagName).
 */
function fireKeyDown(key: string, options: Partial<KeyboardEventInit> = {}) {
  const event = new KeyboardEvent("keydown", {
    key,
    bubbles: true,
    cancelable: true,
    ...options,
  });
  document.body.dispatchEvent(event);
}

describe("useKeyboardShortcuts", () => {
  let handlers: {
    onClosePanel: () => void;
    onFocusSearch: () => void;
    onViewModeChange: (mode: "grid" | "graph") => void;
  };

  beforeEach(() => {
    handlers = {
      onClosePanel: vi.fn(),
      onFocusSearch: vi.fn(),
      onViewModeChange: vi.fn(),
    };
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("calls onClosePanel when Escape is pressed", () => {
    renderHook(() => useKeyboardShortcuts(handlers));

    fireKeyDown("Escape");

    expect(handlers.onClosePanel).toHaveBeenCalledTimes(1);
  });

  it("calls onFocusSearch when / is pressed", () => {
    renderHook(() => useKeyboardShortcuts(handlers));

    fireKeyDown("/");

    expect(handlers.onFocusSearch).toHaveBeenCalledTimes(1);
  });

  it('calls onViewModeChange("grid") when 1 is pressed', () => {
    renderHook(() => useKeyboardShortcuts(handlers));

    fireKeyDown("1");

    expect(handlers.onViewModeChange).toHaveBeenCalledWith("grid");
  });

  it('calls onViewModeChange("graph") when 2 is pressed', () => {
    renderHook(() => useKeyboardShortcuts(handlers));

    fireKeyDown("2");

    expect(handlers.onViewModeChange).toHaveBeenCalledWith("graph");
  });

  it("does not fire / shortcut when metaKey is held", () => {
    renderHook(() => useKeyboardShortcuts(handlers));

    fireKeyDown("/", { metaKey: true });

    expect(handlers.onFocusSearch).not.toHaveBeenCalled();
  });

  it("does not fire / shortcut when ctrlKey is held", () => {
    renderHook(() => useKeyboardShortcuts(handlers));

    fireKeyDown("/", { ctrlKey: true });

    expect(handlers.onFocusSearch).not.toHaveBeenCalled();
  });

  it("does not fire / shortcut when altKey is held", () => {
    renderHook(() => useKeyboardShortcuts(handlers));

    fireKeyDown("/", { altKey: true });

    expect(handlers.onFocusSearch).not.toHaveBeenCalled();
  });

  it("does not fire 1/2 shortcuts when metaKey is held", () => {
    renderHook(() => useKeyboardShortcuts(handlers));

    fireKeyDown("1", { metaKey: true });
    fireKeyDown("2", { metaKey: true });

    expect(handlers.onViewModeChange).not.toHaveBeenCalled();
  });

  describe("input element focus", () => {
    it("ignores / when an input element is focused", () => {
      renderHook(() => useKeyboardShortcuts(handlers));

      const input = document.createElement("input");
      document.body.appendChild(input);
      input.focus();

      const event = new KeyboardEvent("keydown", {
        key: "/",
        bubbles: true,
        cancelable: true,
      });
      input.dispatchEvent(event);

      expect(handlers.onFocusSearch).not.toHaveBeenCalled();

      document.body.removeChild(input);
    });

    it("ignores 1 when a textarea is focused", () => {
      renderHook(() => useKeyboardShortcuts(handlers));

      const textarea = document.createElement("textarea");
      document.body.appendChild(textarea);
      textarea.focus();

      const event = new KeyboardEvent("keydown", {
        key: "1",
        bubbles: true,
        cancelable: true,
      });
      textarea.dispatchEvent(event);

      expect(handlers.onViewModeChange).not.toHaveBeenCalled();

      document.body.removeChild(textarea);
    });

    it("still fires Escape when an input is focused (and blurs it)", () => {
      renderHook(() => useKeyboardShortcuts(handlers));

      const input = document.createElement("input");
      document.body.appendChild(input);
      input.focus();

      // Spy on blur
      const blurSpy = vi.spyOn(input, "blur");

      const event = new KeyboardEvent("keydown", {
        key: "Escape",
        bubbles: true,
        cancelable: true,
      });
      input.dispatchEvent(event);

      expect(blurSpy).toHaveBeenCalled();
      expect(handlers.onClosePanel).toHaveBeenCalledTimes(1);

      document.body.removeChild(input);
    });
  });

  it("cleans up event listener on unmount", () => {
    const removeListenerSpy = vi.spyOn(window, "removeEventListener");
    const { unmount } = renderHook(() => useKeyboardShortcuts(handlers));

    unmount();

    expect(removeListenerSpy).toHaveBeenCalledWith("keydown", expect.any(Function));
  });
});
