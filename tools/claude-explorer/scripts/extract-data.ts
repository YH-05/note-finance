#!/usr/bin/env tsx
/**
 * extract-data.ts
 *
 * Scans .claude/ and .agents/ directories, extracts component metadata
 * from Markdown frontmatter, discovers dependency edges via six regex
 * strategies, validates edges, and writes src/data/graph-data.json.
 *
 * Usage:
 *   npx tsx scripts/extract-data.ts          # from tools/claude-explorer/
 *   npm run extract                          # via package.json script
 */

import fs from "node:fs";
import path from "node:path";
import { glob } from "glob";
import matter from "gray-matter";

import type {
  AgentComponent,
  CommandComponent,
  Component,
  ComponentType,
  DependencyEdge,
  GraphData,
  RuleComponent,
  SkillComponent,
  WorkflowComponent,
} from "./types.js";

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

/** Project root = two directories above tools/claude-explorer/ */
const PROJECT_ROOT = path.resolve(import.meta.dirname, "..", "..", "..");
const OUTPUT_PATH = path.resolve(
  import.meta.dirname,
  "..",
  "src",
  "data",
  "graph-data.json",
);

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function toStringArray(value: unknown): string[] {
  if (Array.isArray(value)) {
    return value
      .filter((v): v is string => typeof v === "string")
      .map((s) => s.trim())
      .filter((s) => s.length > 0);
  }
  if (typeof value === "string" && value.length > 0) {
    // Handle comma-separated strings like "Read, Bash, Write"
    return value
      .split(",")
      .map((s) => s.trim())
      .filter((s) => s.length > 0);
  }
  return [];
}

function toOptionalString(value: unknown): string | undefined {
  return typeof value === "string" ? value : undefined;
}

/**
 * Derive the component name.
 * - Agents/skills: use frontmatter `name`, fall back to slug
 * - Commands/workflows: derive from slug
 * - Rules: use first `# Heading` in the content, fall back to slug
 */
