/**
 * Slide-in detail panel for component inspection.
 *
 * Fixed to the right edge of the viewport, 400px wide, with a CSS
 * translate transition for the slide-in / slide-out effect.
 *
 * Displays: type badge, name, description, type-specific metadata
 * (model/color/tools for agents, etc.), dependency list, Markdown
 * content preview, and the file path.
 */

import type { Component, DependencyEdge } from "@/types";
import { getColorScheme } from "@/lib/colors";
import { DependencyList } from "./DependencyList";
import { MarkdownPreview } from "./MarkdownPreview";

interface DetailPanelProps {
  /** The component to display, or null when closed. */
  component: Component | null;
  /** All edges for dependency resolution. */
  edges: DependencyEdge[];
  /** Component lookup map. */
  componentMap: Map<string, Component>;
  /** Navigate to another component. */
  onSelect: (id: string) => void;
  /** Close the panel. */
  onClose: () => void;
}

/**
 * Renders type-specific metadata badges (model, color, tools, etc.).
 */
function TypeMetadata({ component }: { component: Component }) {
  switch (component.type) {
    case "agent":
      return (
        <div className="space-y-2">
          {/* Model & color */}
          <div className="flex flex-wrap gap-1.5">
            {component.model && (
              <span className="inline-flex items-center px-2 py-0.5 text-[10px] font-medium rounded-full bg-gray-100 text-gray-600">
                model: {component.model}
              </span>
            )}
            {component.color && (
              <span className="inline-flex items-center px-2 py-0.5 text-[10px] font-medium rounded-full bg-gray-100 text-gray-600">
                color: {component.color}
              </span>
            )}
            {component.category && (
              <span className="inline-flex items-center px-2 py-0.5 text-[10px] font-medium rounded-full bg-blue-50 text-blue-600">
                {component.category}
              </span>
            )}
          </div>

          {/* Skills */}
          {component.skills.length > 0 && (
            <div>
              <span className="text-[10px] text-gray-400 uppercase tracking-wider">
                Skills
              </span>
              <div className="mt-0.5 flex flex-wrap gap-1">
                {component.skills.map((s) => (
                  <span
                    key={s}
                    className="px-1.5 py-0.5 text-[10px] rounded bg-purple-50 text-purple-600"
                  >
                    {s}
                  </span>
                ))}
              </div>
            </div>
          )}

          {/* Tools */}
          {component.tools.length > 0 && (
            <div>
              <span className="text-[10px] text-gray-400 uppercase tracking-wider">
                Tools
              </span>
              <div className="mt-0.5 flex flex-wrap gap-1">
                {component.tools.map((t) => (
                  <span
                    key={t}
                    className="px-1.5 py-0.5 text-[10px] rounded bg-gray-100 text-gray-600"
                  >
                    {t}
                  </span>
                ))}
              </div>
            </div>
          )}
        </div>
      );

    case "command":
      return (
        <div className="space-y-2">
          {component.argumentHint && (
            <div>
              <span className="text-[10px] text-gray-400 uppercase tracking-wider">
                Arguments
              </span>
              <p className="mt-0.5 text-xs text-gray-600 font-mono bg-gray-50 px-2 py-1 rounded">
                {component.argumentHint}
              </p>
            </div>
          )}
          {component.skillPreload && (
            <div>
              <span className="text-[10px] text-gray-400 uppercase tracking-wider">
                Skill Preload
              </span>
              <span className="mt-0.5 inline-flex items-center gap-1 px-2 py-0.5 text-[10px] font-medium rounded-full bg-purple-50 text-purple-600">
                {component.skillPreload}
              </span>
            </div>
          )}
        </div>
      );

    case "skill":
      return (
        <div className="space-y-2">
          {component.allowedTools.length > 0 && (
            <div>
              <span className="text-[10px] text-gray-400 uppercase tracking-wider">
                Allowed Tools
              </span>
              <div className="mt-0.5 flex flex-wrap gap-1">
                {component.allowedTools.map((tool) => (
                  <span
                    key={tool}
                    className="px-1.5 py-0.5 text-[10px] rounded bg-gray-100 text-gray-600"
                  >
                    {tool}
                  </span>
                ))}
              </div>
            </div>
          )}
          {component.subFiles.length > 0 && (
            <div>
              <span className="text-[10px] text-gray-400 uppercase tracking-wider">
                Auxiliary Files ({component.subFiles.length})
              </span>
              <div className="mt-0.5 space-y-0.5">
                {component.subFiles.map((f) => (
                  <p key={f} className="text-[10px] text-gray-500 font-mono truncate">
                    {f}
                  </p>
                ))}
              </div>
            </div>
          )}
        </div>
      );

    case "rule":
    case "workflow":
      return null;
  }
}

