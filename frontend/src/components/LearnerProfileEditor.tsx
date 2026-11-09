import { useEffect, useRef, useState } from "react";
import { useStore } from "../store/useStore";
import { LearnerProfileForm } from "./LearnerProfileForm";
import { Button } from "./ui/Button";

function ProfileDialog({ onClose }: { onClose: () => void }) {
  const dialog = useRef<HTMLDialogElement>(null);
  const profile = useStore((s) => s.learnerProfile);
  const loaded = useStore((s) => s.profileLoaded);
  const loading = useStore((s) => s.profileLoading);
  const saving = useStore((s) => s.profileSaving);
  const busy = useStore((s) => s.busy);
  const error = useStore((s) => s.profileError);
  const loadProfile = useStore((s) => s.loadProfile);
  const saveProfile = useStore((s) => s.saveProfile);

  useEffect(() => {
    const element = dialog.current!;
    element.showModal();
    return () => element.close();
  }, []);

  const close = () => {
    dialog.current?.close();
    onClose();
  };

  return (
    <dialog ref={dialog} aria-labelledby="learner-profile-title" aria-describedby="learner-profile-description"
      onCancel={(event) => { event.preventDefault(); if (!saving) close(); }}
      className="m-auto max-h-[90vh] w-[calc(100%-2rem)] max-w-lg overflow-y-auto rounded-2xl border border-line bg-paper p-6 text-ink shadow-xl backdrop:bg-black/30">
      <h2 id="learner-profile-title" className="text-lg font-semibold">Learner profile</h2>
      <p id="learner-profile-description" className="mb-5 mt-2 text-sm text-ink/60">
        Changes apply to future lessons. Your saved lessons and learning history stay available.
      </p>
      {loaded ? (
        <LearnerProfileForm initialProfile={profile} submitLabel="Save profile" disabled={saving || busy} error={error}
          onCancel={close} onSubmit={async (values) => { if (await saveProfile(values)) close(); }} />
      ) : (
        <div>
          {loading ? <p role="status">Loading your profile…</p> : <p role="alert" className="text-sm text-red-700">{error || "Your profile has not loaded yet."}</p>}
          <div className="mt-4 flex justify-end gap-2">
            <Button variant="ghost" onClick={close}>Cancel</Button>
            <Button disabled={loading} onClick={() => void loadProfile()}>Retry loading</Button>
          </div>
        </div>
      )}
    </dialog>
  );
}

export function LearnerProfileEditor() {
  const [open, setOpen] = useState(false);
  const trigger = useRef<HTMLButtonElement | null>(null);
  const busy = useStore((s) => s.busy);
  const saving = useStore((s) => s.profileSaving);
  const courseId = useStore((s) => s.courseId);
  return (
    <>
      <Button variant="ghost" disabled={busy || saving} onClick={(event) => {
        trigger.current = event.currentTarget;
        setOpen(true);
      }}>Learner profile</Button>
      {open && <ProfileDialog key={courseId} onClose={() => {
        setOpen(false);
        trigger.current?.focus();
      }} />}
    </>
  );
}
