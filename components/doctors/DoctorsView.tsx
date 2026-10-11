"use client";

import { useState } from "react";
import { SearchX, Stethoscope } from "lucide-react";

import { PageContainer, PageHeader } from "@/components/layout/PageHeader";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/ui/empty-state";
import { api } from "@/lib/api";
import { tomorrowAtTen } from "@/lib/datetime";
import type { AppointmentDoctor } from "@/lib/types";
import { useDoctorDirectory } from "@/hooks/doctors/use-doctor-directory";
import { useMyAppointments } from "@/hooks/doctors/use-my-appointments";
import { useStoredSession } from "@/hooks/use-stored-session";
import { BookingDetails, type BookingDetailsValue } from "./BookingDetails";
import { DoctorCard, DoctorCardSkeleton } from "./DoctorCard";
import { DoctorFilters } from "./DoctorFilters";
import { MyAppointments } from "./MyAppointments";

type Notice = { tone: "success" | "error" | "warning"; text: string } | null;

export function DoctorsView() {
  const { session } = useStoredSession();
  const isPatient = session?.user.role === "patient";
  const directory = useDoctorDirectory();
  const appointments = useMyAppointments(isPatient ? session.token : null);

  const [details, setDetails] = useState<BookingDetailsValue>(() => ({ date: tomorrowAtTen(), notes: "", accessCode: "" }));
  const [bookingId, setBookingId] = useState<number | null>(null);
  const [notice, setNotice] = useState<Notice>(null);

  async function book(doctor: AppointmentDoctor) {
    if (bookingId !== null) return;
    setNotice(null);
    if (!session) {
      setNotice({ tone: "warning", text: "Please sign in as a patient to book an appointment." });
      return;
    }
    if (!isPatient) {
      setNotice({ tone: "warning", text: "Only patient accounts can book appointments." });
      return;
    }
    const date = new Date(details.date);
    if (Number.isNaN(date.getTime())) {
      setNotice({ tone: "error", text: "Choose a valid date and time in Booking details." });
      return;
    }

    setBookingId(doctor.id);
    try {
      const result = await api.bookAppointment(session.token, {
        doctorId: doctor.id,
        date: date.toISOString(),
        notes: details.notes.trim(),
        patientAccessOtp: details.accessCode.trim(),
      });
      setNotice({ tone: "success", text: result.message });
      setDetails((current) => ({ ...current, notes: "", accessCode: "" }));
      await appointments.reload();
    } catch (err) {
      setNotice({ tone: "error", text: err instanceof Error ? err.message : "Unable to book the appointment." });
    } finally {
      setBookingId(null);
    }
  }

  return (
    <PageContainer>
      <PageHeader
        eyebrow="Appointments"
        title="Find a doctor"
        description="Every doctor listed here has been verified by an administrator. Choose a time, then book."
      />

      <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_340px]">
        <div className="space-y-5">
          <BookingDetails value={details} onChange={setDetails} />
          <DoctorFilters filters={directory.filters} specialties={directory.specialties} />
          {notice ? <Alert tone={notice.tone}>{notice.text}</Alert> : null}

          <section aria-labelledby="doctor-results" aria-busy={directory.status === "loading"}>
            <div className="mb-3 flex items-baseline justify-between">
              <h2 id="doctor-results" className="text-base font-semibold text-ink">
                Doctors
              </h2>
              {directory.status === "ready" ? (
                <p className="text-sm text-ink-muted">
                  {directory.doctors.length} of {directory.total}
                </p>
              ) : null}
            </div>

            {directory.status === "loading" ? (
              <div className="grid gap-4 sm:grid-cols-2">
                {Array.from({ length: 4 }, (_, i) => (
                  <DoctorCardSkeleton key={i} />
                ))}
              </div>
            ) : directory.status === "error" ? (
              <Alert tone="error" title="Doctors could not be loaded">
                {directory.error}{" "}
                <Button variant="ghost" size="sm" onClick={directory.retry} className="ml-1 px-2">
                  Try again
                </Button>
              </Alert>
            ) : directory.total === 0 ? (
              <EmptyState icon={Stethoscope} title="No verified doctors yet" description="Doctors appear here once an administrator approves them." />
            ) : directory.doctors.length === 0 ? (
              <EmptyState icon={SearchX} title="No doctors match" description="Try another name, specialty or turn off Available today." />
            ) : (
              <div className="grid gap-4 sm:grid-cols-2">
                {directory.doctors.map((doctor) => (
                  <DoctorCard
                    key={`${doctor.source}-${doctor.id}`}
                    doctor={doctor}
                    booking={bookingId === doctor.id}
                    disabled={bookingId !== null}
                    onBook={(d) => void book(d)}
                  />
                ))}
              </div>
            )}
          </section>
        </div>

        <MyAppointments signedInAsPatient={isPatient} list={appointments} />
      </div>
    </PageContainer>
  );
}
