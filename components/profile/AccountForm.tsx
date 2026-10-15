"use client";

import { useState, type FormEvent } from "react";

import { Button } from "@/components/ui/button";
import { Card, CardHeader } from "@/components/ui/card";
import { TextField } from "@/components/ui/field";
import type { SaveResult } from "@/hooks/profile/use-profile";
import type { Profile } from "@/lib/types";
import { Notice, type NoticeState } from "./Notice";

/** Name and phone: the part of every profile, whatever the role. */
export function AccountForm({
  account,
  saving,
  onSave,
}: {
  account: Profile["account"];
  saving: boolean;
  onSave: (values: { full_name: string; phone: string }) => Promise<SaveResult>;
}) {
  const [fullName, setFullName] = useState(account.full_name);
  const [phone, setPhone] = useState(account.phone);
  const [notice, setNotice] = useState<NoticeState>(null);
  const [errors, setErrors] = useState<{ fullName?: string; phone?: string }>({});

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const next: typeof errors = {};
    if (fullName.trim().length < 2) next.fullName = "Enter your full name.";
    if (phone.replace(/\D/g, "").length < 7) next.phone = "Enter a phone number with at least 7 digits.";
    setErrors(next);
    if (Object.keys(next).length) return;
    const result = await onSave({ full_name: fullName, phone });
    setNotice(result.ok ? { tone: "success", text: "Your account details were saved." } : { tone: "error", text: result.message });
  }

  return (
    <Card aria-labelledby="account-title">
      <CardHeader title={<span id="account-title">Account</span>} description="How you appear to doctors and patients, and how they can reach you." />
      <form className="grid gap-4 sm:grid-cols-2" onSubmit={submit} noValidate>
        <TextField label="Full name" value={fullName} onChange={(e) => setFullName(e.target.value)} error={errors.fullName} autoComplete="name" wrapperClassName="sm:col-span-2" />
        <TextField label="Email" value={account.email} readOnly hint="Your sign-in email cannot be changed here." />
        <TextField label="Phone" type="tel" value={phone} onChange={(e) => setPhone(e.target.value)} error={errors.phone} autoComplete="tel" placeholder="03XX XXXXXXX" />
        <div className="sm:col-span-2">
          <Notice state={notice} />
          <div className="mt-3 flex justify-end">
            <Button type="submit" variant="secondary" loading={saving}>
              {saving ? "Saving..." : "Save account"}
            </Button>
          </div>
        </div>
      </form>
    </Card>
  );
}
