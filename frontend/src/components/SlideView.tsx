import { motion } from "framer-motion";
import { MessageSquarePlus, Sparkles } from "lucide-react";
import type { Slide } from "../api/types";
import { CitationBadge } from "./CitationBadge";
import { useStore } from "../store/useStore";
import { cn } from "../lib/cn";

export function SlideView({ slide, index, total, readOnly }: {
  slide: Slide;
  index: number;
  total: number;
  readOnly: boolean;
}) {
  const focusSlide = useStore((s) => s.focusSlide);
  const focusedSlideId = useStore((s) => s.focusedSlideId);
  const focused = focusedSlideId === slide.id;
  const supplementary = slide.provenance === "supplementary";

  return (
    <motion.div
      key={slide.id}
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.2 }}
      className="mx-auto flex aspect-[16/10] w-full max-w-3xl flex-col rounded-2xl border border-line bg-panel p-8 shadow-sm"
    >
      <div className="mb-1 flex items-center justify-between text-xs text-ink/40">
        <span>
          Slide {index + 1} of {total}
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

      <h2 className="mt-2 text-2xl font-semibold leading-tight">{slide.heading}</h2>

      <ul className="mt-5 flex-1 space-y-3">
        {slide.bullets.map((b, i) => (
          <li key={i} className="flex gap-3 text-[15px] leading-relaxed text-ink/80">
            <span className="mt-2 h-1.5 w-1.5 shrink-0 rounded-full bg-brand/60" />
            <span>{b}</span>
          </li>
        ))}
      </ul>

      <div className="mt-4 flex items-center justify-between gap-3 border-t border-line pt-3">
        <div className="flex flex-wrap items-center gap-1.5">
          {slide.citations.length > 0 ? (
            slide.citations.map((c, i) => <CitationBadge key={i} citation={c} />)
          ) : supplementary ? (
            <span className="text-[11px] text-ink/40">general knowledge, not from your files</span>
          ) : null}
        </div>
        {!readOnly && (
          <button
            onClick={() => focusSlide(focused ? null : slide.id)}
            className={cn(
              "inline-flex shrink-0 items-center gap-1.5 rounded-lg px-2.5 py-1.5 text-xs font-medium transition",
              focused ? "bg-brand text-white" : "text-brand hover:bg-brandsoft"
            )}
          >
            <MessageSquarePlus className="h-3.5 w-3.5" />
            {focused ? "Talking about this slide" : "Ask about this slide"}
          </button>
        )}
      </div>
    </motion.div>
  );
}
