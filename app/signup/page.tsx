"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { ChangeEvent, FormEvent, useState } from "react";

import { NoraLogo } from "@/components/ui/NoraLogo";
import { RoleCard } from "@/components/ui/saas-shell";
import { api } from "@/lib/api";
import { dashboardPathForRole, saveSession } from "@/lib/auth";
import type { SignupOtpPayload, UserRole } from "@/lib/types";

type SignupValues = {
  role: UserRole;
  full_name: string;
  email: string;
  password: string;
  confirm_password: string;
  cnic: string;
  phone: string;
  date_of_birth: string;
  gender: string;
  pmdc_number: string;
  specialization: string;
  hospital_name: string;
  admin_invite_code: string;
};

const roleCards: Array<{ role: UserRole; title: string; description: string }> = [
  {
    role: "patient",
    title: "Patient",
    description: "Upload reports and manage OCR summaries.",
  },
  {
    role: "doctor",
    title: "Doctor",
    description: "Prepare for patient review modules.",
  },
  {
    role: "admin",
    title: "Admin",
    description: "Manage users, doctors, reports, appointments, and system records.",
  },
];

const roleHeadings: Record<UserRole, string> = {
  patient: "Patient account",
  doctor: "Doctor account",
  admin: "Admin account",
};

const initialValues: SignupValues = {
  role: "patient",
  full_name: "",
  email: "",
  password: "",
  confirm_password: "",
  cnic: "",
  phone: "",
  date_of_birth: "",
  gender: "",
  pmdc_number: "",
  specialization: "",
  hospital_name: "",
  admin_invite_code: "",
};

function getInitialValues(): SignupValues {
  if (typeof window === "undefined") {
    return initialValues;
  }

  const requestedRole = new URLSearchParams(window.location.search).get("role");
  if (requestedRole === "doctor" || requestedRole === "patient" || requestedRole === "admin") {
    return { ...initialValues, role: requestedRole };
  }

  return initialValues;
}

