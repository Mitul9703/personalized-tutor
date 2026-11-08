import { useRef, useState } from "react";
import { motion } from "framer-motion";
import { UploadCloud, Loader2, GraduationCap } from "lucide-react";
import { useStore } from "../store/useStore";
import { cn } from "../lib/cn";
import type { LearnerProfile } from "../api/types";
import { LearnerProfileForm } from "./LearnerProfileForm";
import { Button } from "./ui/Button";

export function UploadScreen() {
  const phase = useStore((s) => s.phase);
  const ingestMsg = useStore((s) => s.ingestMsg);
  const error = useStore((s) => s.error);
  const startFromFile = useStore((s) => s.startFromFile);
  const inputRef = useRef<HTMLInputElement>(null);
  const [drag, setDrag] = useState(false);
  const [profile, setProfile] = useState<LearnerProfile | null>(null);
  const [editing, setEditing] = useState(true);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);

  if (phase === "ingesting") {
    return (
      <div className="h-full grid place-items-center">
        <div className="flex flex-col items-center gap-4 text-center">
          <Loader2 className="h-8 w-8 animate-spin text-brand" />
          <p className="text-ink/70">{ingestMsg}</p>
          <p className="text-xs text-ink/40">This runs once per upload and can take a moment.</p>
        </div>
      </div>
    );
  }

  const pick = (f?: File | null) => {
    if (f && profile && !editing) {
      setSelectedFile(f);
      void startFromFile(f, profile);
    }
  };

  return (
    <div className="h-full overflow-y-auto grid place-items-center p-6">
      <motion.div
        initial={{ opacity: 0, y: 8 }}
        animate={{ opacity: 1, y: 0 }}
        className="w-full max-w-lg text-center"
      >
        <div className="mb-6 inline-flex h-12 w-12 items-center justify-center rounded-xl bg-brandsoft text-brand">
          <GraduationCap className="h-6 w-6" />
        </div>
        <h1 className="text-2xl font-semibold">Personalized Tutor</h1>
        <p className="mt-2 text-ink/60">
          Tell me a little about yourself so I can tailor lessons from your class material.
        </p>

        {editing ? (
          <div className="mt-6 rounded-2xl border border-line bg-panel p-5">
            <LearnerProfileForm initialProfile={profile} submitLabel="Continue to upload"
              onSubmit={(values) => { setProfile(values); setEditing(false); }} />
          </div>
        ) : (
          <>
            <div className="mt-5 flex items-center justify-between gap-3 rounded-xl border border-line bg-panel p-3 text-left text-sm">
              <div className="min-w-0">
                <p className="font-medium capitalize">{profile!.level}</p>
                <p className="truncate text-ink/60">{profile!.goal}</p>
              </div>
              <Button variant="ghost" onClick={() => setEditing(true)}>Edit profile</Button>
            </div>
            {selectedFile && error ? (
              <div className="mt-6 space-y-3">
                <p className="text-sm text-ink/60">Continue setting up {selectedFile.name}.</p>
                <Button onClick={() => pick(selectedFile)}>Retry setup</Button>
              </div>
            ) : (
              <label
                onDragOver={(e) => {
                  e.preventDefault();
                  setDrag(true);
                }}
                onDragLeave={() => setDrag(false)}
                onDrop={(e) => {
                  e.preventDefault();
                  setDrag(false);
                  pick(e.dataTransfer.files?.[0]);
                }}
                htmlFor="course-material"
                className={cn(
                  "mt-8 flex cursor-pointer flex-col items-center gap-3 rounded-2xl border-2 border-dashed p-10 transition focus-within:ring-2 focus-within:ring-brand",
                  drag ? "border-brand bg-brandsoft" : "border-line bg-panel hover:border-brand/50"
                )}
              >
                <UploadCloud className={cn("h-8 w-8", drag ? "text-brand" : "text-ink/40")} />
                <div className="text-sm">
                  <span className="font-medium text-brand">Choose a file</span>
                  <span className="text-ink/50"> or drop it here</span>
                </div>
                <div className="text-xs text-ink/40">PDF or text</div>
                <input
                  id="course-material"
                  ref={inputRef}
                  type="file"
                  accept=".pdf,.txt,.md,text/plain,application/pdf"
                  className="sr-only"
                  onChange={(e) => pick(e.target.files?.[0])}
                />
              </label>
            )}
          </>
        )}

        {error && <p role="alert" className="mt-4 text-sm text-red-600">{error}</p>}
      </motion.div>
    </div>
  );
}
