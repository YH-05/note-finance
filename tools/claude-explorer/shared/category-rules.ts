/**
 * Agent category prefix rules -- shared between build-time scripts and runtime.
 */
export interface CategoryRule {
  prefixes: string[];
  category: string;
}

export const CATEGORY_RULES: CategoryRule[] = [
  { prefixes: ["pr-"], category: "PR Review" },
  { prefixes: ["wr-"], category: "Weekly Report" },
  {
    prefixes: ["weekly-report-", "weekly-comment-"],
    category: "Weekly Report",
  },
  { prefixes: ["finance-"], category: "Finance" },
  { prefixes: ["test-"], category: "Testing" },
  { prefixes: ["exp-", "experience-"], category: "Experience DB" },
  { prefixes: ["csa-"], category: "Case Study" },
  { prefixes: ["asset-management-"], category: "Asset Management" },
  { prefixes: ["ai-research-"], category: "AI Research" },
  { prefixes: ["news-"], category: "News" },
  { prefixes: ["reddit-"], category: "Reddit" },
  { prefixes: ["market-"], category: "Market" },
  { prefixes: ["research-"], category: "Research" },
];

/**
 * Infer agent category from slug using prefix rules.
 */
export function inferCategory(slug: string): string {
  for (const rule of CATEGORY_RULES) {
    for (const prefix of rule.prefixes) {
      if (slug.startsWith(prefix)) {
        return rule.category;
      }
    }
  }
  return "General";
}
