import { useEffect, useState } from "react";
import { CheckCircle2, CircleDashed, Loader2, Sparkles, XCircle } from "lucide-react";
import type { Grade, Quiz, QuizResult } from "../api/types";
import { api } from "../api/client";
import { CitationBadge } from "./CitationBadge";
import { Button } from "./ui/Button";
import { cn } from "../lib/cn";

const VERDICT = {
  right: { label: "Right", icon: CheckCircle2, cls: "border-emerald-200 bg-emerald-50 text-emerald-800" },
  partial: { label: "Partly right", icon: CircleDashed, cls: "border-amber-200 bg-amber-50 text-amber-800" },
  wrong: { label: "Not quite", icon: XCircle, cls: "border-red-200 bg-red-50 text-red-800" },
  ungraded: { label: "Not graded", icon: CircleDashed, cls: "border-line bg-panel text-ink/60" },
} as const;

export function QuizView({ quiz, artifactId, versionId }: {
  quiz: Quiz;
  artifactId: string;
  versionId: string | null;
}) {
  const [answers, setAnswers] = useState<Record<string, string>>({});
  const [result, setResult] = useState<QuizResult | null>(null);
  const [grading, setGrading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // a different quiz or version starts a fresh attempt
  useEffect(() => {
    setAnswers({});
    setResult(null);
    setError(null);
  }, [artifactId, versionId]);

  const grades: Record<string, Grade> = {};
  result?.grades.forEach((g) => (grades[g.question_id] = g));

  const submit = async () => {
    setGrading(true);
    setError(null);
    try {
      setResult(await api.submitQuiz(artifactId, answers, versionId));
    } catch (e) {
      setError(String(e));
    } finally {
      setGrading(false);
    }
  };

  return (
    <div className="h-full overflow-y-auto p-6">
      <div className="mx-auto max-w-3xl space-y-4">
        {result && (
          <div className="rounded-2xl border border-brand/30 bg-brandsoft px-5 py-4">
            <div className="text-sm font-semibold text-brand">
              You scored {result.score} of {result.total}
            </div>
            <div className="mt-1 text-xs text-ink/60">
              Feedback for each question is below, with the source it comes from.
            </div>
          </div>
        )}

        {quiz.questions.map((q, i) => {
          const grade = grades[q.id];
          const v = grade ? VERDICT[grade.verdict] : null;
          return (
            <div key={q.id} className="rounded-2xl border border-line bg-panel p-5 shadow-sm">
              <div className="mb-1 flex items-center justify-between text-xs text-ink/40">
                <span>Question {i + 1} of {quiz.questions.length}</span>
                {q.provenance === "supplementary" ? (
                  <span className="inline-flex items-center gap-1 rounded-full bg-amber-50 px-2 py-0.5 font-medium text-amber-700">
                    <Sparkles className="h-3 w-3" />
                    beyond your materials
                  </span>
                ) : (
                  <span className="text-emerald-600">from your materials</span>
                )}
              </div>
              <div className="mt-1 text-[15px] font-medium leading-relaxed">{q.stem}</div>

              {q.kind === "mcq" ? (
                <div className="mt-3 space-y-2">
                  {q.options.map((opt) => (
                    <label
                      key={opt}
                      className={cn(
                        "flex cursor-pointer items-start gap-2 rounded-lg border px-3 py-2 text-sm transition",
                        answers[q.id] === opt ? "border-brand bg-brandsoft" : "border-line hover:border-brand/40",
                        result && "pointer-events-none"
                      )}
                    >
                      <input
                        type="radio"
                        name={q.id}
                        className="mt-1"
                        checked={answers[q.id] === opt}
                        onChange={() => setAnswers((a) => ({ ...a, [q.id]: opt }))}
                      />
                      <span>{opt}</span>
                    </label>
                  ))}
                </div>
              ) : (
                <textarea
                  value={answers[q.id] ?? ""}
                  disabled={!!result}
                  onChange={(e) => setAnswers((a) => ({ ...a, [q.id]: e.target.value }))}
                  rows={3}
                  placeholder="Type your answer"
                  className="mt-3 w-full resize-y rounded-lg border border-line bg-paper px-3 py-2 text-sm outline-none focus:border-brand/50"
                />
              )}

              {grade && v && (
                <div className={cn("mt-4 rounded-xl border px-4 py-3 text-sm", v.cls)}>
                  <div className="mb-1 flex items-center gap-1.5 font-semibold">
                    <v.icon className="h-4 w-4" />
                    {v.label}
                  </div>
                  <div className="leading-relaxed">{grade.feedback}</div>
                  {grade.verdict !== "right" && (
                    <div className="mt-2 text-xs opacity-80">Correct answer: {q.answer}</div>
                  )}
                  <div className="mt-2 flex flex-wrap items-center gap-1.5">
                    {grade.citations.length > 0 ? (
                      grade.citations.map((c, j) => <CitationBadge key={j} citation={c} />)
                    ) : grade.provenance === "supplementary" ? (
                      <span className="text-[11px] opacity-70">general knowledge, not from your files</span>
                    ) : null}
                  </div>
                </div>
              )}
            </div>
          );
        })}

        {error && <div className="rounded-lg bg-red-50 px-3 py-2 text-xs text-red-700">{error}</div>}

        <div className="flex justify-end gap-2 pb-4">
          {result ? (
            <Button variant="soft" onClick={() => { setAnswers({}); setResult(null); }}>
              Try again
            </Button>
          ) : (
            <Button onClick={submit} disabled={grading || Object.keys(answers).length === 0}>
              {grading && <Loader2 className="h-4 w-4 animate-spin" />}
              {grading ? "Grading…" : "Submit answers"}
            </Button>
          )}
        </div>
      </div>
    </div>
  );
}
