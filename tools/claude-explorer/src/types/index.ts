/**
 * Re-export all type definitions from the shared scripts/types.ts.
 *
 * The canonical definitions live in scripts/types.ts so that both the
 * build-time extraction script and the runtime React app share the
 * exact same interfaces.
 */
export type {
  ComponentType,
  BaseComponent,
  AgentComponent,
  CommandComponent,
  SkillComponent,
  RuleComponent,
  WorkflowComponent,
  Component,
  EdgeType,
  DependencyEdge,
  GraphData,
} from "../../scripts/types.js";
