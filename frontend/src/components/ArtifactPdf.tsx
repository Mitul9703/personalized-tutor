import type { ReactNode } from "react";
import type { ArtifactDetail, Citation, Deck, Doc, FlashcardSet, MindMap, MindNode, Quiz } from "../api/types";
import { Markdown } from "./Markdown";
import { Visual } from "./Visual";
import { CitationBadge } from "./CitationBadge";
import { cn } from "../lib/cn";

// An off-screen, print-friendly layout of a whole artifact. It reuses the same
// Markdown, Visual, and CitationBadge components and the same Tailwind styles
// as the on-screen views, so a capture of it looks like the app. Each top-level
// item is a `.pdf-block` the exporter keeps whole on a page.

const WIDTH = 760;

const LABELS: Record<string, string> = {
  slides: "Slides", doc: "Doc", quiz: "Quiz", flashcards: "Flashcards", mindmap: "Mind map",
};

function Prov({ p }: { p: "source" | "supplementary" }) {
  return p === "supplementary" ? (
    <span className="rounded-full bg-goldsoft px-2 py-0.5 text-[11px] font-medium text-goldink">beyond your materials</span>
  ) : (
    <span className="text-[11px] text-goldink">from your materials</span>
  );
}

function Cites({ citations }: { citations: Citation[] }) {
  if (!citations?.length) return null;
  return (
    <div className="mt-2 flex flex-wrap gap-1.5">
      {citations.map((c, i) => <CitationBadge key={i} citation={c} />)}
    </div>
  );
}

export function ArtifactPdf({ detail, deck }: { detail: ArtifactDetail; deck: any }) {
  const isSlides = detail.type === "slides";
  const title = deck?.title ?? detail.title;
  const heading = (
    <>
      <h1 className="text-2xl font-bold leading-tight">{title}</h1>
      <div className="mt-1 text-xs text-ink/40">Personalized Tutor · {LABELS[detail.type] ?? detail.type}</div>
    </>
  );
  return (
    <div className="bg-white text-ink" style={{ width: WIDTH, fontFamily: "Inter, system-ui, sans-serif" }}>
      {/* in slide mode every block is its own page, so the title rides on slide 1 instead */}
      {!isSlides && <div className="pdf-block px-6 pt-6">{heading}</div>}
      <div className="px-6 pb-6 pt-3">
        {detail.type === "slides" && <Slides deck={deck as Deck} heading={heading} />}
        {detail.type === "doc" && <DocBody doc={deck as Doc} />}
        {detail.type === "flashcards" && <Cards set={deck as FlashcardSet} />}
        {detail.type === "quiz" && <QuizBody quiz={deck as Quiz} />}
        {detail.type === "mindmap" && <MindBody map={deck as MindMap} />}
      </div>
    </div>
  );
}

// Each slide is a 16:9 face (960x540) that the exporter drops onto its own
// landscape page, like a slide deck printed to PDF. Speaker notes ride along as
// a small footer under the slide so nothing is lost.
function Slides({ deck, heading }: { deck: Deck; heading: ReactNode }) {
  const total = deck.slides?.length ?? 0;
  return (
    <>
      {(deck.slides ?? []).map((s, i) => (
        <div key={s.id} className="pdf-block mb-6" style={{ width: 960 }}>
          <div className="flex flex-col rounded-2xl border border-line bg-panel p-8" style={{ minHeight: 540 }}>
            {i === 0 && <div className="mb-3 border-b border-line pb-2">{heading}</div>}
            <div className="mb-1 flex items-center justify-between text-xs text-ink/40">
              <span>Slide {i + 1} of {total}</span>
              <Prov p={s.provenance} />
            </div>
            <h2 className="mb-5 mt-1 text-[28px] font-semibold leading-tight">{s.heading}</h2>
            <ul className="flex-1 space-y-3">
              {s.bullets.map((b, j) => (
                <li key={j} className="flex gap-3 text-[17px] leading-relaxed text-ink/80">
                  <span className="mt-2.5 h-1.5 w-1.5 shrink-0 rounded-full bg-gold" />
                  <Markdown inline className="min-w-0 flex-1">{b}</Markdown>
                </li>
              ))}
            </ul>
            {s.visual && <Visual visual={s.visual} className="mt-3 [&_svg]:max-h-64" />}
            {s.citations.length > 0 && (
              <div className="mt-4 border-t border-line pt-2"><Cites citations={s.citations} /></div>
            )}
          </div>
          {s.notes?.trim() && (
            <div className="mt-2 px-1 text-[12px] leading-relaxed text-ink/60">
              <span className="font-semibold uppercase tracking-wide text-ink/40">Notes · </span>
              <Markdown inline>{s.notes}</Markdown>
            </div>
          )}
        </div>
      ))}
    </>
  );
}

