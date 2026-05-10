"use client";

import Link from "next/link";
import { FormEvent, useState } from "react";

type BookingResponse = {
  message?: string;
  booking?: {
    id: number;
    doctorName: string;
    status: string;
    estimatedMinutes: number;
  };
};

function getStoredValue(key: string) {
  if (typeof window === "undefined") {
    return "";
  }

  return localStorage.getItem(key) ?? "";
}

export default function EmergencyPage() {
  const [userId] = useState(() => getStoredValue("userId"));
  const [patientName, setPatientName] = useState(() => getStoredValue("userName"));
  const [phone, setPhone] = useState("");
  const [address, setAddress] = useState("");
  const [symptoms, setSymptoms] = useState("");
  const [latitude, setLatitude] = useState("");
  const [longitude, setLongitude] = useState("");
  const [statusMessage, setStatusMessage] = useState("");
  const [booking, setBooking] = useState<BookingResponse["booking"]>(undefined);
  const [isSubmitting, setIsSubmitting] = useState(false);

  const useCurrentLocation = () => {
    if (!navigator.geolocation) {
      setStatusMessage("Location is not available in this browser.");
      return;
    }

    setStatusMessage("Getting your location...");
    navigator.geolocation.getCurrentPosition(
      (position) => {
        setLatitude(position.coords.latitude.toFixed(6));
        setLongitude(position.coords.longitude.toFixed(6));
        setStatusMessage("Location added to your emergency request.");
      },
      () => {
        setStatusMessage("Unable to access location. You can type your address instead.");
      },
    );
  };

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setStatusMessage("");

    if (!userId) {
      setStatusMessage("Please login before booking an emergency doctor.");
      return;
    }

    setIsSubmitting(true);

    try {
      const response = await fetch("/api/emergency/book", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          userId,
          patientName,
          phone,
          address,
          symptoms,
          latitude,
          longitude,
        }),
      });

      const data = (await response.json()) as BookingResponse;

      if (!response.ok) {
        setStatusMessage(data.message ?? "Unable to book emergency doctor.");
        return;
      }

      setBooking(data.booking);
      setStatusMessage(data.message ?? "Doctor assigned for your home visit.");
    } catch {
      setStatusMessage("Unable to book emergency doctor. Please try again.");
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <main className="app-shell px-4 py-8 sm:px-6 lg:px-8">
      <section className="mx-auto max-w-6xl">
        <div className="mb-8 flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <Link href="/" className="section-eyebrow">
              Nora MedLink Emergency
            </Link>
            <h1 className="section-title mt-3">
              Book a doctor at home
            </h1>
            <p className="mt-3 max-w-2xl text-sm leading-6 text-slate-300 sm:text-base">
              Request urgent home care, share your location, and track the
              assigned doctor like a ride coming to you.
            </p>
          </div>
          <Link href="/payments" className="gradient-button">
            Pay for Visit
          </Link>
        </div>

        <div className="grid gap-6 lg:grid-cols-[0.9fr_1.1fr]">
          <form className="glass-card p-6 sm:p-8" onSubmit={handleSubmit}>
            <div className="space-y-5">
              <div>
                <label htmlFor="patientName" className="text-sm font-medium text-slate-700">
                  Patient Name
                </label>
                <input
                  id="patientName"
                  value={patientName}
                  onChange={(event) => setPatientName(event.target.value)}
                  className="form-input"
                  placeholder="Patient full name"
                />
              </div>

              <div>
                <label htmlFor="phone" className="text-sm font-medium text-slate-700">
                  Phone Number
                </label>
                <input
                  id="phone"
                  value={phone}
                  onChange={(event) => setPhone(event.target.value)}
                  className="form-input"
                  placeholder="03XX XXXXXXX"
                />
              </div>

              <div>
                <label htmlFor="address" className="text-sm font-medium text-slate-700">
                  Home Address
                </label>
                <textarea
                  id="address"
                  value={address}
                  onChange={(event) => setAddress(event.target.value)}
                  className="form-input min-h-24 resize-none"
                  placeholder="House, street, area, city"
                />
              </div>

              <div>
                <label htmlFor="symptoms" className="text-sm font-medium text-slate-700">
                  Symptoms or Emergency
                </label>
                <textarea
                  id="symptoms"
                  value={symptoms}
                  onChange={(event) => setSymptoms(event.target.value)}
                  className="form-input min-h-24 resize-none"
                  placeholder="Fever, chest pain, weakness, breathing issue..."
                />
              </div>

              <button
                type="button"
                onClick={useCurrentLocation}
                className="secondary-button w-full"
              >
                Use My Current Location
              </button>

              {(latitude || longitude) ? (
                <p className="rounded-2xl bg-slate-50 px-4 py-3 text-xs font-semibold text-slate-600">
                  Location: {latitude || "?"}, {longitude || "?"}
                </p>
              ) : null}

              {statusMessage ? (
                <p className="rounded-2xl border border-blue-100 bg-blue-50 px-4 py-3 text-sm leading-6 text-blue-800">
                  {statusMessage}
                </p>
              ) : null}

              <button
                type="submit"
                disabled={isSubmitting}
                className="gradient-button w-full"
              >
                {isSubmitting ? "Finding Doctor..." : "Find Emergency Doctor"}
              </button>
            </div>
          </form>

          <section className="space-y-6">
            <div className="relative min-h-[420px] overflow-hidden rounded-[24px] border border-slate-200 bg-slate-900 shadow-calm">
              <div className="absolute inset-0 bg-[linear-gradient(90deg,rgba(255,255,255,0.08)_1px,transparent_1px),linear-gradient(rgba(255,255,255,0.08)_1px,transparent_1px)] bg-[size:48px_48px]" />
              <div className="absolute left-[12%] top-[26%] h-3 w-3 rounded-full bg-emerald-300 shadow-[0_0_0_10px_rgba(110,231,183,0.18)]" />
              <div className="absolute right-[18%] top-[18%] h-3 w-3 rounded-full bg-blue-300 shadow-[0_0_0_10px_rgba(59,130,246,0.2)]" />
              <div className="absolute bottom-[18%] left-[42%] h-4 w-4 rounded-full bg-white shadow-[0_0_0_12px_rgba(255,255,255,0.16)]" />
              <div className="absolute left-[13%] top-[28%] h-[3px] w-[68%] rotate-[-7deg] rounded-full bg-gradient-to-r from-emerald-300 via-blue-300 to-white" />
              <div className="absolute bottom-6 left-6 right-6 rounded-2xl bg-white/95 p-5 shadow-xl">
                <p className="text-xs font-bold uppercase tracking-[0.16em] text-blue-700">
                  Live tracking preview
                </p>
                <h2 className="mt-2 text-2xl font-black text-slate-950">
                  {booking ? booking.doctorName : "Doctor route will appear here"}
                </h2>
                <p className="mt-2 text-sm leading-6 text-slate-600">
                  {booking
                    ? `${booking.estimatedMinutes} minutes away. Status: ${booking.status.replaceAll("_", " ")}.`
                    : "Use current location and submit the request to assign a nearby doctor."}
                </p>
              </div>
            </div>

            <div className="grid gap-4 sm:grid-cols-3">
              {["Searching nearby doctors", "Doctor assigned", "Arriving at home"].map(
                (step, index) => (
                  <div
                    key={step}
                    className={`rounded-2xl border p-4 ${
                      booking && index < 2
                        ? "border-emerald-200 bg-emerald-50"
                        : "border-slate-200 bg-white"
                    }`}
                  >
                    <p className="text-sm font-bold text-slate-950">{step}</p>
                    <p className="mt-2 text-xs leading-5 text-slate-500">
                      {index === 0
                        ? "Matching by location and urgency."
                        : index === 1
                          ? "Doctor details and ETA are shown."
                          : "Track arrival until the visit starts."}
                    </p>
                  </div>
                ),
              )}
            </div>
          </section>
        </div>
      </section>
    </main>
  );
}
