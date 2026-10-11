"use client";

import Link from "next/link";
import { useState, type FormEvent } from "react";
import { ClipboardCheck, LocateFixed, PhoneCall, Send } from "lucide-react";

import { PageContainer, PageHeader } from "@/components/layout/PageHeader";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/ui/empty-state";
import { TextAreaField, TextField } from "@/components/ui/field";
import { api } from "@/lib/api";
import { useStoredSession } from "@/hooks/use-stored-session";

type RecordedRequest = { id: number; status: string };
type Location = { latitude: string; longitude: string };

const NEXT_STEPS = [
  "Your request is saved with your contact details and symptoms.",
  "No doctor is dispatched automatically and there is no live tracking.",
  "Keep your phone nearby; follow-up is not guaranteed in this prototype.",
];

export function EmergencyView() {
  const { ready, session } = useStoredSession();
  const isPatient = session?.user.role === "patient";

  const [name, setName] = useState<string | null>(null);
  const [phone, setPhone] = useState("");
  const [address, setAddress] = useState("");
  const [symptoms, setSymptoms] = useState("");
  const [location, setLocation] = useState<Location | null>(null);
  const [locating, setLocating] = useState(false);
  const [locationError, setLocationError] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");
  const [recorded, setRecorded] = useState<RecordedRequest | null>(null);

  const patientName = name ?? session?.user.full_name ?? "";

  function addMyLocation() {
    setLocationError("");
    if (!("geolocation" in navigator)) {
      setLocationError("Location is not available in this browser. Type your address instead.");
      return;
    }
    setLocating(true);
    navigator.geolocation.getCurrentPosition(
      (position) => {
        setLocation({ latitude: position.coords.latitude.toFixed(6), longitude: position.coords.longitude.toFixed(6) });
        setLocating(false);
      },
      () => {
        setLocationError("Location access was denied or failed. Type your address instead.");
        setLocating(false);
      },
      { timeout: 10_000 },
    );
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (submitting || !session) return;
    setError("");
    if (!patientName.trim() || !phone.trim() || !address.trim() || !symptoms.trim()) {
      setError("Fill in the name, phone, address and symptoms.");
      return;
    }
    setSubmitting(true);
    try {
      const data = await api.createEmergencyRequest(session.token, {
        patientName: patientName.trim(),
        phone: phone.trim(),
        address: address.trim(),
        symptoms: symptoms.trim(),
        latitude: location?.latitude,
        longitude: location?.longitude,
      });
      setRecorded({ id: data.booking.id, status: data.booking.status });
    } catch (err) {
      setError(err instanceof Error ? err.message : "The request could not be sent. Please try again.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <PageContainer>
      <PageHeader
        eyebrow="Home visit"
        title="Request a doctor at home"
        description="Send your details and symptoms. Requests are recorded for follow-up; this is not an ambulance service."
      />

      <div className="mb-6 flex flex-col gap-3 rounded-card border border-rose-200 bg-rose-50 p-5 sm:flex-row sm:items-center" role="alert">
        <PhoneCall className="h-6 w-6 flex-shrink-0 text-rose-600" aria-hidden />
        <p className="text-sm font-semibold leading-6 text-rose-900">
          If this is an emergency, call 1122 or go to the nearest emergency department now. Do not wait for a reply here.
        </p>
      </div>

      <div className="grid gap-6 lg:grid-cols-[1.1fr_0.9fr]">
        <section aria-labelledby="request-form-title" className="rounded-card border border-line bg-white p-5 shadow-card sm:p-6">
          <h2 id="request-form-title" className="text-base font-semibold text-ink">
            Your request
          </h2>

          {!ready ? null : !session ? (
            <EmptyState
              className="mt-4"
              icon={Send}
              title="Sign in to send a request"
              description="Home-visit requests are linked to your patient account."
              action={
                <Link href="/login" className="secondary-button min-h-[36px] px-3 text-xs">
                  Sign in
                </Link>
              }
            />
          ) : !isPatient ? (
            <Alert tone="warning" className="mt-4">
              Only patient accounts can send home-visit requests.
            </Alert>
          ) : (
            <form className="mt-4 space-y-4" onSubmit={handleSubmit} noValidate>
              <TextField label="Patient name" autoComplete="name" value={patientName} onChange={(e) => setName(e.target.value)} />
              <TextField label="Phone number" type="tel" autoComplete="tel" placeholder="03XX XXXXXXX" value={phone} onChange={(e) => setPhone(e.target.value)} />
              <TextAreaField
                label="Home address"
                autoComplete="street-address"
                rows={3}
                placeholder="House, street, area, city"
                value={address}
                onChange={(e) => setAddress(e.target.value)}
              />
              <TextAreaField
                label="Symptoms"
                rows={3}
                placeholder="What is happening and since when"
                value={symptoms}
                onChange={(e) => setSymptoms(e.target.value)}
              />
              <div>
                <Button variant="secondary" loading={locating} icon={<LocateFixed className="h-4 w-4" />} onClick={addMyLocation} className="w-full">
                  {locating ? "Getting your location..." : location ? "Update my location" : "Add my current location"}
                </Button>
                {location ? (
                  <p className="mt-2 text-xs text-ink-muted">
                    Location added: {location.latitude}, {location.longitude}
                  </p>
                ) : null}
                {locationError ? <p className="mt-2 text-xs text-rose-600">{locationError}</p> : null}
              </div>
              {error ? <Alert tone="error">{error}</Alert> : null}
              <Button type="submit" size="lg" loading={submitting} icon={<Send className="h-4 w-4" />} className="w-full">
                {submitting ? "Sending..." : "Send request"}
              </Button>
            </form>
          )}
        </section>

        <aside aria-labelledby="next-steps-title" className="h-fit rounded-card border border-line bg-white p-5 shadow-card sm:p-6">
          <h2 id="next-steps-title" className="text-base font-semibold text-ink">
            {recorded ? "Request recorded" : "What happens next"}
          </h2>
          {recorded ? (
            <Alert tone="success" className="mt-4" title={`Request #${recorded.id} saved`}>
              Status: {recorded.status.replaceAll("_", " ").toLowerCase()}. No doctor has been assigned yet and there is no
              arrival time. If your condition gets worse, call 1122.
            </Alert>
          ) : null}
          <ul className="mt-4 space-y-3">
            {NEXT_STEPS.map((step) => (
              <li key={step} className="flex gap-3 text-sm leading-6 text-slate-600">
                <ClipboardCheck className="mt-0.5 h-4 w-4 flex-shrink-0 text-teal-600" aria-hidden />
                {step}
              </li>
            ))}
          </ul>
        </aside>
      </div>
    </PageContainer>
  );
}
