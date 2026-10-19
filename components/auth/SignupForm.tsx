"use client";

import { useRouter, useSearchParams } from "next/navigation";
import { useState, type ChangeEvent, type FormEvent } from "react";
import { UserPlus } from "lucide-react";

import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { SelectField, TextField } from "@/components/ui/field";
import { api } from "@/lib/api";
import { dashboardPathForRole, saveSession } from "@/lib/auth";
import { PMDC_EXAMPLE } from "@/lib/pmdc";
import { buildSignupPayload, EMPTY_SIGNUP, MIN_PASSWORD_LENGTH, parseRole, validateSignup, type SignupValues } from "@/lib/signup";
import type { UserRole } from "@/lib/types";
import { RoleSelector } from "./RoleSelector";

type Errors = Partial<Record<keyof SignupValues, string>>;

export function SignupForm() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const [values, setValues] = useState<SignupValues>(() => ({ ...EMPTY_SIGNUP, role: parseRole(searchParams.get("role")) }));
  const [errors, setErrors] = useState<Errors>({});
  const [formError, setFormError] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);

  function field(name: keyof SignupValues) {
    return {
      value: values[name],
      error: errors[name],
      onChange: (event: ChangeEvent<HTMLInputElement | HTMLSelectElement>) => {
        setValues((current) => ({ ...current, [name]: event.target.value }));
        if (errors[name]) setErrors((current) => ({ ...current, [name]: undefined }));
      },
    };
  }

  function selectRole(role: UserRole) {
    setValues((current) => ({ ...current, role }));
    setErrors({});
    setFormError("");
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (isSubmitting) return;
    setFormError("");
    const found = validateSignup(values);
    setErrors(found);
    if (Object.keys(found).length > 0) {
      setFormError("Please fix the highlighted fields.");
      return;
    }

    setIsSubmitting(true);
    try {
      const auth = await api.signupAccount(buildSignupPayload(values));
      saveSession(auth);
      router.push(dashboardPathForRole(auth.user.role));
    } catch (err) {
      setFormError(err instanceof Error ? err.message : "Sign up failed. Please try again.");
      setIsSubmitting(false);
    }
  }

  return (
    <form className="space-y-6" onSubmit={handleSubmit} noValidate>
      <RoleSelector value={values.role} onChange={selectRole} />

      <div className="grid gap-5 sm:grid-cols-2">
        <TextField label="Full name" autoComplete="name" wrapperClassName="sm:col-span-2" {...field("full_name")} />
        <TextField label="Email" type="email" autoComplete="email" {...field("email")} />
        <TextField label="Phone number" type="tel" autoComplete="tel" placeholder="03XX XXXXXXX" {...field("phone")} />
        <TextField
          label="Password"
          type="password"
          autoComplete="new-password"
          hint={`At least ${MIN_PASSWORD_LENGTH} characters.`}
          {...field("password")}
        />
        <TextField label="Confirm password" type="password" autoComplete="new-password" {...field("confirm_password")} />

        {values.role === "patient" ? (
          <>
            <TextField label="CNIC number" placeholder="12345-1234567-1" inputMode="numeric" {...field("cnic")} />
            <TextField label="Date of birth" type="date" {...field("date_of_birth")} />
            <SelectField label="Gender" {...field("gender")}>
              <option value="">Select</option>
              <option value="female">Female</option>
              <option value="male">Male</option>
              <option value="other">Other</option>
            </SelectField>
          </>
        ) : null}

        {values.role === "doctor" ? (
          <>
            <TextField
              label="PMDC/PMC registration number"
              placeholder={PMDC_EXAMPLE}
              autoCapitalize="characters"
              hint={`As printed on your PMDC certificate, for example ${PMDC_EXAMPLE} or 1815-AJK. An administrator checks it on the PMDC register.`}
              {...field("pmdc_number")}
            />
            <TextField label="Specialization" placeholder="e.g. Cardiology" {...field("specialization")} />
            <TextField label="Hospital or clinic" wrapperClassName="sm:col-span-2" {...field("hospital_name")} />
          </>
        ) : null}

        {values.role === "admin" ? (
          <TextField label="Admin invite code" type="password" autoComplete="off" wrapperClassName="sm:col-span-2" {...field("admin_invite_code")} />
        ) : null}
      </div>

      {values.role === "doctor" ? (
        <Alert tone="info">An administrator checks your registration before patients can find or book you.</Alert>
      ) : null}
      {formError ? <Alert tone="error">{formError}</Alert> : null}

      <Button type="submit" size="lg" loading={isSubmitting} icon={<UserPlus className="h-4 w-4" />} className="w-full">
        {isSubmitting ? "Creating your account..." : "Create account"}
      </Button>
    </form>
  );
}
