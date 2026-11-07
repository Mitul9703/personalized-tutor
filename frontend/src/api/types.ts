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
}

export interface ChatMessage {
  id: string;
  role: "learner" | "system";
  text: string;
  artifactId?: string | null;
}

export interface OutlineTopic {
  topic: string;
  summary?: string;
  prerequisites?: string[];
  chunk_ids?: string[];
}

export interface Outline {
  topics: OutlineTopic[];
  coverage?: Record<string, unknown>;
}
