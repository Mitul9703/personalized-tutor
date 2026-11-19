export interface LearnerProfile {
  level: "beginner" | "intermediate" | "advanced";
  goal: string;
  background: string;
}

export interface OnboardingResponse {
  course_id: string;
  profile: LearnerProfile | null;
}

export interface Citation {
  chunk_id: string;
  doc?: string;
  loc?: string;
}

export interface Visual {
  format: "svg" | "mermaid";
  code: string;
  caption?: string;
}

export interface Slide {
  id: string;
  heading: string;
  bullets: string[];
  notes?: string;
  provenance: "source" | "supplementary";
  citations: Citation[];
  level?: "intro" | "standard" | "deep";
  visual?: Visual | null;
}

export interface Deck {
  title: string;
  slides: Slide[];
}

export interface Flashcard {
  id: string;
  front: string;
  back: string;
  provenance: "source" | "supplementary";
  citations: Citation[];
  visual?: Visual | null;
}

export interface FlashcardSet {
  title: string;
  cards: Flashcard[];
}

export interface FlashcardResponse {
  intent: string;
  type: "flashcards";
  artifact_id: string;
  version_id: string;
  version_number: number;
  content: FlashcardSet;
}

export interface DocSection {
  id: string;
  heading: string;
  body: string;
  provenance: "source" | "supplementary";
  citations: Citation[];
  visual?: Visual | null;
}

export interface Doc {
  title: string;
  sections: DocSection[];
}

export interface DocResponse {
  intent: string;
  type: "doc";
  artifact_id: string;
  version_id: string;
  version_number: number;
  content: Doc;
}

export interface MindNode {
  id: string;
  label: string;
  detail: string;
  parent_id: string | null;
  provenance: "source" | "supplementary";
  citations: Citation[];
  visual?: Visual | null;
}

export interface MindMap {
  title: string;
  nodes: MindNode[];
}

export interface MindMapResponse {
  intent: string;
  type: "mindmap";
  artifact_id: string;
  version_id: string;
  version_number: number;
  content: MindMap;
}

export interface VersionMeta {
  version_id: string;
  version_number: number;
  parent_version_id: string | null;
  caused_by: string;
  slide_count: number;
}

export interface ArtifactDetail {
  artifact_id: string;
  title: string;
  type: string;
  current_version_id: string;
  versions: VersionMeta[];
}

export interface DeckRef {
  artifact_id: string;
  title: string;
  current_version_id: string | null;
}

export interface TurnResponse {
  intent: string;
  reply?: string;
  artifact_id?: string;
  type?: string;
  version_id?: string;
  version_number?: number;
  deck?: Deck;
  // answer and clarify turns: one entry per [n] marker in reply. null means
  // the cited id did not resolve to a chunk.
  citations?: (Citation | null)[];
  uses_general_knowledge?: boolean;
}

export interface ChatMessage {
  id: string;
  role: "learner" | "system";
  text: string;
  artifactId?: string | null;
  citations?: (Citation | null)[];
  usesGeneralKnowledge?: boolean;
}

export interface OutlineTopic {
  topic: string;
  summary?: string;
  prerequisites?: string[];
  chunk_ids?: string[];
}

export interface QuizQuestion {
  id: string;
  kind: "mcq" | "open";
  stem: string;
  options: string[];
  answer: string;
  explanation: string;
  provenance: "source" | "supplementary";
  citations: Citation[];
  visual?: Visual | null;
}

export interface Quiz {
  title: string;
  questions: QuizQuestion[];
}

export interface Grade {
  question_id: string;
  verdict: "right" | "partial" | "wrong" | "ungraded";
  feedback: string;
  provenance: "source" | "supplementary";
  citations: Citation[];
  misconception: string;
}

export interface QuizResult {
  artifact_id: string;
  version_id: string;
  score: number;
  total: number;
  grades: Grade[];
}

export interface CreateQuizResponse {
  type: "quiz";
  artifact_id: string;
  version_id: string;
  version_number: number;
  content: Quiz;
}

export interface Outline {
  topics: OutlineTopic[];
  coverage?: Record<string, unknown>;
}
