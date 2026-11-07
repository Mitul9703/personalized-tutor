import { History } from "lucide-react";
import { useStore } from "../store/useStore";
import { cn } from "../lib/cn";

export function VersionBar() {
  const detail = useStore((s) => s.artifactDetail);
  const viewing = useStore((s) => s.viewingVersionId);
  const selectVersion = useStore((s) => s.selectVersion);

  if (!detail) return null;
  const activeId = viewing ?? detail.current_version_id;

  return (
    <div className="flex items-center gap-2 border-b border-line px-3 py-2">
      <History className="h-3.5 w-3.5 shrink-0 text-ink/40" />
      <div className="flex flex-1 items-center gap-1 overflow-x-auto">
        {detail.versions.map((v) => (
          <button
            key={v.version_id}
            onClick={() => selectVersion(v.version_id)}
            title={v.caused_by}
            className={cn(
              "shrink-0 rounded-md px-2 py-1 text-xs transition",
              v.version_id === activeId ? "bg-brand text-white" : "text-ink/60 hover:bg-black/5"
            )}
          >
            v{v.version_number}
          </button>
        ))}
      </div>
    </div>
  );
}
