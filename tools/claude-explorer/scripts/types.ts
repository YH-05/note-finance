/**
 * Claude Explorer - Shared type definitions
 *
 * Used by both the extraction script (scripts/extract-data.ts) and
 * the React application (src/types/index.ts re-exports).
 */

// ---------------------------------------------------------------------------
// Component types
// ---------------------------------------------------------------------------

export type ComponentType =
  | "agent"
  | "command"
  | "skill"
  | "rule"
  | "workflow";

/**
 * Base interface shared by every component regardless of type.
 */
export interface BaseComponent {
  /** Unique ID, e.g. "agent:code-simplifier" */
  id: string;
  type: ComponentType;
  name: string;
  /** File-name without extension, e.g. "code-simplifier" */
  slug: string;
  description: string;
  /** Path relative to the project root, e.g. ".claude/agents/code-simplifier.md" */
  filePath: string;
  /** Which tree the file lives in */
  source: ".claude" | ".agents";
  /** Markdown body (after front-matter) */
  content: string;
}

export interface AgentComponent extends BaseComponent {
  type: "agent";
  model: string;
  color: string;
  /** Skill names listed in the frontmatter `skills` array */
  skills: string[];
  /** Tool names listed in the frontmatter `tools` array */
  tools: string[];
  /** Category inferred from name prefix */
  category: string;
}

export interface CommandComponent extends BaseComponent {
  type: "command";
  argumentHint?: string;
  /** Skill name specified in `skill-preload` frontmatter */
  skillPreload?: string;
}

export interface SkillComponent extends BaseComponent {
  type: "skill";
  allowedTools: string[];
  skills: string[];
  /** Paths of auxiliary files (guide.md, templates/, examples/, etc.) */
  subFiles: string[];
}

export interface RuleComponent extends BaseComponent {
  type: "rule";
}

export interface WorkflowComponent extends BaseComponent {
  type: "workflow";
}

/** Union of all concrete component types */
export type Component =
  | AgentComponent
  | CommandComponent
  | SkillComponent
  | RuleComponent
  | WorkflowComponent;

// ---------------------------------------------------------------------------
// Dependency edges
// ---------------------------------------------------------------------------

export type EdgeType =
  | "skills"
  | "skill_preload"
  | "subagent_type"
  | "path_ref"
  | "inline_ref";

export interface DependencyEdge {
  source: string;
  target: string;
  type: EdgeType;
  /** true when the target component does not exist in the graph */
  broken: boolean;
}

// ---------------------------------------------------------------------------
// Top-level graph data
// ---------------------------------------------------------------------------

export interface GraphData {
  components: Component[];
  edges: DependencyEdge[];
  stats: Record<ComponentType, number>;
  generatedAt: string;
}
