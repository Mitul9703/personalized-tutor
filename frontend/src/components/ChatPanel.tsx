import { useEffect, useRef } from "react";
import { GraduationCap, Loader2, PanelRightOpen } from "lucide-react";
import { useStore } from "../store/useStore";
import { CourseMap } from "./CourseMap";
import { ChatInput } from "./ChatInput";
import { cn } from "../lib/cn";

export function ChatPanel() {
  const messages = useStore((s) => s.messages);
  const busy = useStore((s) => s.busy);
  const error = useStore((s) => s.error);
  const dismissError = useStore((s) => s.dismissError);
  const deck = useStore((s) => s.deck);
  const panelMode = useStore((s) => s.panelMode);
  const setPanelMode = useStore((s) => s.setPanelMode);
  const endRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, busy]);

  return (
    <div className="flex h-full min-h-0 flex-col bg-paper">
      <div className="flex items-center gap-2 border-b border-line px-4 py-3">
        <div className="flex h-7 w-7 items-center justify-center rounded-lg bg-brandsoft text-brand">
          <GraduationCap className="h-4 w-4" />
        </div>
        <span className="font-semibold">Personalized Tutor</span>
        {deck && panelMode === "closed" && (
          <button
            onClick={() => setPanelMode("split")}
            className="ml-auto inline-flex items-center gap-1.5 rounded-lg px-2.5 py-1.5 text-xs font-medium text-brand hover:bg-brandsoft"
          >
            <PanelRightOpen className="h-3.5 w-3.5" />
            Open deck
          </button>
        )}
      </div>

      <CourseMap />

      <div className="min-h-0 flex-1 space-y-3 overflow-y-auto px-4 py-4">
        {messages.map((m) => (
          <div key={m.id} className={cn("flex", m.role === "learner" ? "justify-end" : "justify-start")}>
            <div
              className={cn(
                "max-w-[85%] rounded-2xl px-3.5 py-2 text-sm leading-relaxed",
                m.role === "learner"
                  ? "bg-brand text-white"
                  : "border border-line bg-panel text-ink/80"
              )}
            >
              {m.text}
            </div>
          </div>
        ))}
        {busy && (
          <div className="flex justify-start">
            <div className="inline-flex items-center gap-2 rounded-2xl border border-line bg-panel px-3.5 py-2 text-sm text-ink/50">
              <Loader2 className="h-3.5 w-3.5 animate-spin" />
              Working on it…
            </div>
          </div>
        )}
        <div ref={endRef} />
      </div>

      {error && (
        <div className="mx-4 mb-2 flex items-center gap-2 rounded-lg bg-red-50 px-3 py-2 text-xs text-red-700">
          <span className="flex-1">{error}</span>
          <button onClick={dismissError} className="font-medium">
            dismiss
          </button>
        </div>
      )}

      <ChatInput />
    </div>
  );
}
