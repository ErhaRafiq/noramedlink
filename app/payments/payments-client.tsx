"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { FormEvent, useMemo, useState } from "react";

type PaymentMethod = "EASYPAISA" | "JAZZCASH" | "NAYAPAY" | "CASH";

const paymentOptions: Array<{
  value: PaymentMethod;
  title: string;
  description: string;
  accent: string;
}> = [
  {
    value: "EASYPAISA",
    title: "Easypaisa",
    description: "Fast wallet checkout for mobile users.",
    accent: "from-emerald-500 to-green-500",
  },
  {
    value: "JAZZCASH",
    title: "JazzCash",
    description: "Pakistan wallet payment flow.",
    accent: "from-orange-500 to-rose-500",
  },
  {
    value: "NAYAPAY",
    title: "NayaPay",
    description: "Digital wallet style payment option.",
    accent: "from-slate-800 to-slate-600",
  },
  {
    value: "CASH",
    title: "Cash on Visit",
    description: "Pay directly when you visit the doctor or clinic.",
    accent: "from-amber-400 to-yellow-500",
  },
];

function getStoredUserId() {
  if (typeof window === "undefined") {
    return "";
  }

  return localStorage.getItem("userId") ?? "";
}

function getStoredUserName() {
  if (typeof window === "undefined") {
    return "";
  }

  return localStorage.getItem("userName") ?? "Patient";
}

