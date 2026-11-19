import { useEffect, useMemo, useState } from "react";
import { Loader2, Send, Sparkles } from "lucide-react";
import type { MindMap, MindNode } from "../api/types";
import { CitationBadge } from "./CitationBadge";
import { useStore } from "../store/useStore";
import { cn } from "../lib/cn";

const QUICK_EDITS = ["Add more detail", "Go deeper on one branch", "Simplify the map"];

const NODE_W = 170;
const NODE_H = 54;
const COL = 220; // horizontal gap between tree levels
const ROW = 74; // vertical gap between leaf nodes
const PAD = 24;

type Pos = { x: number; y: number };

// Lay the nodes out as a tidy left-to-right tree. Each level is a column; a
// leaf takes the next free row, and a parent sits centred on its children.
function layout(nodes: MindNode[]): { pos: Record<string, Pos>; width: number; height: number; rootId: string } {
  const pos: Record<string, Pos> = {};
  if (nodes.length === 0) return { pos, width: 0, height: 0, rootId: "" };

  const childrenOf = (id: string | null) => nodes.filter((n) => (n.parent_id ?? null) === id);
  const root = nodes.find((n) => !n.parent_id) ?? nodes[0];

  let nextRow = 0;
  const seen = new Set<string>();
  const place = (id: string, depth: number) => {
    if (seen.has(id)) return; // guard against a malformed cycle
    seen.add(id);
    const kids = childrenOf(id);
    if (kids.length === 0) {
      pos[id] = { x: depth * COL, y: nextRow * ROW };
      nextRow += 1;
      return;
    }
    kids.forEach((k) => place(k.id, depth + 1));
    const ys = kids.map((k) => pos[k.id]?.y ?? 0);
    pos[id] = { x: depth * COL, y: (Math.min(...ys) + Math.max(...ys)) / 2 };
  };
  place(root.id, 0);
  // any node not reachable from the root still gets a spot, so nothing is lost
  nodes.forEach((n) => {
    if (!pos[n.id]) {
      pos[n.id] = { x: 0, y: nextRow * ROW };
      nextRow += 1;
    }
  });

  const maxX = Math.max(...Object.values(pos).map((p) => p.x));
  const maxY = Math.max(...Object.values(pos).map((p) => p.y));
  return {
    pos,
    width: maxX + NODE_W + PAD * 2,
    height: maxY + NODE_H + PAD * 2,
    rootId: root.id,
  };
}

