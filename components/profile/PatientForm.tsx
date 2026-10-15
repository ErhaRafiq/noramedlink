"use client";

import { useState, type FormEvent } from "react";

import { Button } from "@/components/ui/button";
import { Card, CardHeader } from "@/components/ui/card";
import { SelectField, TextField } from "@/components/ui/field";
import type { SaveResult } from "@/hooks/profile/use-profile";
import type { PatientProfile, PatientProfileInput } from "@/lib/types";
import { Notice, type NoticeState } from "./Notice";

const GENDERS = ["Male", "Female", "Other"];
const BLOOD_GROUPS = ["A+", "A-", "B+", "B-", "AB+", "AB-", "O+", "O-"];

/** A patient's own details: age and gender, where to reach them, and who to call in an emergency. */
export function PatientForm({
  patient,
  saving,
  onSave,
}: {
  patient: PatientProfile;
  saving: boolean;
  onSave: (values: PatientProfileInput) => Promise<SaveResult>;
}) {
  const [birthDate, setBirthDate] = useState(patient.date_of_birth);
  const [gender, setGender] = useState(patient.gender);
  const [bloodGroup, setBloodGroup] = useState(patient.blood_group ?? "");
  const [city, setCity] = useState(patient.city ?? "");
  const [address, setAddress] = useState(patient.address ?? "");
  const [contactName, setContactName] = useState(patient.emergency_contact_name ?? "");
  const [contactPhone, setContactPhone] = useState(patient.emergency_contact_phone ?? "");
  const [errors, setErrors] = useState<{ birthDate?: string; contactPhone?: string }>({});
  const [notice, setNotice] = useState<NoticeState>(null);
  const today = new Date().toISOString().slice(0, 10);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const next: typeof errors = {};
    if (!birthDate || birthDate > today) next.birthDate = "Enter a date of birth that is not in the future.";
    if (contactPhone.trim() && contactPhone.replace(/\D/g, "").length < 7) next.contactPhone = "Enter a phone number with at least 7 digits.";
    setErrors(next);
    if (Object.keys(next).length) return;
    const result = await onSave({
      date_of_birth: birthDate,
      gender,
      city: city || null,
      address: address || null,
      blood_group: bloodGroup || null,
      emergency_contact_name: contactName || null,
      emergency_contact_phone: contactPhone || null,
    });
    setNotice(result.ok ? { tone: "success", text: "Your details were saved." } : { tone: "error", text: result.message });
  }

  return (
    <Card aria-labelledby="patient-title">
      <CardHeader
        title={<span id="patient-title">Personal details</span>}
        description={`Age ${patient.age}. Your CNIC (${patient.cnic_masked}) was recorded at sign-up and is never shown in full.`}
      />
      <form className="grid gap-4 sm:grid-cols-2" onSubmit={submit} noValidate>
        <TextField label="Date of birth" type="date" max={today} value={birthDate} onChange={(e) => setBirthDate(e.target.value)} error={errors.birthDate} />
        <SelectField label="Gender" value={gender} onChange={(e) => setGender(e.target.value)}>
          {GENDERS.map((option) => (
            <option key={option} value={option}>
              {option}
            </option>
          ))}
        </SelectField>
        <SelectField label="Blood group" value={bloodGroup} onChange={(e) => setBloodGroup(e.target.value)} hint="Optional. Helpful in an emergency.">
          <option value="">Not recorded</option>
          {BLOOD_GROUPS.map((option) => (
            <option key={option} value={option}>
              {option}
            </option>
          ))}
        </SelectField>
        <TextField label="City" value={city} onChange={(e) => setCity(e.target.value)} autoComplete="address-level2" />
        <TextField label="Address" value={address} onChange={(e) => setAddress(e.target.value)} autoComplete="street-address" wrapperClassName="sm:col-span-2" />
        <TextField label="Emergency contact name" value={contactName} onChange={(e) => setContactName(e.target.value)} />
        <TextField label="Emergency contact phone" type="tel" value={contactPhone} onChange={(e) => setContactPhone(e.target.value)} error={errors.contactPhone} placeholder="03XX XXXXXXX" />
        <div className="sm:col-span-2">
          <Notice state={notice} />
          <div className="mt-3 flex justify-end">
            <Button type="submit" loading={saving}>
              {saving ? "Saving..." : "Save details"}
            </Button>
          </div>
        </div>
      </form>
    </Card>
  );
}
