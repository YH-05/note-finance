/**
 * Markdown preview component using react-markdown with remark-gfm.
 *
 * Renders Markdown content with GitHub Flavored Markdown support
 * (tables, strikethrough, task lists, autolinks) using Tailwind
 * typography prose styling.
 */

import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import rehypeSanitize from "rehype-sanitize";

interface MarkdownPreviewProps {
  /** Raw Markdown string to render. */
  content: string;
}

export function MarkdownPreview({ content }: MarkdownPreviewProps) {
  if (!content.trim()) {
    return (
      <p className="text-xs text-gray-400 italic">No content available.</p>
    );
  }

  return (
    <div className="prose prose-sm prose-gray max-w-none prose-headings:text-gray-800 prose-headings:font-semibold prose-p:text-gray-600 prose-a:text-blue-600 prose-code:text-pink-600 prose-code:bg-gray-100 prose-code:px-1 prose-code:py-0.5 prose-code:rounded prose-code:text-xs prose-pre:bg-gray-50 prose-pre:text-xs prose-table:text-xs prose-th:text-left prose-th:font-semibold prose-th:text-gray-700 prose-td:text-gray-600">
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        rehypePlugins={[rehypeSanitize]}
        components={{
          a: ({ href, children }) => (
            <a href={href} target="_blank" rel="noopener noreferrer">
              {children}
            </a>
          ),
        }}
      >
        {content}
      </ReactMarkdown>
    </div>
  );
}