// Renders a mind map as a visual tree: node cards joined by curved edges, with
// the root (central topic) on the left. Click a node to read its one-line
// detail and open its sources. Provenance and citations work the same way as
// on slides. The edit box sends a free text instruction to the mind map agent,
// which saves a new version.
export function MindMapView({ map, readOnly }: { map: MindMap; readOnly: boolean }) {
  const nodes = map.nodes ?? [];
  const { pos, width, height, rootId } = useMemo(() => layout(nodes), [map]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [instruction, setInstruction] = useState("");
  const editMindMap = useStore((s) => s.editMindMap);
  const busy = useStore((s) => s.busy);

  useEffect(() => {
    setSelectedId((cur) => (cur && nodes.some((n) => n.id === cur) ? cur : rootId || null));
  }, [map, rootId]);

  const selected = nodes.find((n) => n.id === selectedId) ?? null;

  const submit = (text: string) => {
    if (!text.trim() || busy) return;
    editMindMap(text);
    setInstruction("");
  };

  const edges = nodes
    .filter((n) => n.parent_id && pos[n.parent_id] && pos[n.id])
    .map((n) => {
      const p = pos[n.parent_id as string];
      const c = pos[n.id];
      const x1 = p.x + PAD + NODE_W;
      const y1 = p.y + PAD + NODE_H / 2;
      const x2 = c.x + PAD;
      const y2 = c.y + PAD + NODE_H / 2;
      const dx = Math.max(24, (x2 - x1) / 2);
      return { id: n.id, d: `M ${x1} ${y1} C ${x1 + dx} ${y1}, ${x2 - dx} ${y2}, ${x2} ${y2}` };
    });

  return (
    <div className="flex h-full min-h-0">
      <div className="flex min-w-0 flex-1 flex-col">
        <div className="min-h-0 flex-1 overflow-auto bg-paper p-2">
          {nodes.length === 0 ? (
            <div className="p-6 text-sm text-ink/50">No nodes yet.</div>
          ) : (
            <div className="relative" style={{ width, height }}>
              <svg className="absolute inset-0 pointer-events-none" width={width} height={height}>
                {edges.map((e) => (
                  <path key={e.id} d={e.d} fill="none" stroke="currentColor" strokeWidth={1.5} className="text-line" />
                ))}
              </svg>
              {nodes.map((n) => {
                const p = pos[n.id];
                if (!p) return null;
                const isRoot = n.id === rootId;
                const supplementary = n.provenance === "supplementary";
                return (
                  <button
                    key={n.id}
                    onClick={() => setSelectedId(n.id)}
                    style={{ left: p.x + PAD, top: p.y + PAD, width: NODE_W, minHeight: NODE_H }}
                    className={cn(
                      "absolute flex flex-col justify-center rounded-xl border px-3 py-2 text-left shadow-sm transition",
                      isRoot ? "bg-brand text-white border-brand" : "bg-panel hover:border-brand/40",
                      !isRoot && supplementary ? "border-amber-300" : !isRoot ? "border-line" : "",
                      n.id === selectedId && !isRoot ? "ring-2 ring-brand" : "",
                      n.id === selectedId && isRoot ? "ring-2 ring-brand/40" : ""
                    )}
                  >
                    <span className={cn("line-clamp-2 text-xs font-semibold", isRoot ? "text-white" : "text-ink/80")}>
                      {n.label}
                    </span>
                    {!isRoot && (
                      <span className="mt-0.5 flex items-center gap-1 text-[9px]">
                        {supplementary ? (
                          <span className="text-amber-500">◆ beyond materials</span>
                        ) : (
                          <span className="text-emerald-600">● from materials</span>
                        )}
                      </span>
                    )}
                  </button>
                );
              })}
            </div>
          )}
        </div>

        {!readOnly && (
          <div className="border-t border-line px-4 py-3">
            <div className="mb-2 flex flex-wrap gap-1.5">
              {QUICK_EDITS.map((q) => (
                <button
                  key={q}
                  onClick={() => submit(q)}
                  disabled={busy}
                  className="rounded-full border border-line px-2.5 py-1 text-[11px] text-ink/60 hover:border-brand/40 hover:text-brand disabled:opacity-40"
                >
                  {q}
                </button>
              ))}
            </div>
            <form
              onSubmit={(e) => {
                e.preventDefault();
                submit(instruction);
              }}
              className="flex items-center gap-2"
            >
              <input
                value={instruction}
                onChange={(e) => setInstruction(e.target.value)}
                placeholder='Edit this map, e.g. "add a branch on regularization"'
                disabled={busy}
                className="flex-1 rounded-lg border border-line bg-panel px-3 py-2 text-sm outline-none focus:border-brand/50"
              />
              <button
                type="submit"
                disabled={busy || !instruction.trim()}
                className="rounded-lg bg-brand p-2 text-white disabled:opacity-40"
                title="Edit mind map"
              >
                {busy ? <Loader2 className="h-4 w-4 animate-spin" /> : <Send className="h-4 w-4" />}
              </button>
            </form>
          </div>
        )}
      </div>

      {/* detail panel for the selected node */}
      <div className="w-64 shrink-0 overflow-y-auto border-l border-line p-4">
        {selected ? (
          <>
            <div className="mb-1 text-[10px] font-semibold uppercase tracking-wide text-ink/40">Concept</div>
            <div className="mb-2 text-sm font-semibold text-ink/90">{selected.label}</div>
            {selected.detail && <p className="mb-3 text-[13px] leading-relaxed text-ink/70">{selected.detail}</p>}
            <div className="mb-2">
              {selected.provenance === "supplementary" ? (
                <span className="inline-flex items-center gap-1 rounded-full bg-amber-50 px-2 py-0.5 text-[11px] font-medium text-amber-700">
                  <Sparkles className="h-3 w-3" />
                  beyond your materials
                </span>
              ) : (
                <span className="text-[11px] text-emerald-600">from your materials</span>
              )}
            </div>
            <div className="flex flex-wrap gap-1.5">
              {selected.citations.length > 0 ? (
                selected.citations.map((c, i) => <CitationBadge key={i} citation={c} />)
              ) : selected.provenance === "supplementary" ? (
                <span className="text-[11px] text-ink/40">general knowledge, not from your files</span>
              ) : null}
            </div>
          </>
        ) : (
          <div className="text-sm text-ink/50">Click a node to see its detail and sources.</div>
        )}
      </div>
    </div>
  );
}
