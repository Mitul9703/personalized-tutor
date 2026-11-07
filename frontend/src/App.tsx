import { useEffect } from "react";
import { useStore } from "./store/useStore";
import { UploadScreen } from "./components/UploadScreen";
import { ChatPanel } from "./components/ChatPanel";
import { ArtifactPanel } from "./components/ArtifactPanel";
import { cn } from "./lib/cn";

export default function App() {
  const phase = useStore((s) => s.phase);
  const deck = useStore((s) => s.deck);
  const panelMode = useStore((s) => s.panelMode);

  // resume an existing course from ?course=<id> (shareable, reloadable)
  useEffect(() => {
    const id = new URLSearchParams(window.location.search).get("course");
    if (id) useStore.getState().resumeCourse(id);
  }, []);

  if (phase !== "ready") return <UploadScreen />;

  const showPanel = !!deck && panelMode !== "closed";
  const full = showPanel && panelMode === "full";

  return (
    <div className="flex h-full">
      {!full && (
        <div className={cn(showPanel ? "w-[440px] shrink-0" : "mx-auto w-full max-w-2xl")}>
          <ChatPanel />
        </div>
      )}
      {showPanel && (
        <div className="min-w-0 flex-1">
          <ArtifactPanel />
        </div>
      )}
    </div>
  );
}
