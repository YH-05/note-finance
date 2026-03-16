import { describe, it, expect, beforeEach } from "vitest";
import { renderHook, act } from "@testing-library/react";
import { useDeepLink } from "../useDeepLink";

describe("useDeepLink", () => {
  beforeEach(() => {
    // Reset URL hash before each test
    window.history.replaceState(null, "", window.location.pathname);
  });

  describe("parseHash (via initial state)", () => {
    it("returns null when there is no hash", () => {
      const { result } = renderHook(() => useDeepLink());
      expect(result.current.selectedId).toBeNull();
    });

    it("parses a valid hash like #agent:code-simplifier", () => {
      window.location.hash = "#agent:code-simplifier";
      const { result } = renderHook(() => useDeepLink());
      expect(result.current.selectedId).toBe("agent:code-simplifier");
    });

    it("rejects an invalid hash format", () => {
      window.location.hash = "#invalid format with spaces";
      const { result } = renderHook(() => useDeepLink());
      expect(result.current.selectedId).toBeNull();
    });

    it("rejects hash without colon separator", () => {
      window.location.hash = "#nocolon";
      const { result } = renderHook(() => useDeepLink());
      expect(result.current.selectedId).toBeNull();
    });

    it("accepts hash with hyphens and numbers", () => {
      window.location.hash = "#skill:tdd-development-123";
      const { result } = renderHook(() => useDeepLink());
      expect(result.current.selectedId).toBe("skill:tdd-development-123");
    });

    it("accepts hash with underscores", () => {
      window.location.hash = "#command:my_command";
      const { result } = renderHook(() => useDeepLink());
      expect(result.current.selectedId).toBe("command:my_command");
    });
  });

  describe("validIds filtering", () => {
    it("returns null when hash ID is not in validIds", () => {
      window.location.hash = "#agent:nonexistent";
      const validIds = new Set(["agent:alpha", "agent:beta"]);
      const { result } = renderHook(() => useDeepLink(validIds));
      expect(result.current.selectedId).toBeNull();
    });

    it("returns the ID when it is in validIds", () => {
      window.location.hash = "#agent:alpha";
      const validIds = new Set(["agent:alpha", "agent:beta"]);
      const { result } = renderHook(() => useDeepLink(validIds));
      expect(result.current.selectedId).toBe("agent:alpha");
    });

    it("returns the ID when validIds is undefined (no validation)", () => {
      window.location.hash = "#agent:anything";
      const { result } = renderHook(() => useDeepLink());
      expect(result.current.selectedId).toBe("agent:anything");
    });
  });

  describe("setSelectedId", () => {
    it("updates selectedId and URL hash", () => {
      const { result } = renderHook(() => useDeepLink());

      act(() => {
        result.current.setSelectedId("agent:new-selection");
      });

      expect(result.current.selectedId).toBe("agent:new-selection");
      expect(window.location.hash).toContain("agent%3Anew-selection");
    });

    it("clears hash when setting null", () => {
      window.location.hash = "#agent:something";
      const { result } = renderHook(() => useDeepLink());

      act(() => {
        result.current.setSelectedId(null);
      });

      expect(result.current.selectedId).toBeNull();
      expect(window.location.hash).toBe("");
    });
  });

  describe("hashchange event", () => {
    it("updates selectedId when hash changes externally", async () => {
      const { result } = renderHook(() => useDeepLink());
      expect(result.current.selectedId).toBeNull();

      act(() => {
        window.location.hash = "#skill:coding-standards";
        window.dispatchEvent(new HashChangeEvent("hashchange"));
      });

      expect(result.current.selectedId).toBe("skill:coding-standards");
    });

    it("validates against validIds on hash change", () => {
      const validIds = new Set(["agent:valid"]);
      const { result } = renderHook(() => useDeepLink(validIds));

      act(() => {
        window.location.hash = "#agent:invalid";
        window.dispatchEvent(new HashChangeEvent("hashchange"));
      });

      expect(result.current.selectedId).toBeNull();
    });
  });
});
