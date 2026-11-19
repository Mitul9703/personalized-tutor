import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import remarkMath from "remark-math";
import rehypeKatex from "rehype-katex";
import "katex/dist/katex.min.css";
import { cn } from "../lib/cn";

// Renders agent-written text as markdown with LaTeX math, so emphasis, lists,
// code, tables, and formulas ($...$ / $$...$$) look right. react-markdown does
// not render raw HTML, so this is safe from injected markup. `inline` is for a
// one-line context (a bullet, a card face, a quiz stem) where block margins
// would break the layout; otherwise it renders as a block of prose.
export function Markdown({ children, inline = false, className }: {
  children?: string | null;
  inline?: boolean;
  className?: string;
}) {
  return (
    <div className={cn(inline ? "md-inline" : "md", className)}>
      <ReactMarkdown
        remarkPlugins={[remarkGfm, remarkMath]}
        rehypePlugins={[[rehypeKatex, { throwOnError: false, errorColor: "#cc0000" }]]}
      >
        {children ?? ""}
      </ReactMarkdown>
    </div>
  );
}
