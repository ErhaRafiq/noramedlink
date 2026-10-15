"use client";

import { useState, type FormEvent } from "react";

import { Alert } from "@/components/ui/alert";
import { Badge, type BadgeTone } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardHeader } from "@/components/ui/card";
import { TextAreaField, TextField } from "@/components/ui/field";
import type { SaveResult } from "@/hooks/profile/use-profile";
import { cn } from "@/lib/cn";
import type { ConsultationMode, DoctorProfile, DoctorProfileInput } from "@/lib/types";
import { Notice, type NoticeState } from "./Notice";

export const MODES: Array<{ value: ConsultationMode; label: string; hint: string }> = [
  { value: "in_clinic", label: "In clinic", hint: "Patients visit you" },
  { value: "online", label: "Online", hint: "Video or phone consultation" },
  { value: "home", label: "Home visit", hint: "Non-emergency visits at the patient's home" },
];

const STATUS: Record<string, { label: string; tone: BadgeTone }> = {
  approved: { label: "Verified", tone: "success" },
  verified: { label: "Verified", tone: "success" },
  pending: { label: "Verification pending", tone: "warning" },
  rejected: { label: "Verification rejected", tone: "danger" },
};

/** A doctor's public profile and fee. Specialization and the PMDC number were verified by an admin and are read-only. */
export function DoctorForm({
  doctor,
  saving,
  onSave,
}: {
  doctor: DoctorProfile;
  saving: boolean;
  onSave: (values: DoctorProfileInput) => Promise<SaveResult>;
}) {
  const [hospital, setHospital] = useState(doctor.hospital_name);
  const [city, setCity] = useState(doctor.city ?? "");
  const [qualifications, setQualifications] = useState(doctor.qualifications ?? "");
  const [experience, setExperience] = useState(doctor.experience_years === null ? "" : String(doctor.experience_years));
  const [languages, setLanguages] = useState(doctor.languages.join(", "));
  const [modes, setModes] = useState<ConsultationMode[]>(doctor.consultation_modes);
  const [fee, setFee] = useState(doctor.consultation_fee === null ? "" : String(doctor.consultation_fee));
  const [bio, setBio] = useState(doctor.bio ?? "");
  const [errors, setErrors] = useState<{ hospital?: string; experience?: string; fee?: string; modes?: string }>({});
  const [notice, setNotice] = useState<NoticeState>(null);
  const status = STATUS[doctor.verification_status.toLowerCase()] ?? { label: doctor.verification_status, tone: "neutral" as const };

  function toggleMode(mode: ConsultationMode) {
    setModes((current) => (current.includes(mode) ? current.filter((m) => m !== mode) : [...current, mode]));
  }

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const next: typeof errors = {};
    const years = experience.trim() === "" ? null : Number(experience);
    const price = fee.trim() === "" ? null : Number(fee);
    if (hospital.trim().length < 2) next.hospital = "Enter the hospital or clinic you practise at.";
    if (years !== null && (!Number.isInteger(years) || years < 0 || years > 70)) next.experience = "Enter whole years, from 0 to 70.";
    if (price !== null && (!Number.isInteger(price) || price < 200 || price > 100_000)) next.fee = "Enter a whole amount from PKR 200 to PKR 100,000, or leave it empty.";
    if (modes.length === 0) next.modes = "Choose at least one way you consult.";
    setErrors(next);
    if (Object.keys(next).length) return;
    const result = await onSave({
      hospital_name: hospital,
      city: city || null,
      qualifications: qualifications || null,
      experience_years: years,
      bio: bio || null,
      languages: languages.split(",").map((l) => l.trim()).filter(Boolean),
      consultation_modes: modes,
      consultation_fee: price,
    });
    setNotice(result.ok ? { tone: "success", text: "Your doctor profile was saved." } : { tone: "error", text: result.message });
  }

  return (
    <Card aria-labelledby="doctor-title">
      <CardHeader
        title={<span id="doctor-title">Doctor profile</span>}
        description="What patients see when they search for a doctor."
        action={<Badge tone={status.tone}>{status.label}</Badge>}
      />
      {doctor.verification_status.toLowerCase() === "pending" ? (
        <Alert tone="warning" className="mb-4">
          Patients cannot find or book you until an administrator approves your registration.
        </Alert>
      ) : null}
      <form className="grid gap-4 sm:grid-cols-2" onSubmit={submit} noValidate>
        <TextField label="Specialization" value={doctor.specialization} readOnly hint="Verified by an administrator." />
        <TextField label="PMDC / PMC number" value={doctor.pmdc_number} readOnly hint="Verified by an administrator." />
        <TextField label="Hospital or clinic" value={hospital} onChange={(e) => setHospital(e.target.value)} error={errors.hospital} />
        <TextField label="City" value={city} onChange={(e) => setCity(e.target.value)} />
        <TextAreaField label="Qualifications" rows={2} value={qualifications} onChange={(e) => setQualifications(e.target.value)} hint="For example: MBBS, FCPS (Cardiology)" wrapperClassName="sm:col-span-2" />
        <TextField label="Years of experience" type="number" inputMode="numeric" min={0} max={70} value={experience} onChange={(e) => setExperience(e.target.value)} error={errors.experience} />
        <TextField label="Languages" value={languages} onChange={(e) => setLanguages(e.target.value)} hint="Separate with commas: Urdu, English" />
        <TextField label="Consultation fee (PKR)" type="number" inputMode="numeric" min={200} max={100000} value={fee} onChange={(e) => setFee(e.target.value)} error={errors.fee} hint="Patients pay this online by card. Empty: they cannot pay online yet." />
        <fieldset className="sm:col-span-2">
          <legend className="text-sm font-medium text-slate-700">How you consult</legend>
          <div className="mt-1.5 grid gap-2 sm:grid-cols-3">
            {MODES.map((mode) => {
              const selected = modes.includes(mode.value);
              return (
                <label
                  key={mode.value}
                  className={cn(
                    "flex cursor-pointer items-start gap-3 rounded-control border p-3 text-sm transition-colors has-[:focus-visible]:ring-2 has-[:focus-visible]:ring-brand-blue",
                    selected ? "border-brand-blue bg-blue-50/60" : "border-line bg-white hover:border-line-strong",
                  )}
                >
                  <input type="checkbox" checked={selected} onChange={() => toggleMode(mode.value)} className="mt-1 h-4 w-4 accent-brand-blue" />
                  <span>
                    <span className="block font-semibold text-ink">{mode.label}</span>
                    <span className="block text-xs text-ink-muted">{mode.hint}</span>
                  </span>
                </label>
              );
            })}
          </div>
          {errors.modes ? <p className="mt-1.5 text-xs font-medium text-rose-600">{errors.modes}</p> : null}
        </fieldset>
        <TextAreaField label="About you" rows={4} value={bio} onChange={(e) => setBio(e.target.value)} hint="A few sentences patients can read before booking." wrapperClassName="sm:col-span-2" />
        <div className="sm:col-span-2">
          <Notice state={notice} />
          <div className="mt-3 flex justify-end">
            <Button type="submit" loading={saving}>
              {saving ? "Saving..." : "Save doctor profile"}
            </Button>
          </div>
        </div>
      </form>
    </Card>
  );
}
