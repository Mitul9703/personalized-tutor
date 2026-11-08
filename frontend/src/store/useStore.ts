import { create } from "zustand";
import { api } from "../api/client";
import type {
  ArtifactDetail,
  ChatMessage,
  Deck,
  DeckRef,
  Outline,
  LearnerProfile,
  TurnResponse,
} from "../api/types";

type Phase = "upload" | "ingesting" | "ready";
type PanelMode = "split" | "full" | "closed";

let courseLoadSequence = 0;
let profileLoadSequence = 0;

interface SetupProgress {
  file: File;
  courseId: string | null;
  title: string;
  profile: LearnerProfile | null;
  uploaded: boolean;
}

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
  learnerProfile: LearnerProfile | null;
  profileLoading: boolean;
  profileLoaded: boolean;
  profileSaving: boolean;
  profileError: string | null;
  setupProgress: SetupProgress | null;

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

  startFromFile: (file: File, profile: LearnerProfile) => Promise<void>;
  loadProfile: () => Promise<void>;
  saveProfile: (profile: LearnerProfile) => Promise<boolean>;
  resumeCourse: (courseId: string) => Promise<void>;
  send: (text: string) => Promise<void>;
  selectDeck: (artifactId: string) => Promise<void>;
  selectVersion: (versionId: string | null) => Promise<void>;
  restoreVersion: (versionId: string) => Promise<void>;
  focusSlide: (slideId: string | null) => void;
  setPanelMode: (mode: PanelMode) => void;
  refreshDecks: () => Promise<void>;
  dismissError: () => void;
}

export const useStore = create<State>((set, get) => ({
  phase: "upload",
  ingestMsg: "",
  courseId: null,
  courseTitle: null,
  outline: null,
  learnerProfile: null,
  profileLoading: false,
  profileLoaded: false,
  profileSaving: false,
  profileError: null,
  setupProgress: null,
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

  startFromFile: async (file, profile) => {
    if (get().phase === "ingesting") return;
    const previous = get().setupProgress;
    let progress: SetupProgress = previous?.file === file ? previous : {
      file, courseId: null, title: file.name.replace(/\.[^.]+$/, "") || "My course",
      profile: null, uploaded: false,
    };
    set({ setupProgress: progress });
    set({ phase: "ingesting", ingestMsg: "Creating your workspace…", error: null });
    try {
      if (!progress.courseId) {
        const course = await api.createCourse(progress.title);
        progress = { ...progress, courseId: course.course_id, title: course.title };
        set({ setupProgress: progress, courseId: course.course_id, courseTitle: course.title });
      }
      const courseId = progress.courseId!;
      if (JSON.stringify(progress.profile) !== JSON.stringify(profile)) {
        set({ ingestMsg: "Saving your learner profile…", profileSaving: true, profileError: null });
        try {
          const saved = await api.saveOnboarding(courseId, profile);
          if (!saved.profile) throw new Error("Your profile was not saved. Please retry.");
          progress = { ...progress, profile: saved.profile };
          set({ learnerProfile: saved.profile, profileLoaded: true, setupProgress: progress });
        } catch (e) {
          set({ profileError: String(e) });
          throw e;
        } finally {
          set({ profileSaving: false });
        }
      }
      if (!progress.uploaded) {
        set({ ingestMsg: "Reading and indexing your material…" });
        await api.uploadDocument(courseId, file);
        progress = { ...progress, uploaded: true };
        set({ setupProgress: progress });
      }
      set({ ingestMsg: "Building your course map…" });
      const outline = await api.survey(courseId);
      const count = outline.topics?.length ?? 0;
      set({
        outline,
        phase: "ready",
        setupProgress: null,
        messages: [
          {
            id: rid(),
            role: "system",
            text: `Your course is ready. I read your material and mapped out ${count} topics. Ask me to teach any of them, or anything else.`,
          },
        ],
      });
      const url = new URL(window.location.href);
      url.searchParams.set("course", courseId);
      window.history.replaceState(null, "", url);
    } catch (e) {
      set({ phase: "upload", error: String(e) });
    }
  },

  loadProfile: async () => {
    const { courseId, profileLoading } = get();
    if (!courseId || profileLoading) return;
    const sequence = ++profileLoadSequence;
    set({ profileLoading: true, profileError: null });
    try {
      const res = await api.getOnboarding(courseId);
      if (get().courseId === courseId && sequence === profileLoadSequence) set({ learnerProfile: res.profile, profileLoaded: true });
    } catch (e) {
      if (get().courseId === courseId && sequence === profileLoadSequence) set({ profileError: String(e) });
    } finally {
      if (get().courseId === courseId && sequence === profileLoadSequence) set({ profileLoading: false });
    }
  },

  saveProfile: async (profile) => {
    const { courseId, busy, profileSaving, profileLoading, phase } = get();
    if (!courseId || busy || profileSaving || profileLoading || phase !== "ready") return false;
    set({ profileSaving: true, profileError: null });
    try {
      const res = await api.saveOnboarding(courseId, profile);
      if (!res.profile) throw new Error("Your profile was not saved. Please retry.");
      if (get().courseId !== courseId) return false;
      set({ learnerProfile: res.profile, profileLoaded: true });
      return true;
    } catch (e) {
      if (get().courseId === courseId) set({ profileError: String(e) });
      return false;
    } finally {
      if (get().courseId === courseId) set({ profileSaving: false });
    }
  },

  resumeCourse: async (courseId) => {
    const sequence = ++courseLoadSequence;
    ++profileLoadSequence;
    set({
      phase: "ingesting", ingestMsg: "Loading your course…", courseId, courseTitle: null, error: null,
      learnerProfile: null, profileError: null, profileLoading: false, profileLoaded: false, profileSaving: false,
      setupProgress: null, outline: null, messages: [], decks: [], activeArtifactId: null,
      deck: null, artifactDetail: null, viewingVersionId: null, focusedSlideId: null, panelMode: "closed",
    });
    try {
      const [outline, msgs, decks, course] = await Promise.all([
        api.getOutline(courseId).catch(() => ({ topics: [] }) as Outline),
        api.listMessages(courseId).catch(() => []),
        api.listArtifacts(courseId).catch(() => []),
        api.getCourse(courseId),
        get().loadProfile(),
      ]);
      if (get().courseId !== courseId || sequence !== courseLoadSequence) return;
      const messages: ChatMessage[] = msgs.map((m) => ({
        id: m.id,
        role: m.role,
        text: m.text,
        artifactId: m.artifact_id,
      }));
      set({ outline, decks, messages, phase: "ready", courseTitle: course.title });
      if (decks.length > 0) {
        await get().selectDeck(decks[decks.length - 1].artifact_id);
      }
    } catch (e) {
      if (get().courseId === courseId && sequence === courseLoadSequence) set({ phase: "upload", error: String(e) });
    }
  },

  send: async (text) => {
    const { courseId, focusedSlideId, activeArtifactId, busy, profileSaving } = get();
    if (!courseId || !text.trim() || busy || profileSaving) return;
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
    const { activeArtifactId, busy, profileSaving } = get();
    if (!activeArtifactId || busy || profileSaving) return;
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
  refreshDecks: async () => {
    const { courseId } = get();
    if (!courseId) return;
    const decks = await api.listArtifacts(courseId);
    set({ decks });
  },
  dismissError: () => set({ error: null }),
}));
