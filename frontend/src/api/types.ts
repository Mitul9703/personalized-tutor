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

export interface Slide {
  id: string;
  heading: string;
  bullets: string[];
  notes?: string;
  provenance: "source" | "supplementary";
  citations: Citation[];
  level?: "intro" | "standard" | "deep";
}

export interface Deck {
  title: string;
  slides: Slide[];
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
