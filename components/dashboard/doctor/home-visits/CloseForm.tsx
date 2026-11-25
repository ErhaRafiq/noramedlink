"use client";

import { useState, type FormEvent } from "react";

import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { TextAreaField } from "@/components/ui/field";
import type { HomeVisitSummary } from "@/lib/types";

/** The visit summary that closes a home visit: what was found, the advice given and the follow-up. */
export function CloseForm({ busy, onClose }: { busy: boolean; onClose: (summary: HomeVisitSummary) => Promise<string | null> }) {
  const [findings, setFindings] = useState("");
  const [advice, setAdvice] = useState("");
  const [followUp, setFollowUp] = useState("");
  const [error, setError] = useState("");
  const [shown, setShown] = useState(false);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (busy) return;
    setShown(true);
    if (findings.trim().length < 3 || advice.trim().length < 3 || followUp.trim().length < 2) return;
    setError((await onClose({ findings: findings.trim(), advice: advice.trim(), follow_up: followUp.trim() })) ?? "");
  }

  return (
    <form className="mt-3 space-y-3" onSubmit={submit} noValidate aria-label="Visit summary">
      <p className="text-xs text-ink-muted">
        The summary is saved with the visit and the patient sees it. Write &quot;None needed&quot; where nothing applies.
      </p>
      <TextAreaField label="What you found" rows={2} maxLength={2000} value={findings} onChange={(e) => setFindings(e.target.value)} error={shown && findings.trim().length < 3 ? "Write what you found." : ""} />
      <TextAreaField label="Advice given" rows={2} maxLength={2000} value={advice} onChange={(e) => setAdvice(e.target.value)} error={shown && advice.trim().length < 3 ? "Write the advice you gave." : ""} />
      <TextAreaField label="Follow-up" rows={2} maxLength={1000} value={followUp} onChange={(e) => setFollowUp(e.target.value)} error={shown && followUp.trim().length < 2 ? "Write the follow-up, or None needed." : ""} />
      {error ? <Alert tone="error">{error}</Alert> : null}
      <Button type="submit" size="sm" loading={busy}>
        {busy ? "Saving..." : "Save summary and close"}
      </Button>
    </form>
  );
}
