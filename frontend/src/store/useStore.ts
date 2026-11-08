import { create } from "zustand";
import { api } from "../api/client";
import type {
  ArtifactDetail,
  ChatMessage,
  Deck,
  DeckRef,
  Outline,
  TurnResponse,
} from "../api/types";

type Phase = "upload" | "ingesting" | "ready";
type PanelMode = "split" | "full" | "closed";

function rid(): string {
  return `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
}

function systemLine(res: TurnResponse): string {
  const title = res.deck?.title ?? "the deck";
  if (res.intent === "new_topic") return `Created "${title}".`;
  if (res.intent === "revert") return `Reverted to version ${res.version_number}.`;
  return `Updated "${title}".`;
}

interface State {
  phase: Phase;
  ingestMsg: string;
  courseId: string | null;
  courseTitle: string | null;
  outline: Outline | null;

  messages: ChatMessage[];
  decks: DeckRef[];

  activeArtifactId: string | null;
  deck: Deck | null;
  artifactDetail: ArtifactDetail | null;
  viewingVersionId: string | null; // null means viewing the current version
  focusedSlideId: string | null;

  busy: boolean;
  panelMode: PanelMode;
  error: string | null;

  startFromFile: (file: File) => Promise<void>;
  resumeCourse: (courseId: string) => Promise<void>;
  send: (text: string) => Promise<void>;
  selectDeck: (artifactId: string) => Promise<void>;
  selectVersion: (versionId: string | null) => Promise<void>;
  restoreVersion: (versionId: string) => Promise<void>;
  focusSlide: (slideId: string | null) => void;
  setPanelMode: (mode: PanelMode) => void;
  createFlashcards: (topic: string) => Promise<void>;
  editFlashcards: (instruction: string) => Promise<void>;
  refreshDecks: () => Promise<void>;
  dismissError: () => void;
}

export const useStore = create<State>((set, get) => ({
  phase: "upload",
  ingestMsg: "",
  courseId: null,
  courseTitle: null,
  outline: null,
  messages: [],
  decks: [],
  activeArtifactId: null,
  deck: null,
  artifactDetail: null,
  viewingVersionId: null,
  focusedSlideId: null,
  busy: false,
  panelMode: "closed",
  error: null,

  startFromFile: async (file) => {
    set({ phase: "ingesting", ingestMsg: "Creating your workspace…", error: null });
    try {
      const course = await api.createCourse(file.name.replace(/\.[^.]+$/, "") || "My course");
      set({ courseId: course.course_id, courseTitle: course.title, ingestMsg: "Reading and indexing your material…" });
      await api.uploadDocument(course.course_id, file);
      set({ ingestMsg: "Building your course map…" });
      const outline = await api.survey(course.course_id);
      const count = outline.topics?.length ?? 0;
      set({
        outline,
        phase: "ready",
        messages: [
          {
            id: rid(),
            role: "system",
            text: `Your course is ready. I read your material and mapped out ${count} topics. Ask me to teach any of them, or anything else.`,
          },
        ],
      });
    } catch (e) {
      set({ phase: "upload", error: String(e) });
    }
  },

  resumeCourse: async (courseId) => {
    set({ phase: "ingesting", ingestMsg: "Loading your course…", courseId, error: null });
    try {
      const [outline, msgs, decks] = await Promise.all([
        api.getOutline(courseId).catch(() => ({ topics: [] }) as Outline),
        api.listMessages(courseId).catch(() => []),
        api.listArtifacts(courseId).catch(() => []),
      ]);
      const messages: ChatMessage[] = msgs.map((m) => ({
        id: m.id,
        role: m.role,
        text: m.text,
        artifactId: m.artifact_id,
      }));
      set({ outline, decks, messages, phase: "ready" });
      if (decks.length > 0) {
        await get().selectDeck(decks[decks.length - 1].artifact_id);
      }
    } catch (e) {
      set({ phase: "upload", error: String(e) });
    }
  },

  send: async (text) => {
    const { courseId, focusedSlideId, activeArtifactId } = get();
    if (!courseId || !text.trim()) return;
    const hint = focusedSlideId ? activeArtifactId : null;
    set((s) => ({
      messages: [...s.messages, { id: rid(), role: "learner", text }],
      busy: true,
      error: null,
    }));
    try {
      const res = await api.sendMessage(courseId, text, hint);
      if (res.deck && res.artifact_id) {
        const detail = await api.getArtifact(res.artifact_id);
        set((s) => ({
          messages: [...s.messages, { id: rid(), role: "system", text: systemLine(res), artifactId: res.artifact_id }],
          activeArtifactId: res.artifact_id!,
          deck: res.deck!,
          artifactDetail: detail,
          viewingVersionId: null,
          panelMode: s.panelMode === "closed" ? "split" : s.panelMode,
        }));
        await get().refreshDecks();
      } else {
        set((s) => ({
          messages: [...s.messages, { id: rid(), role: "system", text: res.reply ?? "…" }],
        }));
      }
    } catch (e) {
      set({ error: String(e) });
    } finally {
      set({ busy: false, focusedSlideId: null });
    }
  },

  selectDeck: async (artifactId) => {
    const detail = await api.getArtifact(artifactId);
    const v = await api.getVersion(artifactId, detail.current_version_id);
    set({ activeArtifactId: artifactId, artifactDetail: detail, deck: v.deck, viewingVersionId: null, panelMode: "split", focusedSlideId: null });
  },

  selectVersion: async (versionId) => {
    const { activeArtifactId, artifactDetail } = get();
    if (!activeArtifactId || !artifactDetail) return;
    const vid = versionId ?? artifactDetail.current_version_id;
    const v = await api.getVersion(activeArtifactId, vid);
    set({ deck: v.deck, viewingVersionId: vid === artifactDetail.current_version_id ? null : vid });
  },

  restoreVersion: async (versionId) => {
    const { activeArtifactId } = get();
    if (!activeArtifactId) return;
    set({ busy: true });
    try {
      const res = await api.revert(activeArtifactId, versionId);
      const detail = await api.getArtifact(activeArtifactId);
      set((s) => ({
        deck: res.deck,
        artifactDetail: detail,
        viewingVersionId: null,
        messages: [...s.messages, { id: rid(), role: "system", text: `Restored to version ${res.version_number}.` }],
      }));
    } finally {
      set({ busy: false });
    }
  },

  focusSlide: (slideId) => set({ focusedSlideId: slideId }),
  setPanelMode: (mode) => set({ panelMode: mode }),
  createFlashcards: async (topic) => {
    const { courseId } = get();
    if (!courseId || !topic.trim()) return;
    set((s) => ({
      messages: [...s.messages, { id: rid(), role: "learner", text: `Make flashcards about ${topic}` }],
      busy: true,
      error: null,
    }));
    try {
      const res = await api.createFlashcards(courseId, topic);
      const detail = await api.getArtifact(res.artifact_id);
      set((s) => ({
        messages: [
          ...s.messages,
          { id: rid(), role: "system", text: `Created flashcards "${res.content.title}".`, artifactId: res.artifact_id },
        ],
        activeArtifactId: res.artifact_id,
        // the panel holds the current artifact's content here and switches on artifactDetail.type
        deck: res.content as unknown as Deck,
        artifactDetail: detail,
        viewingVersionId: null,
        panelMode: s.panelMode === "closed" ? "split" : s.panelMode,
      }));
      await get().refreshDecks();
    } catch (e) {
      set({ error: String(e) });
    } finally {
      set({ busy: false });
    }
  },

  editFlashcards: async (instruction) => {
    const { activeArtifactId } = get();
    if (!activeArtifactId || !instruction.trim()) return;
    set((s) => ({
      messages: [...s.messages, { id: rid(), role: "learner", text: instruction }],
      busy: true,
      error: null,
    }));
    try {
      const res = await api.editFlashcards(activeArtifactId, instruction);
      const detail = await api.getArtifact(activeArtifactId);
      set((s) => ({
        messages: [
          ...s.messages,
          { id: rid(), role: "system", text: `Updated flashcards "${res.content.title}".`, artifactId: activeArtifactId },
        ],
        deck: res.content as unknown as Deck,
        artifactDetail: detail,
        viewingVersionId: null,
      }));
    } catch (e) {
      set({ error: String(e) });
    } finally {
      set({ busy: false });
    }
  },

  refreshDecks: async () => {
    const { courseId } = get();
    if (!courseId) return;
    const decks = await api.listArtifacts(courseId);
    set({ decks });
  },
  dismissError: () => set({ error: null }),
}));
