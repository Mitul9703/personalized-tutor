import { useEffect, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { ChevronLeft, ChevronRight, Loader2, RefreshCw, Send, Sparkles } from "lucide-react";
import type { FlashcardSet } from "../api/types";
import { CitationBadge } from "./CitationBadge";
import { useStore } from "../store/useStore";
import { cn } from "../lib/cn";

const QUICK_EDITS = ["Make the cards simpler", "Go deeper", "Add more cards"];

// Renders a flashcard set: a list of cards on the left, one card in the
// middle that flips between front and back. Citations and the source or
// supplementary label work the same way as on slides. The edit box sends a
// free text instruction to the flashcard agent, which saves a new version.
export function FlashcardDeck({ set, readOnly }: { set: FlashcardSet; readOnly: boolean }) {
  const cards = set.cards ?? [];
  const [current, setCurrent] = useState(0);
  const [flipped, setFlipped] = useState(false);
  const [instruction, setInstruction] = useState("");
  const editFlashcards = useStore((s) => s.editFlashcards);
  const busy = useStore((s) => s.busy);

  useEffect(() => {
    setCurrent((c) => Math.min(c, Math.max(0, cards.length - 1)));
    setFlipped(false);
  }, [set]);

  const go = (i: number) => {
    setCurrent(i);
    setFlipped(false);
  };

  const submit = (text: string) => {
    if (!text.trim() || busy) return;
    editFlashcards(text);
    setInstruction("");
  };

  const card = cards[current];
  if (!card) {
    return <div className="p-6 text-sm text-ink/50">No cards yet.</div>;
  }
  const supplementary = card.provenance === "supplementary";

  return (
    <div className="flex h-full min-h-0">
      <div className="w-40 shrink-0 space-y-2 overflow-y-auto border-r border-line p-3">
        {cards.map((c, i) => (
          <button
            key={c.id}
            onClick={() => go(i)}
            className={cn(
              "w-full rounded-lg border p-2 text-left transition",
              i === current ? "border-brand bg-brandsoft" : "border-line bg-panel hover:border-brand/40"
            )}
          >
            <div className="mb-1 flex items-center justify-between text-[9px] text-ink/40">
              <span>{i + 1}</span>
              {c.provenance === "supplementary" && <span className="text-amber-500">◆</span>}
            </div>
            <div className="line-clamp-2 text-[11px] font-medium text-ink/70">{c.front}</div>
          </button>
        ))}
      </div>

      <div className="flex flex-1 flex-col overflow-y-auto p-6">
        <div className="mx-auto mb-2 flex w-full max-w-2xl items-center justify-between text-xs text-ink/40">
          <span>
            Card {current + 1} of {cards.length}
          </span>
          {supplementary ? (
            <span className="inline-flex items-center gap-1 rounded-full bg-amber-50 px-2 py-0.5 font-medium text-amber-700">
              <Sparkles className="h-3 w-3" />
              beyond your materials
            </span>
          ) : (
            <span className="text-emerald-600">from your materials</span>
          )}
        </div>

        <AnimatePresence mode="wait">
          <motion.button
            key={`${card.id}-${flipped ? "back" : "front"}`}
            onClick={() => setFlipped((f) => !f)}
            initial={{ opacity: 0, rotateX: -90 }}
            animate={{ opacity: 1, rotateX: 0 }}
            exit={{ opacity: 0, rotateX: 90 }}
            transition={{ duration: 0.18 }}
            className={cn(
              "mx-auto flex aspect-[16/10] w-full max-w-2xl flex-col items-center justify-center rounded-2xl border p-8 text-center shadow-sm",
              flipped ? "border-brand/40 bg-brandsoft" : "border-line bg-panel"
            )}
          >
            <span className="mb-3 text-[10px] font-semibold uppercase tracking-wide text-ink/40">
              {flipped ? "Answer" : "Question"}
            </span>
            <span className={cn("leading-relaxed text-ink/90", flipped ? "text-lg" : "text-2xl font-semibold")}>
              {flipped ? card.back : card.front}
            </span>
            <span className="mt-6 inline-flex items-center gap-1 text-[11px] text-ink/40">
              <RefreshCw className="h-3 w-3" />
              click to flip
            </span>
          </motion.button>
        </AnimatePresence>

        <div className="mx-auto mt-4 flex w-full max-w-2xl items-center justify-between gap-3">
          <div className="flex flex-wrap items-center gap-1.5">
            {card.citations.length > 0 ? (
              card.citations.map((c, i) => <CitationBadge key={i} citation={c} />)
            ) : supplementary ? (
              <span className="text-[11px] text-ink/40">general knowledge, not from your files</span>
            ) : null}
          </div>
          <div className="flex shrink-0 items-center gap-1">
            <button
              onClick={() => go(Math.max(0, current - 1))}
              disabled={current === 0}
              className="rounded-md p-1.5 text-ink/60 hover:bg-black/5 disabled:opacity-30"
              title="Previous card"
            >
              <ChevronLeft className="h-4 w-4" />
            </button>
            <button
              onClick={() => go(Math.min(cards.length - 1, current + 1))}
              disabled={current === cards.length - 1}
              className="rounded-md p-1.5 text-ink/60 hover:bg-black/5 disabled:opacity-30"
              title="Next card"
            >
              <ChevronRight className="h-4 w-4" />
            </button>
          </div>
        </div>

        {!readOnly && (
          <div className="mx-auto mt-6 w-full max-w-2xl border-t border-line pt-4">
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
                placeholder={`Edit these cards, e.g. "simplify card ${current + 1}"`}
                disabled={busy}
                className="flex-1 rounded-lg border border-line bg-panel px-3 py-2 text-sm outline-none focus:border-brand/50"
              />
              <button
                type="submit"
                disabled={busy || !instruction.trim()}
                className="rounded-lg bg-brand p-2 text-white disabled:opacity-40"
                title="Edit cards"
              >
                {busy ? <Loader2 className="h-4 w-4 animate-spin" /> : <Send className="h-4 w-4" />}
              </button>
            </form>
          </div>
        )}
      </div>
    </div>
  );
}
