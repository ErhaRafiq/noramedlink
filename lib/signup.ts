import type { SignupOtpPayload, UserRole } from "@/lib/types";

export type SignupValues = {
  role: UserRole;
  full_name: string;
  email: string;
  password: string;
  confirm_password: string;
  phone: string;
  cnic: string;
  date_of_birth: string;
  gender: string;
  pmdc_number: string;
  specialization: string;
  hospital_name: string;
  admin_invite_code: string;
};

export const EMPTY_SIGNUP: SignupValues = {
  role: "patient",
  full_name: "",
  email: "",
  password: "",
  confirm_password: "",
  phone: "",
  cnic: "",
  date_of_birth: "",
  gender: "",
  pmdc_number: "",
  specialization: "",
  hospital_name: "",
  admin_invite_code: "",
};

export const MIN_PASSWORD_LENGTH = 8;
const CNIC_PATTERN = /^(?:\d{5}-\d{7}-\d|\d{13})$/;

export function parseRole(value: string | null | undefined): UserRole {
  return value === "doctor" || value === "admin" ? value : "patient";
}

/** Field-level errors (empty object = valid). The backend validates again. */
export function validateSignup(values: SignupValues): Partial<Record<keyof SignupValues, string>> {
  const errors: Partial<Record<keyof SignupValues, string>> = {};
  if (!values.full_name.trim()) errors.full_name = "Enter your full name.";
  if (!/^\S+@\S+\.\S+$/.test(values.email.trim())) errors.email = "Enter a valid email address.";
  if (!values.phone.trim()) errors.phone = "Enter a phone number.";
  if (values.password.length < MIN_PASSWORD_LENGTH) errors.password = `Use at least ${MIN_PASSWORD_LENGTH} characters.`;
  if (values.confirm_password !== values.password) errors.confirm_password = "Passwords do not match.";

  if (values.role === "patient") {
    if (!CNIC_PATTERN.test(values.cnic.trim())) errors.cnic = "Use 13 digits, e.g. 12345-1234567-1.";
    if (!values.date_of_birth) errors.date_of_birth = "Enter your date of birth.";
    if (!values.gender) errors.gender = "Select an option.";
  }
  if (values.role === "doctor") {
    if (!values.pmdc_number.trim()) errors.pmdc_number = "Enter your PMDC/PMC registration number.";
    if (!values.specialization.trim()) errors.specialization = "Enter your specialization.";
    if (!values.hospital_name.trim()) errors.hospital_name = "Enter your hospital or clinic.";
  }
  if (values.role === "admin" && !values.admin_invite_code.trim()) {
    errors.admin_invite_code = "An invite code is required for admin accounts.";
  }
  return errors;
}

/** The request body for POST /auth/signup: common fields plus only the chosen role's fields. */
export function buildSignupPayload(values: SignupValues): SignupOtpPayload {
  const common: SignupOtpPayload = {
    role: values.role,
    full_name: values.full_name.trim(),
    email: values.email.trim().toLowerCase(),
    password: values.password,
    confirm_password: values.confirm_password,
    phone: values.phone.trim(),
  };
  if (values.role === "patient") {
    return { ...common, cnic: values.cnic.trim(), date_of_birth: values.date_of_birth, gender: values.gender };
  }
  if (values.role === "doctor") {
    return {
      ...common,
      pmdc_number: values.pmdc_number.trim(),
      specialization: values.specialization.trim(),
      hospital_name: values.hospital_name.trim(),
    };
  }
  return { ...common, admin_invite_code: values.admin_invite_code.trim() };
}