export function DetailPanel({
  component,
  edges,
  componentMap,
  onSelect,
  onClose,
}: DetailPanelProps) {
  const isOpen = component !== null;

  return (
    <>
      {/* Backdrop overlay */}
      {isOpen && (
        <div
          className="fixed inset-0 bg-black/20 z-40 transition-opacity"
          onClick={onClose}
        />
      )}

      {/* Panel */}
      <div
        className={`fixed top-0 right-0 h-full w-[400px] bg-white shadow-xl z-50 transform transition-transform duration-300 ease-in-out ${
          isOpen ? "translate-x-0" : "translate-x-full"
        }`}
      >
        {component && (
          <div className="h-full flex flex-col">
            {/* Header */}
            <div className="flex items-center justify-between px-4 py-3 border-b border-gray-200">
              <div className="flex items-center gap-2 min-w-0">
                {/* Type badge */}
                <span
                  className={`flex-shrink-0 text-[10px] font-medium px-2 py-0.5 rounded ${getColorScheme(component.type).bg} ${getColorScheme(component.type).text}`}
                >
                  {getColorScheme(component.type).label}
                </span>
                <h2 className="text-sm font-semibold text-gray-900 truncate">
                  {component.name}
                </h2>
              </div>

              {/* Close button */}
              <button
                type="button"
                onClick={onClose}
                className="flex-shrink-0 p-1 rounded hover:bg-gray-100 transition-colors"
                aria-label="Close panel"
              >
                <svg
                  className="w-5 h-5 text-gray-500"
                  fill="none"
                  stroke="currentColor"
                  viewBox="0 0 24 24"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={2}
                    d="M6 18L18 6M6 6l12 12"
                  />
                </svg>
              </button>
            </div>

            {/* Scrollable content */}
            <div className="flex-1 overflow-y-auto">
              <div className="px-4 py-4 space-y-5">
                {/* Description */}
                <div>
                  <h3 className="text-[10px] font-medium text-gray-400 uppercase tracking-wider mb-1">
                    Description
                  </h3>
                  <p className="text-xs text-gray-600 leading-relaxed">
                    {component.description}
                  </p>
                </div>

                {/* Type-specific metadata */}
                <TypeMetadata component={component} />

                {/* Dependencies */}
                <div>
                  <h3 className="text-[10px] font-medium text-gray-400 uppercase tracking-wider mb-1">
                    Dependencies
                  </h3>
                  <DependencyList
                    componentId={component.id}
                    edges={edges}
                    componentMap={componentMap}
                    onSelect={onSelect}
                  />
                </div>

                {/* Markdown content */}
                <div>
                  <h3 className="text-[10px] font-medium text-gray-400 uppercase tracking-wider mb-2">
                    Content
                  </h3>
                  <MarkdownPreview content={component.content} />
                </div>

                {/* File path */}
                <div className="border-t border-gray-100 pt-3">
                  <h3 className="text-[10px] font-medium text-gray-400 uppercase tracking-wider mb-1">
                    File Path
                  </h3>
                  <p className="text-[10px] text-gray-500 font-mono break-all">
                    {component.filePath}
                  </p>
                </div>
              </div>
            </div>
          </div>
        )}
      </div>
    </>
  );
}
