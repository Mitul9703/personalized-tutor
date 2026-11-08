import { useId, useState } from "react";
import type { FormEvent } from "react";
import type { LearnerProfile } from "../api/types";
import { Button } from "./ui/Button";

interface Props {
  initialProfile?: LearnerProfile | null;
  submitLabel: string;
  disabled?: boolean;
  error?: string | null;
  onSubmit: (profile: LearnerProfile) => void | Promise<void>;
  onCancel?: () => void;
}

export function LearnerProfileForm({ initialProfile, submitLabel, disabled, error, onSubmit, onCancel }: Props) {
  const id = useId();
  const [level, setLevel] = useState<LearnerProfile["level"] | "">(initialProfile?.level ?? "");
  const [goal, setGoal] = useState(initialProfile?.goal ?? "");
  const [background, setBackground] = useState(initialProfile?.background ?? "");
  const valid = !!level && !!goal.trim() && !!background.trim();
  const fieldClass = "mt-1 w-full rounded-lg border border-line bg-panel px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand";

  const submit = (event: FormEvent) => {
    event.preventDefault();
    if (!valid || disabled || !level) return;
    void onSubmit({ level, goal: goal.trim(), background: background.trim() });
  };

  return (
    <form onSubmit={submit} className="space-y-4 text-left">
      <fieldset disabled={disabled} className="space-y-4">
        <div>
          <label htmlFor={`${id}-level`} className="text-sm font-medium">How familiar are you with this subject?</label>
          <select id={`${id}-level`} required value={level} onChange={(e) => setLevel(e.target.value as LearnerProfile["level"])} className={fieldClass}>
            <option value="" disabled>Choose your level</option>
            <option value="beginner">Beginner</option>
            <option value="intermediate">Intermediate</option>
            <option value="advanced">Advanced</option>
          </select>
        </div>
        <div>
          <label htmlFor={`${id}-goal`} className="text-sm font-medium">What do you want to achieve?</label>
          <textarea id={`${id}-goal`} required maxLength={1000} rows={2} value={goal} onChange={(e) => setGoal(e.target.value)}
            placeholder="For example, understand the concepts for my exam." className={fieldClass} />
        </div>
        <div>
          <label htmlFor={`${id}-background`} className="text-sm font-medium">What do you already know?</label>
          <textarea id={`${id}-background`} required maxLength={2000} rows={3} value={background} onChange={(e) => setBackground(e.target.value)}
            aria-describedby={`${id}-background-help`} placeholder="For example, basic Python but no machine learning." className={fieldClass} />
          <p id={`${id}-background-help`} className="mt-1 text-xs text-ink/50">New to the subject? Write “No prior experience.”</p>
        </div>
      </fieldset>
      {error && <p role="alert" className="text-sm text-red-700">{error}</p>}
      <div className="flex justify-end gap-2">
        {onCancel && <Button type="button" variant="ghost" disabled={disabled} onClick={onCancel}>Cancel</Button>}
        <Button type="submit" disabled={disabled || !valid}>{disabled ? "Please wait…" : submitLabel}</Button>
      </div>
    </form>
  );
}
