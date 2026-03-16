/**
 * Dispatcher component — renders the correct card based on component type.
 */

import type { Component } from "@/types";
import { AgentCard } from "./AgentCard";
import { CommandCard } from "./CommandCard";
import { SkillCard } from "./SkillCard";
import { RuleCard } from "./RuleCard";
import { WorkflowCard } from "./WorkflowCard";

interface ComponentCardProps {
  component: Component;
}

export function ComponentCard({ component }: ComponentCardProps) {
  switch (component.type) {
    case "agent":
      return <AgentCard component={component} />;
    case "command":
      return <CommandCard component={component} />;
    case "skill":
      return <SkillCard component={component} />;
    case "rule":
      return <RuleCard component={component} />;
    case "workflow":
      return <WorkflowCard component={component} />;
  }
}
