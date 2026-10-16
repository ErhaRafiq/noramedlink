"use client";

import { useMemo, useState } from "react";
import { SearchX, Stethoscope } from "lucide-react";

import { PageContainer, PageHeader } from "@/components/layout/PageHeader";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/ui/empty-state";
import type { AppointmentDoctor } from "@/lib/types";
import { useDoctorDirectory } from "@/hooks/doctors/use-doctor-directory";
import { useMyAppointments } from "@/hooks/doctors/use-my-appointments";
import { useStoredSession } from "@/hooks/use-stored-session";
import { BookingDialog } from "./BookingDialog";
import { DoctorCard, DoctorCardSkeleton } from "./DoctorCard";
import { DoctorFilters } from "./DoctorFilters";
import { MyAppointments } from "./MyAppointments";

type Notice = { tone: "success" | "error" | "warning"; text: string } | null;

export function DoctorsView() {
  const { session } = useStoredSession();
  const isPatient = session?.user.role === "patient";
  const directory = useDoctorDirectory();
  const appointments = useMyAppointments(isPatient);

  const [booking, setBooking] = useState<AppointmentDoctor | null>(null);
  const [notice, setNotice] = useState<Notice>(null);
  const busyTimes = useMemo(
    () =>
      appointments.appointments
        .filter((a) => a.status === "BOOKED")
        .map((a) => ({ start: a.date, end: new Date(new Date(a.date).getTime() + a.duration_minutes * 60_000).toISOString() })),
    [appointments.appointments],
  );

  function startBooking(doctor: AppointmentDoctor) {
    setNotice(null);
    if (!session) {
      setNotice({ tone: "warning", text: "Please sign in as a patient to book an appointment." });
      return;
    }
    if (!isPatient) {
      setNotice({ tone: "warning", text: "Only patient accounts can book appointments." });
      return;
    }
    setBooking(doctor);
  }

  async function booked(message: string) {
    setBooking(null);
    setNotice({ tone: "success", text: message });
    await Promise.all([appointments.reload(), directory.retry()]);
  }

  return (
    <PageContainer>
      <PageHeader
        eyebrow="Appointments"
        title="Find a doctor"
        description="Every doctor listed here has been verified by an administrator. Pick a real open time and book."
      />

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-[minmax(0,1fr)_340px]">
        <div className="min-w-0 space-y-5">
          <DoctorFilters directory={directory} />
          {notice ? <Alert tone={notice.tone}>{notice.text}</Alert> : null}

          <section aria-labelledby="doctor-results" aria-busy={directory.status === "loading"}>
            <div className="mb-3 flex items-baseline justify-between">
              <h2 id="doctor-results" className="text-base font-semibold text-ink">
                Doctors
              </h2>
              {directory.status === "ready" ? (
                <p className="text-sm text-ink-muted">
                  {directory.doctors.length} {directory.doctors.length === 1 ? "doctor" : "doctors"}
                </p>
              ) : null}
            </div>

            {directory.status === "loading" && !directory.hasLoaded ? (
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
            ) : directory.doctors.length === 0 ? (
              directory.filtered ? (
                <EmptyState
                  icon={SearchX}
                  title="No doctors match"
                  description="Try another name or city, or loosen the fee and rating limits."
                  action={
                    <Button variant="secondary" size="sm" onClick={directory.reset}>
                      Clear filters
                    </Button>
                  }
                />
              ) : (
                <EmptyState icon={Stethoscope} title="No verified doctors yet" description="Doctors appear here once an administrator approves them." />
              )
            ) : (
              <div className="grid gap-4 sm:grid-cols-2">
                {directory.doctors.map((doctor) => (
                  <DoctorCard key={`${doctor.source}-${doctor.id}`} doctor={doctor} canBook={session === null || isPatient} onBook={startBooking} />
                ))}
              </div>
            )}
          </section>
        </div>

        <MyAppointments signedInAsPatient={isPatient} list={appointments} />
      </div>

      <BookingDialog doctor={booking} busy={busyTimes} onClose={() => setBooking(null)} onBooked={(message) => void booked(message)} />
    </PageContainer>
  );
}
