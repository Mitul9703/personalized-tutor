import type { Components } from "react-markdown";
import { Sparkles } from "lucide-react";
import type { Citation } from "../api/types";
import { CitationBadge } from "./CitationBadge";
import { Markdown } from "./Markdown";

const CITE_HREF = "#cite-";

// A tutor reply in the chat. The QA agent puts markers like [1] in the text,
// and citations[n - 1] is the chunk behind marker [n]. The reply renders as
// markdown with LaTeX math; each marker becomes a clickable badge that shows
// the exact source text, and a numbered source list sits under the reply.
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

  // turn each [n] that has a citation into a markdown link (#cite-n), then
  // render those links as source badges. markers with no citation stay as text.
  const withLinks = text.replace(/\[(\d+)\](?!\()/g, (marker, n) =>
    cites[Number(n) - 1] ? `[${n}](${CITE_HREF}${n})` : marker
  );
  const components: Components = {
    a: ({ href, children }) => {
      if (href?.startsWith(CITE_HREF)) {
        const n = href.slice(CITE_HREF.length);
        const cite = cites[Number(n) - 1];
        if (cite) return <CitationBadge citation={cite} label={n} />;
      }
      return <a href={href} target="_blank" rel="noreferrer">{children}</a>;
    },
  };

  return (
    <div>
      <Markdown components={components}>{withLinks}</Markdown>

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
        <div className="mt-2 inline-flex items-center gap-1 rounded-full bg-goldsoft px-2 py-0.5 text-[11px] font-medium text-goldink">
          <Sparkles className="h-3 w-3" />
          includes general knowledge, not from your files
        </div>
      )}
    </div>
  );
}
