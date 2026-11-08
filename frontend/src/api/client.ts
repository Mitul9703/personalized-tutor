import type {
  ArtifactDetail,
  Deck,
  DeckRef,
  FlashcardResponse,
  Outline,
  TurnResponse,
} from "./types";

const BASE = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";
const JSON_HEADERS = { "content-type": "application/json" };

async function unwrap<T>(res: Response): Promise<T> {
  if (!res.ok) {
    const detail = await res.text();
    throw new Error(detail || `request failed: ${res.status}`);
  }
  return res.json() as Promise<T>;
}

export const api = {
  createCourse: (title: string) =>
    fetch(`${BASE}/courses`, {
      method: "POST",
      headers: JSON_HEADERS,
      body: JSON.stringify({ title }),
    }).then(unwrap<{ course_id: string; title: string }>),

  uploadDocument: (courseId: string, file: File) => {
    const form = new FormData();
    form.append("file", file);
    return fetch(`${BASE}/courses/${courseId}/documents`, {
      method: "POST",
      body: form,
    }).then(unwrap<{ document_id: string; status: string; chunks: number }>);
  },

  survey: (courseId: string) =>
    fetch(`${BASE}/courses/${courseId}/survey`, { method: "POST" }).then(
      unwrap<Outline>
    ),

  getOutline: (courseId: string) =>
    fetch(`${BASE}/courses/${courseId}/outline`).then(unwrap<Outline>),

  listMessages: (courseId: string) =>
    fetch(`${BASE}/courses/${courseId}/messages`).then(
      unwrap<Array<{ id: string; role: "learner" | "system"; text: string; artifact_id: string | null }>>
    ),

  listArtifacts: (courseId: string) =>
    fetch(`${BASE}/courses/${courseId}/artifacts`).then(unwrap<DeckRef[]>),

  sendMessage: (courseId: string, text: string, artifactId?: string | null) =>
    fetch(`${BASE}/courses/${courseId}/messages`, {
      method: "POST",
      headers: JSON_HEADERS,
      body: JSON.stringify({ text, artifact_id: artifactId ?? null }),
    }).then(unwrap<TurnResponse>),

  createFlashcards: (courseId: string, topic: string) =>
    fetch(`${BASE}/courses/${courseId}/flashcards`, {
      method: "POST",
      headers: JSON_HEADERS,
      body: JSON.stringify({ topic }),
    }).then(unwrap<FlashcardResponse>),

  editFlashcards: (artifactId: string, instruction: string) =>
    fetch(`${BASE}/artifacts/${artifactId}/flashcards/edit`, {
      method: "POST",
      headers: JSON_HEADERS,
      body: JSON.stringify({ instruction }),
    }).then(unwrap<FlashcardResponse>),

  getChunk: (chunkId: string) =>
    fetch(`${BASE}/chunks/${chunkId}`).then(
      unwrap<{ chunk_id: string; text: string; location: Record<string, unknown> }>
    ),

  getArtifact: (artifactId: string) =>
    fetch(`${BASE}/artifacts/${artifactId}`).then(unwrap<ArtifactDetail>),

  getVersion: (artifactId: string, versionId: string) =>
    fetch(`${BASE}/artifacts/${artifactId}/versions/${versionId}`).then(
      unwrap<{ deck: Deck; version_number: number }>
    ),

  revert: (artifactId: string, versionId: string) =>
    fetch(`${BASE}/artifacts/${artifactId}/revert/${versionId}`, {
      method: "POST",
    }).then(unwrap<{ artifact_id: string; version_id: string; version_number: number; deck: Deck }>),
};
