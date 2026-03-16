import { describe, it, expect } from "vitest";
import { getColorScheme, TYPE_COLORS } from "../colors";
import type { ComponentType } from "@/types";

const ALL_TYPES: ComponentType[] = ["agent", "command", "skill", "rule", "workflow"];

describe("getColorScheme", () => {
  it.each(ALL_TYPES)("returns a valid ColorScheme for type '%s'", (type) => {
    const scheme = getColorScheme(type);
    expect(scheme).toBeDefined();
    expect(typeof scheme.border).toBe("string");
    expect(typeof scheme.bg).toBe("string");
    expect(typeof scheme.bgSolid).toBe("string");
    expect(typeof scheme.text).toBe("string");
    expect(typeof scheme.textLight).toBe("string");
    expect(typeof scheme.label).toBe("string");
    expect(typeof scheme.bgHex).toBe("string");
    expect(typeof scheme.borderHex).toBe("string");
  });

  it("returns correct values for agent type", () => {
    const scheme = getColorScheme("agent");
    expect(scheme.label).toBe("Agent");
    expect(scheme.bgHex).toBe("#eff6ff");
    expect(scheme.borderHex).toBe("#60a5fa");
  });

  it("returns correct values for command type", () => {
    const scheme = getColorScheme("command");
    expect(scheme.label).toBe("Command");
    expect(scheme.bgHex).toBe("#f0fdf4");
    expect(scheme.borderHex).toBe("#4ade80");
  });

  it("returns correct values for skill type", () => {
    const scheme = getColorScheme("skill");
    expect(scheme.label).toBe("Skill");
    expect(scheme.bgHex).toBe("#faf5ff");
    expect(scheme.borderHex).toBe("#c084fc");
  });

  it("returns correct values for rule type", () => {
    const scheme = getColorScheme("rule");
    expect(scheme.label).toBe("Rule");
    expect(scheme.bgHex).toBe("#f9fafb");
    expect(scheme.borderHex).toBe("#9ca3af");
  });

  it("returns correct values for workflow type", () => {
    const scheme = getColorScheme("workflow");
    expect(scheme.label).toBe("Workflow");
    expect(scheme.bgHex).toBe("#fff7ed");
    expect(scheme.borderHex).toBe("#fb923c");
  });

  it("returns the same object as TYPE_COLORS lookup", () => {
    for (const type of ALL_TYPES) {
      expect(getColorScheme(type)).toBe(TYPE_COLORS[type]);
    }
  });

  it("has hex color values starting with #", () => {
    for (const type of ALL_TYPES) {
      const scheme = getColorScheme(type);
      expect(scheme.bgHex).toMatch(/^#[0-9a-f]{6}$/i);
      expect(scheme.borderHex).toMatch(/^#[0-9a-f]{6}$/i);
    }
  });
});
