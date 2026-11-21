import { useEffect, useRef, useState } from "react";
import { Download, FileText, Layers, Layers3, ListChecks, Loader2, Maximize2, Minimize2, Network, RotateCcw, X } from "lucide-react";
import { useStore } from "../store/useStore";
import type { Doc, FlashcardSet, MindMap, Quiz } from "../api/types";
import { VersionBar } from "./VersionBar";
import { SlideDeck } from "./SlideDeck";
import { QuizView } from "./QuizView";
import { FlashcardDeck } from "./FlashcardDeck";
import { DocView } from "./DocView";
import { MindMapView } from "./MindMapView";
import { ArtifactPdf } from "./ArtifactPdf";
import { exportBlocksPdf } from "../lib/pdf";

export function ArtifactPanel() {
  const deck = useStore((s) => s.deck);
  const detail = useStore((s) => s.artifactDetail);
  const viewing = useStore((s) => s.viewingVersionId);
  const panelMode = useStore((s) => s.panelMode);
  const setPanelMode = useStore((s) => s.setPanelMode);
  const selectVersion = useStore((s) => s.selectVersion);
  const restoreVersion = useStore((s) => s.restoreVersion);
  const decks = useStore((s) => s.decks);
  const selectDeck = useStore((s) => s.selectDeck);
  const activeArtifactId = useStore((s) => s.activeArtifactId);
  const createQuiz = useStore((s) => s.createQuiz);
  const createFlashcards = useStore((s) => s.createFlashcards);
  const createDoc = useStore((s) => s.createDoc);
  const createMindMap = useStore((s) => s.createMindMap);
  const busy = useStore((s) => s.busy);

  const [exporting, setExporting] = useState(false);
  const pdfRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!exporting) return;
    const el = pdfRef.current;
    if (!el || !detail || !deck) {
      setExporting(false);
      return;
    }
    let cancelled = false;
    (async () => {
      try {
        await exportBlocksPdf(el, deck.title ?? detail.title, { slideMode: detail.type === "slides" });
      } catch (e) {
        if (!cancelled) useStore.setState({ error: `Could not make the PDF: ${e}` });
      } finally {
        if (!cancelled) setExporting(false);
      }
    })();
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [exporting]);

  if (!deck) return null;
  const isQuiz = detail?.type === "quiz";
  const isFlashcards = detail?.type === "flashcards";
  const isDoc = detail?.type === "doc";
  const isMindMap = detail?.type === "mindmap";
  const viewingNumber =
    viewing && detail ? detail.versions.find((v) => v.version_id === viewing)?.version_number : null;

  return (
    <div className="flex h-full min-h-0 flex-col bg-paper">
      <div className="flex items-center gap-2 border-b border-line px-4 py-3">
        <Layers className="h-4 w-4 shrink-0 text-brand" />
        <div className="min-w-0 flex-1 truncate font-semibold">{deck.title}</div>

        {decks.length > 1 && (
          <select
            value={activeArtifactId ?? ""}
            onChange={(e) => selectDeck(e.target.value)}
            className="max-w-[150px] rounded-md border border-line bg-panel px-2 py-1 text-xs"
          >
            {decks.map((d) => (
              <option key={d.artifact_id} value={d.artifact_id}>
                {d.title}
              </option>
            ))}
          </select>
        )}

        {!isQuiz && (
          <button
            onClick={() => createQuiz(deck.title)}
            disabled={busy}
            className="inline-flex items-center gap-1.5 rounded-md px-2 py-1 text-xs font-medium text-brand hover:bg-brandsoft disabled:opacity-40"
            title="Make a graded quiz on this topic"
          >
            <ListChecks className="h-3.5 w-3.5" />
            Quiz me
          </button>
        )}

        {!isFlashcards && (
          <button
            onClick={() => createFlashcards(deck.title)}
            disabled={busy}
            className="inline-flex items-center gap-1.5 rounded-md px-2 py-1 text-xs font-medium text-brand hover:bg-brandsoft disabled:opacity-40"
            title="Make flashcards on this topic"
          >
            <Layers3 className="h-3.5 w-3.5" />
            Flashcards
          </button>
        )}

        {!isDoc && (
          <button
            onClick={() => createDoc(deck.title)}
            disabled={busy}
            className="inline-flex items-center gap-1.5 rounded-md px-2 py-1 text-xs font-medium text-brand hover:bg-brandsoft disabled:opacity-40"
            title="Write a doc on this topic"
          >
            <FileText className="h-3.5 w-3.5" />
            Doc
          </button>
        )}

        {!isMindMap && (
          <button
            onClick={() => createMindMap(deck.title)}
            disabled={busy}
            className="inline-flex items-center gap-1.5 rounded-md px-2 py-1 text-xs font-medium text-brand hover:bg-brandsoft disabled:opacity-40"
            title="Make a mind map on this topic"
          >
            <Network className="h-3.5 w-3.5" />
            Mind map
          </button>
        )}

        <button
          onClick={() => !exporting && setExporting(true)}
          disabled={busy || exporting}
          className="inline-flex items-center gap-1.5 rounded-md px-2 py-1 text-xs font-medium text-brand hover:bg-brandsoft disabled:opacity-40"
          title="Download this as a PDF"
        >
          {exporting ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Download className="h-3.5 w-3.5" />}
          PDF
        </button>

        <button
          onClick={() => setPanelMode(panelMode === "full" ? "split" : "full")}
          className="rounded-md p-1.5 text-ink/50 hover:bg-black/5"
          title={panelMode === "full" ? "Split view" : "Fullscreen"}
        >
          {panelMode === "full" ? <Minimize2 className="h-4 w-4" /> : <Maximize2 className="h-4 w-4" />}
        </button>
        <button
          onClick={() => setPanelMode("closed")}
          className="rounded-md p-1.5 text-ink/50 hover:bg-black/5"
          title="Close"
        >
          <X className="h-4 w-4" />
        </button>
      </div>

      <VersionBar />

      {viewing && (
        <div className="flex items-center gap-2 bg-goldsoft px-4 py-2 text-xs text-goldink">
          <span>Viewing version {viewingNumber} (older, read-only).</span>
          <button
            onClick={() => restoreVersion(viewing)}
            className="ml-auto inline-flex items-center gap-1 rounded-md bg-brand px-2 py-1 font-medium text-white hover:bg-branddark"
          >
            <RotateCcw className="h-3 w-3" />
            Restore this
          </button>
          <button
            onClick={() => selectVersion(null)}
            className="rounded-md px-2 py-1 font-medium hover:bg-goldsoft"
          >
            Back to latest
          </button>
        </div>
      )}

      <div className="min-h-0 flex-1">
        {isFlashcards ? (
          <FlashcardDeck set={deck as unknown as FlashcardSet} readOnly={!!viewing} />
        ) : isQuiz && activeArtifactId ? (
          <QuizView
            quiz={deck as unknown as Quiz}
            artifactId={activeArtifactId}
            versionId={viewing ?? detail?.current_version_id ?? null}
          />
        ) : isDoc ? (
          <DocView doc={deck as unknown as Doc} readOnly={!!viewing} />
        ) : isMindMap ? (
          <MindMapView map={deck as unknown as MindMap} readOnly={!!viewing} />
        ) : (
          <SlideDeck deck={deck} readOnly={!!viewing} />
        )}
      </div>

      {exporting && detail && (
        <div aria-hidden className="pointer-events-none fixed left-[-10000px] top-0 -z-10">
          <div ref={pdfRef}>
            <ArtifactPdf detail={detail} deck={deck as any} />
          </div>
        </div>
      )}
    </div>
  );
}