export default function PaymentsClient() {
  const searchParams = useSearchParams();
  const linkedAppointmentId = searchParams.get("appointmentId") ?? "";
  const [userId] = useState(getStoredUserId);
  const [userName] = useState(getStoredUserName);
  const [amount, setAmount] = useState("1500");
  const [method, setMethod] = useState<PaymentMethod>("EASYPAISA");
  const [phone, setPhone] = useState("");
  const [statusMessage, setStatusMessage] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);

  const selectedPayment = useMemo(
    () => paymentOptions.find((option) => option.value === method) ?? paymentOptions[0],
    [method],
  );
  const isCashPayment = method === "CASH";

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setStatusMessage("");

    if (!userId) {
      setStatusMessage("Please login before creating a payment.");
      return;
    }

    if (!isCashPayment && !phone.trim()) {
      setStatusMessage("Enter the wallet phone number to continue.");
      return;
    }

    setIsSubmitting(true);

    try {
      const response = await fetch("/api/payments/create", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          userId,
          amount,
          method,
          phone: isCashPayment ? undefined : phone,
          purpose: linkedAppointmentId
            ? `Appointment payment #${linkedAppointmentId}`
            : "Doctor consultation",
          appointmentId: linkedAppointmentId || undefined,
        }),
      });

      const data = (await response.json()) as {
        message?: string;
        payment?: { reference: string; status: string };
      };

      if (!response.ok) {
        setStatusMessage(data.message ?? "Unable to create payment.");
        return;
      }

      setStatusMessage(data.message ?? `Payment request created via ${selectedPayment.title}`);
    } catch {
      setStatusMessage("Unable to create payment. Please try again.");
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <main className="app-shell px-4 py-8 sm:px-6 lg:px-8">
      <section className="mx-auto max-w-5xl">
        <div className="mb-8 flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <Link href="/" className="section-eyebrow">
              Nora MedLink
            </Link>
            <h1 className="section-title mt-3">Consultation Payment</h1>
            <p className="mt-3 max-w-2xl text-sm leading-6 text-slate-300 sm:text-base">
              Select a wallet or choose cash on visit for a consultation or
              linked appointment.
            </p>
          </div>
          <Link href="/doctors" className="secondary-button">
            Book Appointment
          </Link>
        </div>

        {linkedAppointmentId ? (
          <div className="mb-6 rounded-2xl border border-blue-100 bg-blue-50 px-4 py-3 text-sm font-semibold text-blue-800">
            Linked appointment: #{linkedAppointmentId}
          </div>
        ) : null}

        <div className="grid gap-6 lg:grid-cols-[1.1fr_0.9fr]">
          <form className="glass-card p-6 sm:p-8" onSubmit={handleSubmit}>
            <div className="grid gap-5 sm:grid-cols-2">
              <div>
                <label htmlFor="amount" className="text-sm font-medium text-slate-700">
                  Amount in PKR
                </label>
                <input
                  id="amount"
                  type="number"
                  min="1"
                  value={amount}
                  onChange={(event) => setAmount(event.target.value)}
                  className="form-input"
                />
              </div>

              <div>
                <label htmlFor="phone" className="text-sm font-medium text-slate-700">
                  {isCashPayment ? "Phone number optional" : "Wallet phone number"}
                </label>
                <input
                  id="phone"
                  type="tel"
                  value={phone}
                  onChange={(event) => setPhone(event.target.value)}
                  className="form-input"
                  placeholder={isCashPayment ? "Optional contact number" : "03xx xxxxxxx"}
                />
              </div>
            </div>

            <div className="mt-6">
              <span className="text-sm font-medium text-slate-700">
                Select payment method
              </span>
              <div className="mt-3 grid gap-3">
                {paymentOptions.map((option) => {
                  const isSelected = option.value === method;

                  return (
                    <button
                      key={option.value}
                      type="button"
                      onClick={() => setMethod(option.value)}
                      className={`flex items-center justify-between gap-4 rounded-3xl border p-4 text-left transition ${
                        isSelected
                          ? "border-slate-900 bg-slate-950 text-white shadow-lg"
                          : "border-slate-200 bg-white/90 hover:border-slate-300"
                      }`}
                      aria-pressed={isSelected}
                    >
                      <div className="flex items-center gap-4">
                        <span
                          className={`h-11 w-11 rounded-2xl bg-gradient-to-br ${option.accent}`}
                        />
                        <span>
                          <span
                            className={`block text-sm font-bold ${
                              isSelected ? "text-white" : "text-slate-950"
                            }`}
                          >
                            {option.title}
                          </span>
                          <span
                            className={`mt-1 block text-xs leading-5 ${
                              isSelected ? "text-slate-200" : "text-slate-500"
                            }`}
                          >
                            {option.description}
                          </span>
                        </span>
                      </div>
                      <span
                        className={`rounded-full px-3 py-1 text-xs font-bold ${
                          isSelected
                            ? "bg-white/10 text-white"
                            : "bg-slate-100 text-slate-600"
                        }`}
                      >
                        {isSelected ? "Selected" : "Choose"}
                      </span>
                    </button>
                  );
                })}
              </div>
            </div>

            {statusMessage ? (
              <p className="mt-5 rounded-2xl border border-green-100 bg-green-50 px-4 py-3 text-sm leading-6 text-green-800">
                {statusMessage}
              </p>
            ) : null}

            <button
              type="submit"
              disabled={isSubmitting}
              className="gradient-button mt-6 w-full"
            >
              {isSubmitting ? "Confirming..." : `Confirm ${selectedPayment.title}`}
            </button>
          </form>

          <aside className="rounded-[24px] border border-slate-200 bg-white p-6 shadow-calm sm:p-8">
            <p className="section-eyebrow">Payment flow</p>
            <h2 className="mt-3 text-2xl font-black text-slate-950">
              Payment confirmation
            </h2>
            <p className="mt-4 text-sm leading-6 text-slate-600">
              Wallet payments are marked successful immediately. Cash payments
              are saved as pay on visit, so the admin can collect and update the
              payment later.
            </p>

            <div className="mt-6 space-y-3 text-sm font-semibold text-slate-700">
              <p className="rounded-2xl bg-slate-50 px-4 py-3">
                User: {userName}
              </p>
              <p className="rounded-2xl bg-slate-50 px-4 py-3">
                Method: {selectedPayment.title}
              </p>
              <p className="rounded-2xl bg-slate-50 px-4 py-3">
                Payment status: {isCashPayment ? "PAY_ON_VISIT" : "SUCCESS after confirmation"}
              </p>
              <p className="rounded-2xl bg-slate-50 px-4 py-3">
                Linked appointment: {linkedAppointmentId ? `#${linkedAppointmentId}` : "none"}
              </p>
            </div>
          </aside>
        </div>
      </section>
    </main>
  );
}
