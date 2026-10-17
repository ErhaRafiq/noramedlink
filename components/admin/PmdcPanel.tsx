"use client";

import { useState, type FormEvent } from "react";
import { BadgeCheck, ExternalLink, Gavel, Search } from "lucide-react";

import { Alert } from "@/components/ui/alert";
import { Badge, type BadgeTone } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { TextAreaField } from "@/components/ui/field";
import { Modal } from "@/components/ui/modal";
import { api } from "@/lib/api";
import { formatDateTime } from "@/lib/datetime";
import { PMDC_REGISTER_URL } from "@/lib/pmdc";
import type { PmdcStatus } from "@/lib/types";

function summary(status: PmdcStatus): { label: string; tone: BadgeTone } {
  if (status.verified) return { label: "PMDC verified", tone: "success" };
  if (!status.format_ok) return { label: "Number not recognised", tone: "danger" };
  if (status.outcome === null) return { label: "Not checked yet", tone: "neutral" };
  if (status.outcome === "manual") return { label: "Not verified (by hand)", tone: "warning" };
  return { label: "Not verified", tone: "warning" };
}

/**
 * One doctor's PMDC verification for the administrator: the number, what the PMDC register answered, and the
 * two ways to decide. A check asks the public register (only the number is sent); a decision by hand needs a
 * written reason. Neither blocks approval: a doctor can be approved and active without being PMDC verified.
 */
export function PmdcPanel({ doctorId, initial }: { doctorId: number; initial: PmdcStatus }) {
  const [status, setStatus] = useState(initial);
  const [checking, setChecking] = useState(false);
  const [error, setError] = useState("");
  const [deciding, setDeciding] = useState(false);
  const badge = summary(status);

  async function check() {
    setChecking(true);
    setError("");
    try {
      setStatus(await api.adminCheckPmdc(doctorId));
    } catch (err) {
      setError(err instanceof Error ? err.message : "The PMDC check could not be completed.");
    } finally {
      setChecking(false);
    }
  }

  return (
    <div className="mt-3 rounded-control border border-line bg-surface-soft p-3.5" aria-label="PMDC verification">
      <div className="flex flex-wrap items-center gap-2">
        <BadgeCheck className="h-4 w-4 text-ink-muted" aria-hidden />
        <span className="text-sm font-semibold text-ink">PMDC verification</span>
        <Badge tone={badge.tone}>{badge.label}</Badge>
      </div>

      <dl className="mt-2 space-y-0.5 text-sm">
        <div>
          <dt className="inline text-ink-muted">Number entered: </dt>
          <dd className="inline break-all font-medium text-ink">{status.number || "Not provided"}</dd>
        </div>
        {status.format_ok && status.searchable !== status.number ? (
          <div>
            <dt className="inline text-ink-muted">Searched as: </dt>
            <dd className="inline font-medium text-ink">{status.searchable}</dd>
          </div>
        ) : null}
        {status.register_name ? (
          <div>
            <dt className="inline text-ink-muted">Register lists: </dt>
            <dd className="inline break-words font-medium text-ink">
              {status.register_name}
              {status.register_status ? ` (${status.register_status})` : ""}
            </dd>
          </div>
        ) : null}
      </dl>

      <p className="mt-2 text-xs leading-5 text-ink-muted">
        {status.message}
        {status.checked_at ? ` Last checked ${formatDateTime(status.checked_at)}${status.checked_by_name ? ` by ${status.checked_by_name}` : ""}.` : ""}
      </p>
      {!status.format_ok && !status.verified ? (
        <p className="mt-1 text-xs leading-5 text-rose-700">
          The register searches numbers like 12345-P. Ask the doctor for the number on their certificate, or look them up by name on the PMDC site
          and decide by hand.
        </p>
      ) : null}

      {error ? (
        <Alert tone="error" className="mt-3 text-xs">
          {error}
        </Alert>
      ) : null}

      <div className="mt-3 flex flex-wrap gap-2">
        <Button size="sm" variant="secondary" loading={checking} disabled={checking || !status.format_ok} icon={<Search className="h-4 w-4" />} onClick={() => void check()}>
          {checking ? "Checking..." : status.checked_at ? "Check again" : "Check on PMDC"}
        </Button>
        <Button size="sm" variant="ghost" disabled={checking} icon={<Gavel className="h-4 w-4" />} onClick={() => setDeciding(true)}>
          Decide by hand
        </Button>
        <a
          href={PMDC_REGISTER_URL}
          target="_blank"
          rel="noopener noreferrer"
          className="inline-flex min-h-[36px] items-center gap-1.5 rounded-control px-3 py-1.5 text-xs font-semibold text-brand-blue hover:bg-blue-50"
        >
          Open the PMDC register
          <ExternalLink className="h-3.5 w-3.5" aria-hidden />
          <span className="sr-only">(opens in a new tab)</span>
        </a>
      </div>

      <DecideDialog
        open={deciding}
        initialVerified={!status.verified}
        onClose={() => setDeciding(false)}
        onSave={async (verified, note) => {
          const saved = await api.adminDecidePmdc(doctorId, verified, note);
          setStatus(saved);
        }}
      />
    </div>
  );
}