function deriveName(
  type: ComponentType,
  slug: string,
  fmName: unknown,
  content: string,
): string {
  if (typeof fmName === "string" && fmName.length > 0) return fmName;

  if (type === "rule") {
    const headingMatch = content.match(/^#\s+(.+)$/m);
    if (headingMatch?.[1]) return headingMatch[1].trim();
  }

  return slug;
}

// ---------------------------------------------------------------------------
// Phase 1: File collection + frontmatter parsing
// ---------------------------------------------------------------------------

interface GlobSpec {
  type: ComponentType;
  patterns: string[];
  source: ".claude" | ".agents";
}

const GLOB_SPECS: GlobSpec[] = [
  {
    type: "agent",
    patterns: [".claude/agents/*.md"],
    source: ".claude",
  },
  {
    type: "command",
    patterns: [".claude/commands/*.md"],
    source: ".claude",
  },
  {
    type: "skill",
    patterns: [".claude/skills/*/SKILL.md"],
    source: ".claude",
  },
  {
    type: "rule",
    patterns: [".claude/rules/*.md"],
    source: ".claude",
  },
  {
    type: "workflow",
    patterns: [".agents/workflows/*.md"],
    source: ".agents",
  },
  {
    // Mirror skills living under .agents/skills/
    type: "skill",
    patterns: [".agents/skills/*/SKILL.md"],
    source: ".agents",
  },
];

/** Collect sub-files for a skill directory (guide.md, templates/, etc.) */
function collectSubFiles(skillDir: string): string[] {
  const subFiles: string[] = [];
  if (!fs.existsSync(skillDir)) return subFiles;

  const entries = fs.readdirSync(skillDir, { withFileTypes: true });
  for (const entry of entries) {
    if (entry.name === "SKILL.md") continue;
    const relative = path.relative(PROJECT_ROOT, path.join(skillDir, entry.name));
    subFiles.push(relative);
  }
  return subFiles;
}

/**
 * Fallback frontmatter parser for files where gray-matter fails
 * (e.g. unquoted YAML values containing colons).
 * Parses simple key: value pairs line by line.
 */
function parseFrontmatterFallback(raw: string): {
  data: Record<string, unknown>;
  content: string;
} {
  const fmMatch = raw.match(/^---\r?\n([\s\S]*?)\r?\n---\r?\n([\s\S]*)$/);
  if (!fmMatch) {
    return { data: {}, content: raw };
  }

  const fmBlock = fmMatch[1]!;
  const content = fmMatch[2]!;
  const data: Record<string, unknown> = {};

  for (const line of fmBlock.split("\n")) {
    const trimmed = line.trim();
    if (!trimmed || trimmed.startsWith("#")) continue;

    // Handle "key: value" - take everything after the first ": "
    const colonIdx = trimmed.indexOf(": ");
    if (colonIdx > 0) {
      const key = trimmed.slice(0, colonIdx).trim();
      const value = trimmed.slice(colonIdx + 2).trim();
      data[key] = value;
    }
    // Handle list items "  - item" under an array key
    if (trimmed.startsWith("- ")) {
      // This is a simplistic approach; arrays are handled by the last key
      continue;
    }
  }

  return { data, content };
}

async function collectComponents(): Promise<Component[]> {
  const components: Component[] = [];

  for (const spec of GLOB_SPECS) {
    for (const pattern of spec.patterns) {
      const absolutePattern = path.join(PROJECT_ROOT, pattern);
      const files = await glob(absolutePattern);

      for (const filePath of files) {
        const relativePath = path.relative(PROJECT_ROOT, filePath);
        const raw = fs.readFileSync(filePath, "utf-8");

        let fm: Record<string, unknown>;
        let content: string;
        try {
          const parsed = matter(raw);
          fm = parsed.data;
          content = parsed.content;
        } catch {
          // Some frontmatter has unquoted YAML values with special chars.
          // Fall back to treating the whole file as content with no metadata.
          console.warn(`  Warning: YAML parse error in ${relativePath}, using fallback parser`);
          const fallback = parseFrontmatterFallback(raw);
          fm = fallback.data;
          content = fallback.content;
        }

        // Derive slug from the file path
        let slug: string;
        if (spec.type === "skill") {
          // .claude/skills/<name>/SKILL.md -> slug = <name>
          slug = path.basename(path.dirname(filePath));
        } else {
          slug = path.basename(filePath, ".md");
        }

        // Skip README.md in rules
        if (spec.type === "rule" && slug.toLowerCase() === "readme") continue;

        const id = `${spec.type}:${slug}`;
        const name = deriveName(spec.type, slug, fm.name, content);
        const description =
          typeof fm.description === "string" ? fm.description : "";

        const base = {
          id,
          type: spec.type,
          name,
          slug,
          description,
          filePath: relativePath,
          source: spec.source,
          content,
        };

        switch (spec.type) {
          case "agent": {
            const agent: AgentComponent = {
              ...base,
              type: "agent",
              model: typeof fm.model === "string" ? fm.model : "unknown",
              color: typeof fm.color === "string" ? fm.color : "gray",
              skills: toStringArray(fm.skills),
              tools: toStringArray(fm.tools),
              category: inferAgentCategory(slug),
            };
            components.push(agent);
            break;
          }

          case "command": {
            const cmd: CommandComponent = {
              ...base,
              type: "command",
              argumentHint: toOptionalString(fm["argument-hint"]),
              skillPreload: toOptionalString(fm["skill-preload"]),
            };
            components.push(cmd);
            break;
          }

          case "skill": {
            const skillDir = path.dirname(filePath);
            const skill: SkillComponent = {
              ...base,
              type: "skill",
              allowedTools: toStringArray(fm["allowed-tools"]),
              skills: toStringArray(fm.skills),
              subFiles: collectSubFiles(skillDir),
            };
            components.push(skill);
            break;
          }

          case "rule": {
            const rule: RuleComponent = {
              ...base,
              type: "rule",
            };
            components.push(rule);
            break;
          }

          case "workflow": {
            const workflow: WorkflowComponent = {
              ...base,
              type: "workflow",
            };
            components.push(workflow);
            break;
          }
        }
      }
    }
  }

  return components;
}

// ---------------------------------------------------------------------------
// Phase 2: Dependency edge extraction (6 regex strategies)
// ---------------------------------------------------------------------------

function extractEdges(components: Component[]): DependencyEdge[] {
  const edges: DependencyEdge[] = [];

  for (const component of components) {
    // Strategy 1: frontmatter skills[] array (agents & skills)
    if (component.type === "agent") {
      for (const skillName of component.skills) {
        edges.push({
          source: component.id,
          target: `skill:${skillName}`,
          type: "skills",
          broken: false,
        });
      }
    }
    if (component.type === "skill") {
      for (const skillName of component.skills) {
        edges.push({
          source: component.id,
          target: `skill:${skillName}`,
          type: "skills",
          broken: false,
        });
      }
    }

    // Strategy 2: skill-preload frontmatter (commands)
    if (component.type === "command" && component.skillPreload) {
      edges.push({
        source: component.id,
        target: `skill:${component.skillPreload}`,
        type: "skill_preload",
        broken: false,
      });
    }

    // Strategy 3: subagent_type references in body content
    const subagentRe =
      /subagent_type\s*[:=]\s*["']([a-z][-a-z0-9]*)["']/g;
    let match: RegExpExecArray | null;
    while ((match = subagentRe.exec(component.content)) !== null) {
      const targetSlug = match[1]!;
      edges.push({
        source: component.id,
        target: `agent:${targetSlug}`,
        type: "subagent_type",
        broken: false,
      });
    }

    // Strategy 4: .claude/ path references
    const claudePathRe =
      /\.claude\/(agents|commands|skills|rules)\/([a-zA-Z0-9][-a-zA-Z0-9_]*)/g;
    while ((match = claudePathRe.exec(component.content)) !== null) {
      const dir = match[1]!;
      const targetSlug = match[2]!;
      const targetType = dirToComponentType(dir);
      if (targetType) {
        edges.push({
          source: component.id,
          target: `${targetType}:${targetSlug}`,
          type: "path_ref",
          broken: false,
        });
      }
    }

    // Strategy 5: .agents/ path references
    const agentsPathRe =
      /\.agents\/(skills|workflows)\/([a-zA-Z0-9][-a-zA-Z0-9_]*)/g;
    while ((match = agentsPathRe.exec(component.content)) !== null) {
      const dir = match[1]!;
      const targetSlug = match[2]!;
      const targetType = dir === "workflows" ? "workflow" : "skill";
      edges.push({
        source: component.id,
        target: `${targetType}:${targetSlug}`,
        type: "path_ref",
        broken: false,
      });
    }

    // Strategy 6: Inline Japanese references
    //   "xxx エージェント" -> agent:xxx
    //   "xxx スキル" -> skill:xxx
    const agentInlineRe = /([a-z][-a-z0-9]+)\s+エージェント/g;
    while ((match = agentInlineRe.exec(component.content)) !== null) {
      const targetSlug = match[1]!;
      // Skip self-references
      if (`agent:${targetSlug}` === component.id) continue;
      edges.push({
        source: component.id,
        target: `agent:${targetSlug}`,
        type: "inline_ref",
        broken: false,
      });
    }

    const skillInlineRe = /([a-z][-a-z0-9]+)\s+スキル/g;
    while ((match = skillInlineRe.exec(component.content)) !== null) {
      const targetSlug = match[1]!;
      if (`skill:${targetSlug}` === component.id) continue;
      edges.push({
        source: component.id,
        target: `skill:${targetSlug}`,
        type: "inline_ref",
        broken: false,
      });
    }
  }

  return edges;
}

function dirToComponentType(
  dir: string,
): ComponentType | null {
  switch (dir) {
    case "agents":
      return "agent";
    case "commands":
      return "command";
    case "skills":
      return "skill";
    case "rules":
      return "rule";
    default:
      return null;
  }
}

// ---------------------------------------------------------------------------
// Phase 3: Edge validation (target existence check, broken flag, dedup)
// ---------------------------------------------------------------------------

function validateEdges(
  edges: DependencyEdge[],
  componentIds: Set<string>,
): DependencyEdge[] {
  // Mark broken edges where target does not exist
  for (const edge of edges) {
    if (!componentIds.has(edge.target)) {
      edge.broken = true;
    }
  }

  // Remove self-referencing edges
  const filtered = edges.filter((e) => e.source !== e.target);

  // Deduplicate by (source, target, type)
  const seen = new Set<string>();
  const unique: DependencyEdge[] = [];
  for (const edge of filtered) {
    const key = `${edge.source}|${edge.target}|${edge.type}`;
    if (!seen.has(key)) {
      seen.add(key);
      unique.push(edge);
    }
  }

  return unique;
}

// ---------------------------------------------------------------------------
// Phase 4: Agent category inference
// ---------------------------------------------------------------------------

interface CategoryRule {
  prefixes: string[];
  category: string;
}

const CATEGORY_RULES: CategoryRule[] = [
  { prefixes: ["pr-"], category: "PR Review" },
  { prefixes: ["wr-"], category: "Weekly Report" },
  { prefixes: ["weekly-report-", "weekly-comment-"], category: "Weekly Report" },
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

function inferAgentCategory(slug: string): string {
  for (const rule of CATEGORY_RULES) {
    for (const prefix of rule.prefixes) {
      if (slug.startsWith(prefix)) return rule.category;
    }
  }
  return "General";
}

// ---------------------------------------------------------------------------
// Stats computation
// ---------------------------------------------------------------------------

function computeStats(
  components: Component[],
): Record<ComponentType, number> {
  const stats: Record<ComponentType, number> = {
    agent: 0,
    command: 0,
    skill: 0,
    rule: 0,
    workflow: 0,
  };
  for (const c of components) {
    stats[c.type]++;
  }
  return stats;
}

// ---------------------------------------------------------------------------
// Main
// ---------------------------------------------------------------------------

async function main(): Promise<void> {
  console.log("Phase 1: Collecting components...");
  const components = await collectComponents();
  console.log(`  Found ${components.length} components`);

  const componentIds = new Set(components.map((c) => c.id));

  console.log("Phase 2: Extracting dependency edges...");
  const rawEdges = extractEdges(components);
  console.log(`  Found ${rawEdges.length} raw edges`);

  console.log("Phase 3: Validating edges...");
  const edges = validateEdges(rawEdges, componentIds);
  const brokenCount = edges.filter((e) => e.broken).length;
  console.log(
    `  ${edges.length} unique edges (${brokenCount} broken targets)`,
  );

  console.log("Phase 4: Computing stats...");
  const stats = computeStats(components);
  console.log(
    `  agents: ${stats.agent}, commands: ${stats.command}, ` +
      `skills: ${stats.skill}, rules: ${stats.rule}, workflows: ${stats.workflow}`,
  );

  const graphData: GraphData = {
    components,
    edges,
    stats,
    generatedAt: new Date().toISOString(),
  };

  // Ensure output directory exists
  const outputDir = path.dirname(OUTPUT_PATH);
  if (!fs.existsSync(outputDir)) {
    fs.mkdirSync(outputDir, { recursive: true });
  }

  fs.writeFileSync(OUTPUT_PATH, JSON.stringify(graphData, null, 2), "utf-8");
  console.log(`\nWrote ${OUTPUT_PATH}`);
}

main().catch((err: unknown) => {
  console.error("Fatal error:", err);
  process.exit(1);
});
