import { useEffect, useId, useState } from "react";
import mermaid from "mermaid";
import DOMPurify from "dompurify";
import type { Visual as VisualType } from "../api/types";
import { cn } from "../lib/cn";

let mermaidReady = false;
function ensureMermaid() {
  if (!mermaidReady) {
    mermaid.initialize({
      startOnLoad: false,
      // on a syntax error mermaid otherwise draws its own "Syntax error in
      // text" bomb graphic into a temp node in <body> and leaves it there.
      suppressErrorRendering: true,
      theme: "base",
      securityLevel: "strict", // no click handlers, no raw HTML labels
      // render labels as SVG <text>, not HTML <foreignObject>, so they survive
      // the DOMPurify SVG sanitiser (which drops foreignObject).
      htmlLabels: false,
      flowchart: { htmlLabels: false, curve: "basis" },
      fontFamily: "Inter, system-ui, sans-serif",
      themeVariables: {
        primaryColor: "#f6e8ec", // node fill: light maroon
        primaryBorderColor: "#8c1d40", // maroon border
        primaryTextColor: "#1a1a1a",
        lineColor: "#8c1d40", // maroon edges
        secondaryColor: "#fff4d6", // gold-tinted
        secondaryBorderColor: "#ffc627",
        tertiaryColor: "#ffffff",
        fontFamily: "Inter, system-ui, sans-serif",
      },
    });
    mermaidReady = true;
  }
}

// Agents often write labels with parentheses or other punctuation, e.g.
// A[Gradient: (-10,-8)] or B[Compute f'(x)]. Mermaid reads "(" inside an
// unquoted [label] as shape syntax and rejects the whole diagram; the label is
// only valid quoted: A["Gradient: (-10,-8)"]. This wraps unquoted [...] and
// {...} labels in quotes (escaping any " inside). Used only as a retry when the
// diagram as written does not parse, so valid diagrams render untouched.
function quoteLabels(code: string): string {
  const quote = (text: string) => `"${text.trim().replace(/"/g, "#quot;")}"`;
  return code
    .replace(/(\b[A-Za-z][\w-]*)\[(?!["[(])([^\[\]"\n]*?)\](?!\])/g, (_, id, text) => `${id}[${quote(text)}]`)
    .replace(/(\b[A-Za-z][\w-]*)\{(?!["{])([^{}"\n]*?)\}/g, (_, id, text) => `${id}{${quote(text)}}`);
}

// DOMPurify with the SVG profile strips <script>, event handlers, and foreign
// objects, so an agent-authored SVG cannot run code when we inject it.
function sanitizeSvg(code: string): string {
  return DOMPurify.sanitize(code, { USE_PROFILES: { svg: true, svgFilters: true } });
}

// Renders an agent-authored visual: a Mermaid diagram or an inline SVG. Both
// are sanitized before they touch the DOM (mermaid runs in strict mode and the
// output SVG is cleaned with DOMPurify). A render error falls back to just the
// caption, so a bad diagram never breaks the page.
export function Visual({ visual, className }: { visual: VisualType; className?: string }) {
  const [html, setHtml] = useState<string | null>(null);
  const [failed, setFailed] = useState(false);
  const rawId = useId();
  const id = "mmd-" + rawId.replace(/[^a-zA-Z0-9]/g, "");

  useEffect(() => {
    let alive = true;
    setFailed(false);
    setHtml(null);
    const code = visual?.code?.trim();
    if (!code) {
      setFailed(true);
      return;
    }
    if (visual.format === "mermaid") {
      ensureMermaid();
      // mermaid.render builds the diagram in temporary nodes in <body> (#id and
      // #d<id>). they are removed on success but can linger after a failure,
      // so clear them out whenever a render does not succeed.
      const cleanup = () => {
        document.getElementById(id)?.remove();
        document.getElementById("d" + id)?.remove();
      };
      (async () => {
        // check the syntax first, so an invalid diagram is never rendered. if
        // it fails, retry with its labels quoted (the most common agent mistake).
        let source = code;
        if (!(await mermaid.parse(source, { suppressErrors: true }))) {
          source = quoteLabels(code);
          if (!(await mermaid.parse(source, { suppressErrors: true }))) {
            throw new Error("invalid mermaid syntax");
          }
        }
        const { svg } = await mermaid.render(id, source);
        if (alive) setHtml(sanitizeSvg(svg));
      })().catch(() => {
        cleanup();
        if (alive) setFailed(true);
      });
    } else {
      const clean = sanitizeSvg(code);
      if (clean.includes("<svg")) setHtml(clean);
      else setFailed(true);
    }
    return () => {
      alive = false;
    };
  }, [visual?.format, visual?.code, id]);

  if (failed) {
    return visual?.caption ? (
      <div className={cn("text-xs text-ink/40", className)}>{visual.caption}</div>
    ) : null;
  }

  const box =
    "flex min-h-[48px] items-center justify-center overflow-x-auto rounded-xl border border-line bg-white p-3 [&_svg]:h-auto [&_svg]:max-w-full";

  return (
    <figure className={cn("my-2", className)}>
      {html ? (
        <div className={box} dangerouslySetInnerHTML={{ __html: html }} />
      ) : (
        <div className={box}>
          <span className="text-xs text-ink/30">rendering diagram…</span>
        </div>
      )}
      {visual.caption && (
        <figcaption className="mt-1 text-center text-xs text-ink/50">{visual.caption}</figcaption>
      )}
    </figure>
  );
}
