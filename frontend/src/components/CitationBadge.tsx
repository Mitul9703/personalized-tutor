import { useState } from "react";
import { BookOpen, Loader2 } from "lucide-react";
import type { Citation } from "../api/types";
import { api } from "../api/client";

export function CitationBadge({ citation }: { citation: Citation }) {
  const [open, setOpen] = useState(false);
  const [text, setText] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const toggle = async () => {
    const next = !open;
    setOpen(next);
    if (next && text === null) {
      setLoading(true);
      try {
        const c = await api.getChunk(citation.chunk_id);
        setText(c.text);
      } catch {
        setText("(could not load the source text)");
      } finally {
        setLoading(false);
      }
    }
  };

  const label = citation.loc || citation.doc || "source";

  return (
    <span className="relative inline-block">
      <button
        onClick={toggle}
        className="inline-flex items-center gap-1 rounded-md bg-emerald-50 px-1.5 py-0.5 text-[11px] font-medium text-emerald-700 hover:bg-emerald-100"
      >
        <BookOpen className="h-3 w-3" />
        {label}
      </button>
      {open && (
        <span className="absolute left-0 top-full z-20 mt-1 block w-80 rounded-lg border border-line bg-panel p-3 text-left text-xs leading-relaxed text-ink/80 shadow-lg">
          <span className="mb-1 block text-[10px] font-semibold uppercase tracking-wide text-ink/40">
            From your material{citation.doc ? ` · ${citation.doc}` : ""}
          </span>
          {loading ? (
            <Loader2 className="h-4 w-4 animate-spin text-ink/40" />
          ) : (
            <span>{text}</span>
          )}
        </span>
      )}
    </span>
  );
}
