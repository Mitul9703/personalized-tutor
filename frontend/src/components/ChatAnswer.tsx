import { Fragment } from "react";
import { Sparkles } from "lucide-react";
import type { Citation } from "../api/types";
import { CitationBadge } from "./CitationBadge";

// A tutor reply in the chat. The QA agent puts markers like [1] in the text,
// and citations[n - 1] is the chunk behind marker [n]. Each marker becomes a
// clickable badge that shows the exact source text, and a numbered source
// list sits under the reply.
export function ChatAnswer({
  text,
  citations,
  usesGeneralKnowledge,
}: {
  text: string;
  citations?: (Citation | null)[];
  usesGeneralKnowledge?: boolean;
}) {
  const cites = citations ?? [];
  const parts = text.split(/(\[\d+\])/g);

  return (
    <div>
      <div className="whitespace-pre-wrap">
        {parts.map((part, i) => {
          const m = part.match(/^\[(\d+)\]$/);
          const cite = m ? cites[Number(m[1]) - 1] : null;
          if (m && cite) {
            return <CitationBadge key={i} citation={cite} label={m[1]} />;
          }
          return <Fragment key={i}>{part}</Fragment>;
        })}
      </div>

      {cites.some(Boolean) && (
        <div className="mt-2 border-t border-line pt-2">
          <div className="mb-1 text-[10px] font-semibold uppercase tracking-wide text-ink/40">Sources</div>
          <div className="flex flex-wrap gap-1.5">
            {cites.map((c, i) =>
              c ? (
                <CitationBadge
                  key={i}
                  citation={c}
                  label={`[${i + 1}] ${[c.doc, c.loc].filter(Boolean).join(" · ") || "source"}`}
                />
              ) : null
            )}
          </div>
        </div>
      )}

      {usesGeneralKnowledge && (
        <div className="mt-2 inline-flex items-center gap-1 rounded-full bg-amber-50 px-2 py-0.5 text-[11px] font-medium text-amber-700">
          <Sparkles className="h-3 w-3" />
          includes general knowledge, not from your files
        </div>
      )}
    </div>
  );
}