function DocBody({ doc }: { doc: Doc }) {
  return (
    <>
      {(doc.sections ?? []).map((s) => (
        <section key={s.id} className="pdf-block mb-6">
          <div className="mb-1 flex items-center justify-between gap-2">
            <h2 className="text-lg font-semibold text-ink/90">{s.heading}</h2>
            <Prov p={s.provenance} />
          </div>
          <Markdown className="text-[15px] leading-relaxed text-ink/80">{s.body}</Markdown>
          {s.visual && <Visual visual={s.visual} className="mt-3 [&_svg]:max-h-[380px]" />}
          <Cites citations={s.citations} />
        </section>
      ))}
    </>
  );
}

function Cards({ set }: { set: FlashcardSet }) {
  return (
    <>
      {(set.cards ?? []).map((c, i) => (
        <div key={c.id} className="pdf-block mb-3 rounded-xl border border-line bg-panel p-4">
          <div className="flex items-center justify-between text-xs text-ink/40">
            <span>Card {i + 1}</span>
            <Prov p={c.provenance} />
          </div>
          <div className="mt-2 text-[15px] font-semibold text-ink/90"><Markdown inline>{c.front}</Markdown></div>
          <div className="mt-2 text-[15px] text-ink/80">
            <span className="mr-1 text-[10px] font-semibold uppercase tracking-wide text-ink/40">Answer</span>
            <Markdown inline>{c.back}</Markdown>
          </div>
          {c.visual && <Visual visual={c.visual} className="mt-2 [&_svg]:max-h-56" />}
          <Cites citations={c.citations} />
        </div>
      ))}
    </>
  );
}

function QuizBody({ quiz }: { quiz: Quiz }) {
  const qs = quiz.questions ?? [];
  return (
    <>
      {qs.map((q, i) => (
        <div key={q.id} className="pdf-block mb-3 rounded-xl border border-line bg-panel p-4">
          <div className="flex items-center justify-between text-xs text-ink/40">
            <span>Question {i + 1}</span>
            <Prov p={q.provenance} />
          </div>
          <div className="mt-1 text-[15px] font-medium leading-relaxed"><Markdown inline>{q.stem}</Markdown></div>
          {q.visual && <Visual visual={q.visual} className="mt-2 [&_svg]:max-h-56" />}
          {q.kind === "mcq" ? (
            <ul className="mt-3 space-y-1.5">
              {q.options.map((o, j) => (
                <li key={j} className="flex items-start gap-2 rounded-lg border border-line px-3 py-1.5 text-sm">
                  <span className="mt-0.5 inline-block h-3.5 w-3.5 shrink-0 rounded-full border border-ink/30" />
                  <Markdown inline className="min-w-0 flex-1">{o}</Markdown>
                </li>
              ))}
            </ul>
          ) : (
            <div className="mt-3 rounded-lg border border-dashed border-line px-3 py-6 text-xs text-ink/30">
              Answer: ______________________________________
            </div>
          )}
        </div>
      ))}
      <div className="pdf-block mt-4 rounded-xl border border-brand/30 bg-brandsoft p-4">
        <h2 className="mb-2 text-sm font-semibold text-brand">Answer key</h2>
        <ol className="space-y-2 text-sm">
          {qs.map((q, i) => (
            <li key={q.id}>
              <span className="font-semibold">{i + 1}.</span>{" "}
              <Markdown inline>{q.answer}</Markdown>
              {q.explanation && <div className="mt-0.5 text-ink/70"><Markdown inline>{q.explanation}</Markdown></div>}
              <Cites citations={q.citations} />
            </li>
          ))}
        </ol>
      </div>
    </>
  );
}

// ---- mind map: the same tree the app draws, plus a list of the nodes ----

const N_W = 170, N_H = 54, COL = 220, ROW = 74, PAD = 24;

