import { useState } from "react";
import { Send, X } from "lucide-react";
import { useStore } from "../store/useStore";

const SUGGESTIONS = [
  "Explain this more deeply",
  "Make it simpler",
  "Give me an example",
  "Summarize the key points",
];

export function ChatInput() {
  const send = useStore((s) => s.send);
  const busy = useStore((s) => s.busy || s.profileSaving);
  const deck = useStore((s) => s.deck);
  const focusedSlideId = useStore((s) => s.focusedSlideId);
  const focusSlide = useStore((s) => s.focusSlide);
  const [text, setText] = useState("");

  const focusedIndex = deck && focusedSlideId ? deck.slides.findIndex((s) => s.id === focusedSlideId) : -1;
  const focusedSlide = focusedIndex >= 0 ? deck!.slides[focusedIndex] : null;

  const submit = () => {
    const t = text.trim();
    if (!t || busy) return;
    send(t);
    setText("");
  };

  return (
    <div className="border-t border-line p-3">
      {deck && (
        <div className="mb-2 flex flex-wrap gap-1.5">
          {SUGGESTIONS.map((s) => (
            <button
              key={s}
              disabled={busy}
              onClick={() => setText(s)}
              className="rounded-full bg-black/[0.03] px-2.5 py-1 text-xs text-ink/60 transition hover:bg-brandsoft hover:text-brand disabled:opacity-50"
            >
              {s}
            </button>
          ))}
        </div>
      )}

      {focusedSlide && (
        <div className="mb-2 inline-flex items-center gap-1.5 rounded-lg bg-brandsoft px-2.5 py-1 text-xs text-brand">
          Re: Slide {focusedIndex + 1} · {focusedSlide.heading}
          <button onClick={() => focusSlide(null)} className="hover:text-indigo-800">
            <X className="h-3 w-3" />
          </button>
        </div>
      )}

      <div className="flex items-end gap-2 rounded-xl border border-line bg-panel p-2">
        <textarea
          value={text}
          onChange={(e) => setText(e.target.value)}
          rows={1}
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.shiftKey) {
              e.preventDefault();
              submit();
            }
          }}
          placeholder="Ask for a topic, or say explain this, simplify that, undo…"
          className="max-h-40 flex-1 resize-none bg-transparent px-1 py-1.5 text-sm outline-none placeholder:text-ink/30"
        />
        <button
          onClick={submit}
          disabled={busy || !text.trim()}
          className="inline-flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-brand text-white transition hover:bg-indigo-600 disabled:opacity-40"
        >
          <Send className="h-4 w-4" />
        </button>
      </div>
    </div>
  );
}