function DecideDialog({
  open,
  initialVerified,
  onClose,
  onSave,
}: {
  open: boolean;
  initialVerified: boolean;
  onClose: () => void;
  onSave: (verified: boolean, note: string) => Promise<void>;
}) {
  return (
    <Modal open={open} onClose={onClose} title="Decide PMDC verification by hand" description="Use this after checking the doctor on the PMDC site yourself, or when the register's spelling differs.">
      {open ? <DecideForm initialVerified={initialVerified} onClose={onClose} onSave={onSave} /> : null}
    </Modal>
  );
}

function DecideForm({ initialVerified, onClose, onSave }: { initialVerified: boolean; onClose: () => void; onSave: (verified: boolean, note: string) => Promise<void> }) {
  const [verified, setVerified] = useState(initialVerified);
  const [note, setNote] = useState("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const tooShort = note.trim().length < 10;

  async function submit(event: FormEvent) {
    event.preventDefault();
    if (tooShort || saving) return;
    setSaving(true);
    setError("");
    try {
      await onSave(verified, note.trim());
      onClose();
    } catch (err) {
      setError(err instanceof Error ? err.message : "The decision could not be saved.");
      setSaving(false);
    }
  }

  return (
    <form onSubmit={submit} className="space-y-4">
      <fieldset>
        <legend className="text-sm font-medium text-slate-700">Decision</legend>
        <div className="mt-2 space-y-2">
          {[
            { value: true, label: "PMDC verified", hint: "Shows the badge on the doctor's card." },
            { value: false, label: "Not PMDC verified", hint: "Removes the badge. The doctor stays approved." },
          ].map((option) => (
            <label key={String(option.value)} className="flex cursor-pointer items-start gap-3 rounded-control border border-line p-3 has-[:checked]:border-brand-blue has-[:checked]:bg-blue-50/40">
              <input type="radio" name="pmdc-decision" checked={verified === option.value} onChange={() => setVerified(option.value)} className="mt-1 h-4 w-4" />
              <span>
                <span className="block text-sm font-semibold text-ink">{option.label}</span>
                <span className="block text-xs text-ink-muted">{option.hint}</span>
              </span>
            </label>
          ))}
        </div>
      </fieldset>
      <TextAreaField
        label="Reason"
        rows={3}
        value={note}
        maxLength={300}
        onChange={(event) => setNote(event.target.value)}
        hint={tooShort ? "Required: a few words on why, for example: Checked on pmdc.pk, the name is spelled differently." : `${note.trim().length} of 300 characters.`}
      />
      {error ? <Alert tone="error">{error}</Alert> : null}
      <div className="flex flex-col-reverse gap-2 sm:flex-row sm:justify-end">
        <Button type="button" variant="secondary" onClick={onClose} disabled={saving}>
          Cancel
        </Button>
        <Button type="submit" loading={saving} disabled={tooShort}>
          {saving ? "Saving..." : "Save decision"}
        </Button>
      </div>
    </form>
  );
}
