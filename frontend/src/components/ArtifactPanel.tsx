import { Layers, Maximize2, Minimize2, RotateCcw, X } from "lucide-react";
import { useStore } from "../store/useStore";
import { VersionBar } from "./VersionBar";
import { SlideDeck } from "./SlideDeck";

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

  if (!deck) return null;
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
        <div className="flex items-center gap-2 bg-amber-50 px-4 py-2 text-xs text-amber-800">
          <span>Viewing version {viewingNumber} (older, read-only).</span>
          <button
            onClick={() => restoreVersion(viewing)}
            className="ml-auto inline-flex items-center gap-1 rounded-md bg-amber-600 px-2 py-1 font-medium text-white hover:bg-amber-700"
          >
            <RotateCcw className="h-3 w-3" />
            Restore this
          </button>
          <button
            onClick={() => selectVersion(null)}
            className="rounded-md px-2 py-1 font-medium hover:bg-amber-100"
          >
            Back to latest
          </button>
        </div>
      )}

      <div className="min-h-0 flex-1">
        <SlideDeck deck={deck} readOnly={!!viewing} />
      </div>
    </div>
  );
}
