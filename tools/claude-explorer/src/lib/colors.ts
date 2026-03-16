/**
 * Type-based color palette for component cards.
 *
 * Each ComponentType maps to a Tailwind-compatible color scheme used
 * for card borders, badges, and filter pills.
 */

import type { ComponentType } from "@/types";

export interface ColorScheme {
  /** Tailwind border class, e.g. "border-blue-400" */
  border: string;
  /** Tailwind background class for badges/pills, e.g. "bg-blue-100" */
  bg: string;
  /** Tailwind background class for solid badges, e.g. "bg-blue-500" */
  bgSolid: string;
  /** Tailwind text class, e.g. "text-blue-700" */
  text: string;
  /** Tailwind text class for light backgrounds */
  textLight: string;
  /** Human-readable label */
  label: string;
  /** Hex background color for React Flow nodes */
  bgHex: string;
  /** Hex border color for React Flow nodes */
  borderHex: string;
}

export const TYPE_COLORS: Record<ComponentType, ColorScheme> = {
  agent: {
    border: "border-blue-400",
    bg: "bg-blue-50",
    bgSolid: "bg-blue-500",
    text: "text-blue-700",
    textLight: "text-blue-600",
    label: "Agent",
    bgHex: "#eff6ff",
    borderHex: "#60a5fa",
  },
  command: {
    border: "border-green-400",
    bg: "bg-green-50",
    bgSolid: "bg-green-500",
    text: "text-green-700",
    textLight: "text-green-600",
    label: "Command",
    bgHex: "#f0fdf4",
    borderHex: "#4ade80",
  },
  skill: {
    border: "border-purple-400",
    bg: "bg-purple-50",
    bgSolid: "bg-purple-500",
    text: "text-purple-700",
    textLight: "text-purple-600",
    label: "Skill",
    bgHex: "#faf5ff",
    borderHex: "#c084fc",
  },
  rule: {
    border: "border-gray-400",
    bg: "bg-gray-50",
    bgSolid: "bg-gray-500",
    text: "text-gray-700",
    textLight: "text-gray-600",
    label: "Rule",
    bgHex: "#f9fafb",
    borderHex: "#9ca3af",
  },
  workflow: {
    border: "border-orange-400",
    bg: "bg-orange-50",
    bgSolid: "bg-orange-500",
    text: "text-orange-700",
    textLight: "text-orange-600",
    label: "Workflow",
    bgHex: "#fff7ed",
    borderHex: "#fb923c",
  },
};

/**
 * Get the color scheme for a given component type.
 */
export function getColorScheme(type: ComponentType): ColorScheme {
  return TYPE_COLORS[type];
}
