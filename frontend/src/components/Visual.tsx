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
      theme: "neutral",
      securityLevel: "strict", // no click handlers, no raw HTML labels
      // render labels as SVG <text>, not HTML <foreignObject>, so they survive
      // the DOMPurify SVG sanitiser (which drops foreignObject).
      htmlLabels: false,
      flowchart: { htmlLabels: false, curve: "basis" },
      fontFamily: "Inter, system-ui, sans-serif",
    });
    mermaidReady = true;
  }
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
      mermaid
        .render(id, code)
        .then(({ svg }) => alive && setHtml(sanitizeSvg(svg)))
        .catch(() => alive && setFailed(true));
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
