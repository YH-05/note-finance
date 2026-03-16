/**
 * Dispatcher component — renders the correct card based on component type.
 *
 * Wraps each card in a clickable container that triggers the detail panel.
 */

import type { Component } from "@/types";
import { AgentCard } from "./AgentCard";
import { CommandCard } from "./CommandCard";
import { SkillCard } from "./SkillCard";
import { RuleCard } from "./RuleCard";
import { WorkflowCard } from "./WorkflowCard";

interface ComponentCardProps {
  component: Component;
  /** Callback when the card is clicked. */
  onSelect?: (id: string) => void;
}

function renderCard(component: Component) {
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

export function ComponentCard({ component, onSelect }: ComponentCardProps) {
  return (
    <div
      role="button"
      tabIndex={0}
      className="cursor-pointer"
      onClick={() => onSelect?.(component.id)}
      onKeyDown={(e) => {
        if (e.key === "Enter" || e.key === " ") {
          e.preventDefault();
          onSelect?.(component.id);
        }
      }}
    >
      {renderCard(component)}
    </div>
  );
}