function layout(nodes: MindNode[]) {
  const pos: Record<string, { x: number; y: number }> = {};
  if (!nodes.length) return { pos, width: 0, height: 0, rootId: "" };
  const childrenOf = (id: string | null) => nodes.filter((n) => (n.parent_id ?? null) === id);
  const root = nodes.find((n) => !n.parent_id) ?? nodes[0];
  let nextRow = 0;
  const seen = new Set<string>();
  const place = (id: string, depth: number) => {
    if (seen.has(id)) return;
    seen.add(id);
    const kids = childrenOf(id);
    if (!kids.length) { pos[id] = { x: depth * COL, y: nextRow * ROW }; nextRow += 1; return; }
    kids.forEach((k) => place(k.id, depth + 1));
    const ys = kids.map((k) => pos[k.id]?.y ?? 0);
    pos[id] = { x: depth * COL, y: (Math.min(...ys) + Math.max(...ys)) / 2 };
  };
  place(root.id, 0);
  nodes.forEach((n) => { if (!pos[n.id]) { pos[n.id] = { x: 0, y: nextRow * ROW }; nextRow += 1; } });
  const maxX = Math.max(...Object.values(pos).map((p) => p.x));
  const maxY = Math.max(...Object.values(pos).map((p) => p.y));
  return { pos, width: maxX + N_W + PAD * 2, height: maxY + N_H + PAD * 2, rootId: root.id };
}

function MindBody({ map }: { map: MindMap }) {
  const nodes = map.nodes ?? [];
  const { pos, width, height, rootId } = layout(nodes);
  const edges = nodes
    .filter((n) => n.parent_id && pos[n.parent_id] && pos[n.id])
    .map((n) => {
      const p = pos[n.parent_id as string], c = pos[n.id];
      const x1 = p.x + PAD + N_W, y1 = p.y + PAD + N_H / 2, x2 = c.x + PAD, y2 = c.y + PAD + N_H / 2;
      const dx = Math.max(24, (x2 - x1) / 2);
      return { id: n.id, d: `M ${x1} ${y1} C ${x1 + dx} ${y1}, ${x2 - dx} ${y2}, ${x2} ${y2}` };
    });
  return (
    <>
      {nodes.length > 0 && (
        <div className="pdf-block mb-4 overflow-hidden rounded-xl border border-line bg-white p-2">
          <div className="relative" style={{ width, height }}>
            <svg className="pointer-events-none absolute inset-0" width={width} height={height}>
              {edges.map((e) => (
                <path key={e.id} d={e.d} fill="none" stroke="currentColor" strokeWidth={1.5} className="text-line" />
              ))}
            </svg>
            {nodes.map((n) => {
              const p = pos[n.id];
              if (!p) return null;
              const isRoot = n.id === rootId;
              const supp = n.provenance === "supplementary";
              return (
                <div
                  key={n.id}
                  style={{ left: p.x + PAD, top: p.y + PAD, width: N_W, minHeight: N_H }}
                  className={cn(
                    "absolute flex flex-col justify-center rounded-xl border px-3 py-2",
                    isRoot ? "border-brand bg-brand text-white" : supp ? "border-gold bg-panel" : "border-line bg-panel",
                  )}
                >
                  <Markdown inline className={cn("text-xs font-semibold", isRoot ? "text-white" : "text-ink/80")}>
                    {n.label}
                  </Markdown>
                </div>
              );
            })}
          </div>
        </div>
      )}
      <div className="pdf-block">
        <h2 className="mb-2 text-sm font-semibold text-ink/70">Concepts</h2>
        <ul className="space-y-2">
          {nodes.map((n) => (
            <li key={n.id} className="rounded-lg border border-line bg-panel p-3">
              <div className="flex items-center justify-between gap-2">
                <div className="text-sm font-semibold text-ink/90"><Markdown inline>{n.label}</Markdown></div>
                <Prov p={n.provenance} />
              </div>
              {n.detail && <Markdown className="mt-1 text-[13px] leading-relaxed text-ink/70">{n.detail}</Markdown>}
              {n.visual && <Visual visual={n.visual} className="mt-2 [&_svg]:max-h-56" />}
              <Cites citations={n.citations} />
            </li>
          ))}
        </ul>
      </div>
    </>
  );
}
