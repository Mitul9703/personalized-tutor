import ReactMarkdown, { type Components } from "react-markdown";
import remarkGfm from "remark-gfm";
import remarkMath from "remark-math";
import rehypeKatex from "rehype-katex";
import "katex/dist/katex.min.css";
import { cn } from "../lib/cn";

// remark-math only understands $...$ and $$...$$, but models often write math
// with LaTeX's own delimiters, \( ... \) and \[ ... \]. convert those so the
// formula renders instead of showing up as raw text.
export function normalizeMath(text: string): string {
  return text
    .replace(/\\\[([\s\S]+?)\\\]/g, (_, body) => `$$${body}$$`)
    .replace(/\\\(([\s\S]+?)\\\)/g, (_, body) => `$${body}$`);
}

// Renders agent-written text as markdown with LaTeX math, so emphasis, lists,
// code, tables, and formulas ($...$ / $$...$$ / \(...\) / \[...\]) look right.
// react-markdown does not render raw HTML, so this is safe from injected
// markup. `inline` is for a one-line context (a bullet, a card face, a quiz
// stem) where block margins would break the layout; otherwise it renders as a
// block of prose. `components` lets a caller swap how an element renders (the
// chat uses it to turn citation links into source badges).
export function Markdown({ children, inline = false, className, components }: {
  children?: string | null;
  inline?: boolean;
  className?: string;
  components?: Components;
}) {
  return (
    <div className={cn(inline ? "md-inline" : "md", className)}>
      <ReactMarkdown
        remarkPlugins={[remarkGfm, remarkMath]}
        rehypePlugins={[[rehypeKatex, { throwOnError: false, errorColor: "#cc0000" }]]}
        components={components}
      >
        {normalizeMath(children ?? "")}
      </ReactMarkdown>
    </div>
  );
}
