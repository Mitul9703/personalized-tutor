import { useState } from "react";
import { Loader2, Send, Sparkles } from "lucide-react";
import type { Doc } from "../api/types";
import { CitationBadge } from "./CitationBadge";
import { Markdown } from "./Markdown";
import { Visual } from "./Visual";
import { useStore } from "../store/useStore";

const QUICK_EDITS = ["Make it simpler", "Go deeper", "Add an example"];

// Renders a doc: a readable article of sections, each a heading and a block of
// prose. Provenance and citations work the same way as on slides, so a reader
// can see which parts come from their own material and open the source text.
// The edit box sends a free text instruction to the doc agent, which saves a
// new version.
export function DocView({ doc, readOnly }: { doc: Doc; readOnly: boolean }) {
  const sections = doc.sections ?? [];
  const [instruction, setInstruction] = useState("");
  const editDoc = useStore((s) => s.editDoc);
  const busy = useStore((s) => s.busy);

  const submit = (text: string) => {
    if (!text.trim() || busy) return;
    editDoc(text);
    setInstruction("");
  };

  return (
    <div className="flex h-full min-h-0 flex-col">
      <div className="flex-1 overflow-y-auto px-6 py-6">
        <article className="mx-auto w-full max-w-2xl space-y-8">
          {sections.length === 0 && <p className="text-sm text-ink/50">No sections yet.</p>}
          {sections.map((s) => {
            const supplementary = s.provenance === "supplementary";
            return (
              <section key={s.id}>
                <div className="mb-2 flex items-center justify-between gap-2">
                  <h2 className="text-lg font-semibold text-ink/90">{s.heading}</h2>
                  {supplementary ? (
                    <span className="inline-flex shrink-0 items-center gap-1 rounded-full bg-amber-50 px-2 py-0.5 text-[11px] font-medium text-amber-700">
                      <Sparkles className="h-3 w-3" />
                      beyond your materials
                    </span>
                  ) : (
                    <span className="shrink-0 text-[11px] text-emerald-600">from your materials</span>
                  )}
                </div>
                <Markdown className="text-[15px] leading-relaxed text-ink/80">{s.body}</Markdown>
                {s.visual && <Visual visual={s.visual} className="mt-3 [&_svg]:max-h-[420px]" />}
                {(s.citations.length > 0 || supplementary) && (
                  <div className="mt-3 flex flex-wrap items-center gap-1.5">
                    {s.citations.length > 0 ? (
                      s.citations.map((c, i) => <CitationBadge key={i} citation={c} />)
                    ) : (
                      <span className="text-[11px] text-ink/40">general knowledge, not from your files</span>
                    )}
                  </div>
                )}
              </section>
            );
          })}
        </article>
      </div>

      {!readOnly && (
        <div className="border-t border-line px-6 py-4">
          <div className="mx-auto w-full max-w-2xl">
            <div className="mb-2 flex flex-wrap gap-1.5">
              {QUICK_EDITS.map((q) => (
                <button
                  key={q}
                  onClick={() => submit(q)}
                  disabled={busy}
                  className="rounded-full border border-line px-2.5 py-1 text-[11px] text-ink/60 hover:border-brand/40 hover:text-brand disabled:opacity-40"
                >
                  {q}
                </button>
              ))}
            </div>
            <form
              onSubmit={(e) => {
                e.preventDefault();
                submit(instruction);
              }}
              className="flex items-center gap-2"
            >
              <input
                value={instruction}
                onChange={(e) => setInstruction(e.target.value)}
                placeholder='Edit this doc, e.g. "expand the section on momentum"'
                disabled={busy}
                className="flex-1 rounded-lg border border-line bg-panel px-3 py-2 text-sm outline-none focus:border-brand/50"
              />
              <button
                type="submit"
                disabled={busy || !instruction.trim()}
                className="rounded-lg bg-brand p-2 text-white disabled:opacity-40"
                title="Edit doc"
              >
                {busy ? <Loader2 className="h-4 w-4 animate-spin" /> : <Send className="h-4 w-4" />}
              </button>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
