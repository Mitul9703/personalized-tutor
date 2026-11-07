import { useState } from "react";
import { ChevronDown, Map } from "lucide-react";
import { useStore } from "../store/useStore";
import { cn } from "../lib/cn";

export function CourseMap() {
  const outline = useStore((s) => s.outline);
  const send = useStore((s) => s.send);
  const busy = useStore((s) => s.busy);
  const [open, setOpen] = useState(true);

  const topics = outline?.topics ?? [];
  if (topics.length === 0) return null;

  return (
    <div className="border-b border-line">
      <button
        onClick={() => setOpen((v) => !v)}
        className="flex w-full items-center gap-2 px-4 py-2.5 text-left text-xs font-semibold uppercase tracking-wide text-ink/50 hover:bg-black/[0.02]"
      >
        <Map className="h-3.5 w-3.5" />
        Course map
        <ChevronDown className={cn("ml-auto h-4 w-4 transition", open ? "" : "-rotate-90")} />
      </button>
      {open && (
        <div className="flex flex-wrap gap-1.5 px-4 pb-3">
          {topics.map((t) => (
            <button
              key={t.topic}
              disabled={busy}
              onClick={() => send(`Teach me about ${t.topic}`)}
              title={t.summary}
              className="rounded-full border border-line bg-panel px-3 py-1 text-xs text-ink/70 transition hover:border-brand/40 hover:bg-brandsoft hover:text-brand disabled:opacity-50"
            >
              {t.topic}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
