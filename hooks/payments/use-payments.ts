"use client";

import { useCallback, useEffect, useState } from "react";

import { api } from "@/lib/api";
import type { Appointment, Payment } from "@/lib/types";

const PAGE_SIZE = 50;

/** Appointments still to pay, the payment history, and opening Stripe's payment page. */
export function usePayments(signedIn: boolean) {
  const [appointments, setAppointments] = useState<Appointment[]>([]);
  const [payments, setPayments] = useState<Payment[]>([]);
  const [status, setStatus] = useState<"loading" | "ready" | "error">("loading");
  const [error, setError] = useState("");
  const [payingId, setPayingId] = useState<number | null>(null);
  const [payError, setPayError] = useState<{ appointmentId: number; message: string } | null>(null);

  const load = useCallback(async () => {
    if (!signedIn) return;
    setStatus("loading");
    try {
      const [appointmentPage, paymentPage] = await Promise.all([
        api.appointments({ limit: PAGE_SIZE }),
        api.payments({ limit: PAGE_SIZE }),
      ]);
      setAppointments(appointmentPage.items);
      setPayments(paymentPage.items);
      setStatus("ready");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to load your payments.");
      setStatus("error");
    }
  }, [signedIn]);

  useEffect(() => {
    if (!signedIn) return;
    const timer = window.setTimeout(() => void load(), 0);
    return () => window.clearTimeout(timer);
  }, [load, signedIn]);

  /** Sends the browser to Stripe Checkout; on failure the button shows why. */
  const pay = useCallback(
    async (appointmentId: number) => {
      if (!signedIn || payingId !== null) return;
      setPayingId(appointmentId);
      setPayError(null);
      try {
        const { checkout_url } = await api.startCheckout(appointmentId);
        window.location.assign(checkout_url);
      } catch (err) {
        setPayError({ appointmentId, message: err instanceof Error ? err.message : "The payment page could not be opened." });
        setPayingId(null);
      }
    },
    [payingId, signedIn],
  );

  const toPay = appointments.filter((a) => a.status.toUpperCase() !== "CANCELLED" && a.payment_status.toUpperCase() !== "PAID");
  return { toPay, payments, status, error, payingId, payError, pay, reload: load };
}
