import { useEffect, useState } from "react";
import { AnimatePresence } from "framer-motion";
import type { Deck } from "../api/types";
import { SlideView } from "./SlideView";
import { cn } from "../lib/cn";

export function SlideDeck({ deck, readOnly }: { deck: Deck; readOnly: boolean }) {
  const [current, setCurrent] = useState(0);

  useEffect(() => {
    setCurrent((c) => Math.min(c, Math.max(0, deck.slides.length - 1)));
  }, [deck]);

  const slide = deck.slides[current];

  return (
    <div className="flex h-full min-h-0">
      <div className="w-40 shrink-0 space-y-2 overflow-y-auto border-r border-line p-3">
        {deck.slides.map((s, i) => (
          <button
            key={s.id}
            onClick={() => setCurrent(i)}
            className={cn(
              "w-full rounded-lg border p-2 text-left transition",
              i === current ? "border-brand bg-brandsoft" : "border-line bg-panel hover:border-brand/40"
            )}
          >
            <div className="mb-1 flex items-center justify-between text-[9px] text-ink/40">
              <span>{i + 1}</span>
              {s.provenance === "supplementary" && <span className="text-amber-500">◆</span>}
            </div>
            <div className="line-clamp-2 text-[11px] font-medium text-ink/70">{s.heading}</div>
          </button>
        ))}
      </div>

      <div className="flex-1 overflow-y-auto p-6">
        <AnimatePresence mode="wait">
          {slide && (
            <SlideView
              key={slide.id}
              slide={slide}
              index={current}
              total={deck.slides.length}
              readOnly={readOnly}
            />
          )}
        </AnimatePresence>
      </div>
    </div>
  );
}