export default function SignupPage() {
  const router = useRouter();
  const [values, setValues] = useState<SignupValues>(getInitialValues);
  const [statusMessage, setStatusMessage] = useState("");
  const [successMessage, setSuccessMessage] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);

  function updateField(field: keyof SignupValues) {
    return (event: ChangeEvent<HTMLInputElement | HTMLSelectElement>) => {
      setValues((current) => ({ ...current, [field]: event.target.value }));
      setStatusMessage("");
      setSuccessMessage("");
    };
  }

  function selectRole(role: UserRole) {
    setValues((current) => ({ ...current, role }));
    setStatusMessage("");
    setSuccessMessage("");
  }

  function validate() {
    if (!values.full_name.trim() || !values.email.trim() || !values.phone.trim()) {
      return "Full name, email, and phone number are required.";
    }
    if (values.password.length < 8) {
      return "Password must be at least 8 characters.";
    }
    if (values.password !== values.confirm_password) {
      return "Password and confirm password must match.";
    }
    if (values.role === "patient") {
      const cnicPattern = /^(?:\d{5}-\d{7}-\d|\d{13})$/;
      if (!cnicPattern.test(values.cnic.trim())) {
        return "CNIC must be 13 digits or formatted like 12345-1234567-1.";
      }
      if (!values.date_of_birth || !values.gender) {
        return "Date of birth and gender are required for patient signup.";
      }
    }
    if (values.role === "doctor") {
      if (!values.pmdc_number.trim() || !values.specialization.trim() || !values.hospital_name.trim()) {
        return "PMDC/PMC number, specialization, and hospital/clinic name are required for doctors.";
      }
    }
    if (values.role === "admin" && !values.admin_invite_code.trim()) {
      return "Admin invite code is required for admin signup.";
    }
    return "";
  }

  function buildSignupPayload(): SignupOtpPayload {
    const commonPayload: SignupOtpPayload = {
      role: values.role,
      full_name: values.full_name.trim(),
      email: values.email.trim().toLowerCase(),
      password: values.password,
      confirm_password: values.confirm_password,
      phone: values.phone.trim(),
    };

    if (values.role === "patient") {
      return {
        ...commonPayload,
        cnic: values.cnic.trim(),
        date_of_birth: values.date_of_birth,
        gender: values.gender,
      };
    }

    if (values.role === "doctor") {
      return {
        ...commonPayload,
        pmdc_number: values.pmdc_number.trim(),
        specialization: values.specialization.trim(),
        hospital_name: values.hospital_name.trim(),
      };
    }

    return {
      ...commonPayload,
      admin_invite_code: values.admin_invite_code.trim(),
    };
  }

  async function createAccount() {
    const validationMessage = validate();
    if (validationMessage) {
      setStatusMessage(validationMessage);
      return;
    }

    setIsSubmitting(true);
    setStatusMessage("");
    setSuccessMessage("");

    try {
      const auth = await api.signupAccount(buildSignupPayload());

      saveSession(auth);
      setSuccessMessage("Account created successfully.");
      router.push(dashboardPathForRole(auth.user.role));
    } catch (error) {
      setStatusMessage(error instanceof Error ? error.message : "Signup failed.");
    } finally {
      setIsSubmitting(false);
    }
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    await createAccount();
  }

  return (
    <main className="app-shell min-h-screen px-4 py-8 sm:px-6 lg:px-8">
      <section className="mx-auto grid max-w-6xl gap-6 lg:grid-cols-[0.82fr_1.18fr]">
        <aside className="rounded-[28px] border border-white/10 bg-gradient-to-br from-[#06182F] via-[#082A46] to-[#064F59] p-7 text-white shadow-[0_24px_70px_rgba(6,24,47,0.18)] sm:p-9">
          <NoraLogo inverse />
          <div className="mt-12">
            <p className="text-xs font-bold uppercase tracking-[0.18em] text-teal-200">
              Verification ready
            </p>
            <h1 className="mt-4 text-4xl font-black leading-tight">
              Create a role-based Nora MedLink account.
            </h1>
            <p className="mt-5 text-sm leading-7 text-slate-300">
              Create a patient, doctor, or administrator account and go directly to the matching dashboard.
            </p>
          </div>
          <div className="mt-10 grid gap-3">
            {[
              "Unique email and phone checks",
              "Pakistani CNIC format check",
              "PMDC/PMC or admin invite validation",
              "JWT login after signup",
            ].map((item) => (
              <div key={item} className="rounded-2xl border border-white/10 bg-white/[0.08] px-4 py-3 text-sm font-semibold text-slate-100">
                {item}
              </div>
            ))}
          </div>
        </aside>

        <section className="rounded-[28px] border border-[#DCE8F5] bg-white p-6 shadow-[0_16px_40px_rgba(15,23,42,0.06)] sm:p-8">
          <div className="mb-8 flex items-center justify-between gap-4">
            <div>
              <p className="section-eyebrow">Signup</p>
              <h2 className="mt-2 text-3xl font-black tracking-tight text-slate-950">
                {roleHeadings[values.role]}
              </h2>
            </div>
            <Link href="/login" className="secondary-button px-4 py-2">
              Login
            </Link>
          </div>

          <form className="space-y-5" onSubmit={handleSubmit}>
            <div className="grid gap-3 sm:grid-cols-3">
              {roleCards.map((roleCard) => (
                <RoleCard
                  key={roleCard.role}
                  title={roleCard.title}
                  description={roleCard.description}
                  selected={values.role === roleCard.role}
                  onClick={() => selectRole(roleCard.role)}
                />
              ))}
            </div>

            <div className="grid gap-5 sm:grid-cols-2">
              <Field label="Full name" id="full_name" value={values.full_name} onChange={updateField("full_name")} />
              <Field label="Email" id="email" type="email" value={values.email} onChange={updateField("email")} />
              <Field label="Password" id="password" type="password" value={values.password} onChange={updateField("password")} />
              <Field label="Confirm password" id="confirm_password" type="password" value={values.confirm_password} onChange={updateField("confirm_password")} />
              <Field label="Phone number" id="phone" value={values.phone} onChange={updateField("phone")} />
              {values.role === "patient" ? (
                <>
                  <Field label="CNIC number" id="cnic" value={values.cnic} onChange={updateField("cnic")} placeholder="12345-1234567-1" />
                  <Field label="Date of birth" id="date_of_birth" type="date" value={values.date_of_birth} onChange={updateField("date_of_birth")} />
                  <div>
                    <label htmlFor="gender" className="text-sm font-bold text-slate-700">
                      Gender
                    </label>
                    <select id="gender" className="form-input" value={values.gender} onChange={updateField("gender")}>
                      <option value="">Select gender</option>
                      <option value="female">Female</option>
                      <option value="male">Male</option>
                      <option value="other">Other</option>
                    </select>
                  </div>
                </>
              ) : null}

              {values.role === "doctor" ? (
                <>
                  <Field label="PMDC/PMC registration number" id="pmdc_number" value={values.pmdc_number} onChange={updateField("pmdc_number")} />
                  <Field label="Specialization" id="specialization" value={values.specialization} onChange={updateField("specialization")} />
                  <Field label="Hospital/clinic name" id="hospital_name" value={values.hospital_name} onChange={updateField("hospital_name")} />
                </>
              ) : null}

              {values.role === "admin" ? (
                <Field
                  label="Admin invite code"
                  id="admin_invite_code"
                  type="password"
                  value={values.admin_invite_code}
                  onChange={updateField("admin_invite_code")}
                />
              ) : null}
            </div>

            {statusMessage ? (
              <p className="rounded-2xl border border-red-100 bg-red-50 px-4 py-3 text-sm font-semibold text-red-700">
                {statusMessage}
              </p>
            ) : null}

            {successMessage ? (
              <p className="rounded-2xl border border-emerald-100 bg-emerald-50 px-4 py-3 text-sm font-semibold text-emerald-700">
                {successMessage}
              </p>
            ) : null}

            <button type="submit" disabled={isSubmitting} className="gradient-button w-full">
              {isSubmitting ? "Creating account..." : "Create Account"}
            </button>
          </form>
        </section>
      </section>
    </main>
  );
}

function Field({
  label,
  id,
  type = "text",
  value,
  placeholder,
  inputMode,
  maxLength,
  onChange,
}: {
  label: string;
  id: string;
  type?: string;
  value: string;
  placeholder?: string;
  inputMode?: "numeric";
  maxLength?: number;
  onChange: (event: ChangeEvent<HTMLInputElement>) => void;
}) {
  return (
    <div>
      <label htmlFor={id} className="text-sm font-bold text-slate-700">
        {label}
      </label>
      <input
        id={id}
        type={type}
        className="form-input"
        value={value}
        placeholder={placeholder}
        inputMode={inputMode}
        maxLength={maxLength}
        onChange={onChange}
      />
    </div>
  );
}
