/**
 * Smoke tests -- verify key components render without crashing.
 */
import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { CardHeader } from "../cards/CardHeader";
import { PillList } from "../cards/PillList";
import { LoadingSpinner } from "../LoadingSpinner";
import { ErrorBoundary } from "../ErrorBoundary";

describe("CardHeader", () => {
  it("renders name and type badge", () => {
    render(
      <CardHeader
        name="test-agent"
        type="agent"
        description="A test agent"
      />,
    );
    expect(screen.getByText("test-agent")).toBeInTheDocument();
    expect(screen.getByText("Agent")).toBeInTheDocument();
    expect(screen.getByText("A test agent")).toBeInTheDocument();
  });
});

describe("PillList", () => {
  it("renders items as pills", () => {
    render(
      <PillList
        label="Skills"
        items={["skill1", "skill2"]}
        colorClass="bg-purple-50 text-purple-600"
      />,
    );
    expect(screen.getByText("Skills")).toBeInTheDocument();
    expect(screen.getByText("skill1")).toBeInTheDocument();
    expect(screen.getByText("skill2")).toBeInTheDocument();
  });

  it("returns null for empty items", () => {
    const { container } = render(
      <PillList label="Skills" items={[]} colorClass="bg-purple-50" />,
    );
    expect(container.innerHTML).toBe("");
  });
});

describe("LoadingSpinner", () => {
  it("renders with message", () => {
    render(<LoadingSpinner message="Loading..." />);
    expect(screen.getByText("Loading...")).toBeInTheDocument();
  });
});

describe("ErrorBoundary", () => {
  it("renders children when no error", () => {
    render(
      <ErrorBoundary>
        <div>Hello</div>
      </ErrorBoundary>,
    );
    expect(screen.getByText("Hello")).toBeInTheDocument();
  });
});
