"use client";

import Link from "next/link";
import { ChangeEvent, FormEvent, useCallback, useEffect, useMemo, useState } from "react";
import {
  CalendarDays,
  Clock,
  MapPin,
  RefreshCw,
  Search,
  Stethoscope,
  WalletCards,
  XCircle,
} from "lucide-react";

import { api } from "@/lib/api";
import { getSession, type StoredSession } from "@/lib/auth";
import type { Appointment, AppointmentDoctor } from "@/lib/types";

function toDateTimeInputValue(date: Date) {
  const pad = (value: number) => String(value).padStart(2, "0");
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}T${pad(
    date.getHours(),
  )}:${pad(date.getMinutes())}`;
}

function defaultAppointmentDate() {
  const date = new Date();
  date.setDate(date.getDate() + 1);
  date.setHours(10, 0, 0, 0);
  return toDateTimeInputValue(date);
}

function formatAppointmentDate(value: string) {
  return new Intl.DateTimeFormat("en", {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(new Date(value));
}

function statusClass(status: string) {
  const normalized = status.toUpperCase();
  if (normalized === "BOOKED" || normalized === "CONFIRMED") {
    return "border-emerald-200 bg-emerald-50 text-emerald-700";
  }
  if (normalized === "CANCELLED") {
    return "border-red-200 bg-red-50 text-red-700";
  }
  if (normalized === "COMPLETED") {
    return "border-blue-200 bg-blue-50 text-blue-700";
  }
  return "border-amber-200 bg-amber-50 text-amber-700";
}

function paymentStatusClass(status: string) {
  return status.toUpperCase() === "SUCCESS"
    ? "border-emerald-200 bg-emerald-50 text-emerald-700"
    : "border-slate-200 bg-slate-50 text-slate-600";
}

export default function DoctorsPage() {
  const [session, setSession] = useState<StoredSession | null>(null);
  const [doctors, setDoctors] = useState<AppointmentDoctor[]>([]);
  const [appointments, setAppointments] = useState<Appointment[]>([]);
  const [searchTerm, setSearchTerm] = useState("");
  const [selectedSpecialty, setSelectedSpecialty] = useState("All Specialties");
  const [availableTodayOnly, setAvailableTodayOnly] = useState(false);
  const [appointmentDate, setAppointmentDate] = useState(defaultAppointmentDate);
  const [notes, setNotes] = useState("");
  const [patientAccessOtp, setPatientAccessOtp] = useState("");
  const [bookingDoctorId, setBookingDoctorId] = useState<number | null>(null);
  const [updatingAppointmentId, setUpdatingAppointmentId] = useState<number | null>(null);
  const [rescheduleValues, setRescheduleValues] = useState<Record<number, string>>({});
  const [statusMessage, setStatusMessage] = useState("");
  const [isLoadingDoctors, setIsLoadingDoctors] = useState(true);
  const [isLoadingAppointments, setIsLoadingAppointments] = useState(false);

  useEffect(() => {
    void Promise.resolve().then(() => setSession(getSession()));
  }, []);

  useEffect(() => {
    let isMounted = true;

    async function loadDoctors() {
      setIsLoadingDoctors(true);
      try {
        const doctorData = await api.appointmentDoctors();
        if (isMounted) {
          setDoctors(doctorData);
        }
      } catch (error) {
        if (isMounted) {
          setStatusMessage(error instanceof Error ? error.message : "Unable to load doctors.");
        }
      } finally {
        if (isMounted) {
          setIsLoadingDoctors(false);
        }
      }
    }

    void loadDoctors();
    return () => {
      isMounted = false;
    };
  }, []);

  const loadAppointments = useCallback(async (activeSession?: StoredSession | null) => {
    const appointmentSession = activeSession ?? session;
    if (!appointmentSession) {
      setAppointments([]);
      return;
    }

    setIsLoadingAppointments(true);
    try {
      const appointmentData = await api.appointments(appointmentSession.token);
      setAppointments(appointmentData);
    } catch (error) {
      setStatusMessage(error instanceof Error ? error.message : "Unable to load appointments.");
    } finally {
      setIsLoadingAppointments(false);
    }
  }, [session]);

  useEffect(() => {
    if (session) {
      void Promise.resolve().then(() => loadAppointments(session));
    }
  }, [loadAppointments, session]);

  const specialties = useMemo(
    () => ["All Specialties", ...Array.from(new Set(doctors.map((doctor) => doctor.specialty))).sort()],
    [doctors],
  );

  const filteredDoctors = useMemo(() => {
    const query = searchTerm.trim().toLowerCase();

    return doctors.filter((doctor) => {
      const matchesSearch =
        doctor.name.toLowerCase().includes(query) ||
        doctor.specialty.toLowerCase().includes(query) ||
        doctor.location.toLowerCase().includes(query);
      const matchesSpecialty =
        selectedSpecialty === "All Specialties" || doctor.specialty === selectedSpecialty;
      const matchesAvailability = !availableTodayOnly || doctor.available_today;

      return matchesSearch && matchesSpecialty && matchesAvailability;
    });
  }, [availableTodayOnly, doctors, searchTerm, selectedSpecialty]);

  const upcomingAppointments = useMemo(
    () =>
      [...appointments].sort(
        (first, second) => new Date(first.date).getTime() - new Date(second.date).getTime(),
      ),
    [appointments],
  );

  const handleSpecialtyChange = (event: ChangeEvent<HTMLSelectElement>) => {
    setSelectedSpecialty(event.target.value);
  };

  async function handleBookAppointment(doctor: AppointmentDoctor) {
    setStatusMessage("");

    if (!session) {
      setStatusMessage("Please log in as a patient before booking an appointment.");
      return;
    }

    if (session.user.role !== "patient") {
      setStatusMessage("Only patient accounts can book appointments.");
      return;
    }

    const scheduledDate = new Date(appointmentDate);
    if (Number.isNaN(scheduledDate.getTime())) {
      setStatusMessage("Choose a valid appointment date and time.");
      return;
    }

    setBookingDoctorId(doctor.id);
    try {
      const result = await api.createAppointment(session.token, {
        doctor_name: doctor.name,
        doctor_id: doctor.doctor_id,
        date: scheduledDate.toISOString(),
        notes: notes.trim() || null,
        patient_access_otp: patientAccessOtp.trim() || null,
      });

      setStatusMessage(result.message);
      setNotes("");
      setPatientAccessOtp("");
      await loadAppointments(session);
    } catch (error) {
      setStatusMessage(error instanceof Error ? error.message : "Unable to book appointment.");
    } finally {
      setBookingDoctorId(null);
    }
  }

  async function handleCancelAppointment(appointment: Appointment) {
    if (!session) {
      setStatusMessage("Please log in before updating an appointment.");
      return;
    }

    setUpdatingAppointmentId(appointment.id);
    setStatusMessage("");
    try {
      await api.updateAppointment(session.token, appointment.id, { status: "CANCELLED" });
      setStatusMessage(`Appointment #${appointment.id} cancelled.`);
      await loadAppointments(session);
    } catch (error) {
      setStatusMessage(error instanceof Error ? error.message : "Unable to cancel appointment.");
    } finally {
      setUpdatingAppointmentId(null);
    }
  }

  async function handleRescheduleAppointment(event: FormEvent<HTMLFormElement>, appointment: Appointment) {
    event.preventDefault();
    if (!session) {
      setStatusMessage("Please log in before updating an appointment.");
      return;
    }

    const nextValue = rescheduleValues[appointment.id] || toDateTimeInputValue(new Date(appointment.date));
    const nextDate = new Date(nextValue);
    if (Number.isNaN(nextDate.getTime())) {
      setStatusMessage("Choose a valid reschedule date and time.");
      return;
    }

    setUpdatingAppointmentId(appointment.id);
    setStatusMessage("");
    try {
      await api.updateAppointment(session.token, appointment.id, {
        date: nextDate.toISOString(),
        status: "BOOKED",
      });
      setStatusMessage(`Appointment #${appointment.id} rescheduled.`);
      await loadAppointments(session);
    } catch (error) {
      setStatusMessage(error instanceof Error ? error.message : "Unable to reschedule appointment.");
    } finally {
      setUpdatingAppointmentId(null);
    }
  }

  return (
    <main className="app-shell px-4 py-8 sm:px-6 lg:px-8">
      <section className="mx-auto max-w-7xl">
        <div className="dashboard-topbar mb-8 overflow-hidden">
          <div>
            <p className="section-eyebrow">Nora MedLink</p>
            <h1 className="section-title mt-3">Appointment Booking</h1>
            <p className="mt-3 max-w-2xl text-sm leading-6 text-slate-600 sm:text-base">
              Find doctors, choose a consultation time, and manage booked appointments from the FastAPI backend.
            </p>
          </div>
          <div className="flex flex-col gap-3 sm:flex-row">
            <Link href="/dashboard/patient" className="secondary-button gap-2 px-4 py-2">
              <Stethoscope className="h-4 w-4" />
              Patient Dashboard
            </Link>
            <Link href="/login" className="gradient-button gap-2 px-4 py-2">
              <WalletCards className="h-4 w-4" />
              Login
            </Link>
          </div>
        </div>

        <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_390px]">
          <div className="space-y-6">
            <section className="dashboard-panel">
              <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_220px_180px]">
                <div>
                  <label htmlFor="doctor-search" className="text-sm font-bold text-slate-700">
                    Search
                  </label>
                  <div className="relative">
                    <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
                    <input
                      id="doctor-search"
                      type="search"
                      value={searchTerm}
                      onChange={(event) => setSearchTerm(event.target.value)}
                      placeholder="Search by doctor, specialty, or location"
                      className="form-input pl-9 text-sm"
                    />
                  </div>
                </div>

                <div>
                  <label htmlFor="specialty" className="text-sm font-bold text-slate-700">
                    Specialty
                  </label>
                  <select
                    id="specialty"
                    value={selectedSpecialty}
                    onChange={handleSpecialtyChange}
                    className="form-input text-sm"
                  >
                    {specialties.map((specialty) => (
                      <option key={specialty} value={specialty}>
                        {specialty}
                      </option>
                    ))}
                  </select>
                </div>

                <label className="flex items-end">
                  <span className="flex min-h-[50px] w-full items-center gap-3 rounded-2xl border border-slate-200 bg-white/85 px-4 py-3 text-sm font-bold text-slate-700 shadow-sm">
                    <input
                      type="checkbox"
                      checked={availableTodayOnly}
                      onChange={(event) => setAvailableTodayOnly(event.target.checked)}
                      className="h-4 w-4 rounded border-slate-300 text-blue-600 focus:ring-blue-500"
                    />
                    Available Today
                  </span>
                </label>
              </div>

              <div className="mt-5 grid gap-4 md:grid-cols-2">
                <div>
                  <label htmlFor="appointment-date" className="text-sm font-bold text-slate-700">
                    Appointment time
                  </label>
                  <input
                    id="appointment-date"
                    type="datetime-local"
                    min={toDateTimeInputValue(new Date())}
                    value={appointmentDate}
                    onChange={(event) => setAppointmentDate(event.target.value)}
                    className="form-input text-sm"
                  />
                </div>
                <div>
                  <label htmlFor="patient-access-otp" className="text-sm font-bold text-slate-700">
                    Patient dashboard OTP
                  </label>
                  <input
                    id="patient-access-otp"
                    type="text"
                    value={patientAccessOtp}
                    onChange={(event) => setPatientAccessOtp(event.target.value)}
                    placeholder="Optional"
                    className="form-input text-sm"
                  />
                </div>
              </div>

              <div className="mt-4">
                <label htmlFor="appointment-notes" className="text-sm font-bold text-slate-700">
                  Notes
                </label>
                <textarea
                  id="appointment-notes"
                  value={notes}
                  onChange={(event) => setNotes(event.target.value)}
                  rows={3}
                  placeholder="Symptoms, preferred visit type, or context for the doctor"
                  className="form-input resize-none text-sm"
                />
              </div>
            </section>

            {statusMessage ? (
              <div className="rounded-2xl border border-blue-100 bg-blue-50 px-4 py-3 text-sm font-semibold text-blue-800">
                {statusMessage}
              </div>
            ) : null}

            <section>
              <div className="mb-4 flex items-center justify-between gap-4">
                <h2 className="text-lg font-black text-white">Doctors</h2>
                <p className="text-sm font-semibold text-slate-300">
                  {isLoadingDoctors
                    ? "Loading"
                    : `${filteredDoctors.length} result${filteredDoctors.length === 1 ? "" : "s"}`}
                </p>
              </div>

              {filteredDoctors.length > 0 ? (
                <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
                  {filteredDoctors.map((doctor) => (
                    <article key={`${doctor.source}-${doctor.id}`} className="glass-card floating-card p-5">
                      <div className="flex items-start justify-between gap-4">
                        <div>
                          <h3 className="text-lg font-black text-slate-950">{doctor.name}</h3>
                          <p className="mt-1 text-sm font-bold text-blue-600">{doctor.specialty}</p>
                        </div>
                        <span
                          className={`rounded-full px-3 py-1 text-xs font-bold ${
                            doctor.available_today
                              ? "bg-emerald-50 text-emerald-700"
                              : "bg-amber-50 text-amber-700"
                          }`}
                        >
                          {doctor.available_today ? "Today" : "Later"}
                        </span>
                      </div>

                      <div className="mt-5 space-y-3 text-sm text-slate-600">
                        <p className="flex items-center gap-2">
                          <Stethoscope className="h-4 w-4 text-blue-500" />
                          <span className="font-semibold text-slate-900">Rating:</span>
                          {doctor.rating.toFixed(1)} / 5.0
                        </p>
                        <p className="flex items-start gap-2">
                          <MapPin className="mt-0.5 h-4 w-4 text-blue-500" />
                          <span>{doctor.location}</span>
                        </p>
                      </div>

                      <button
                        type="button"
                        disabled={bookingDoctorId === doctor.id}
                        onClick={() => void handleBookAppointment(doctor)}
                        className="gradient-button mt-5 w-full gap-2 py-2.5"
                      >
                        <CalendarDays className="h-4 w-4" />
                        {bookingDoctorId === doctor.id ? "Booking" : "Book Appointment"}
                      </button>
                    </article>
                  ))}
                </div>
              ) : (
                <div className="glass-card border-dashed p-8 text-center">
                  <h3 className="text-lg font-semibold">No doctors found</h3>
                  <p className="mt-2 text-sm text-slate-500">Try changing your search term or filters.</p>
                </div>
              )}
            </section>
          </div>

          <aside className="dashboard-panel h-fit">
            <div className="flex items-center justify-between gap-3">
              <div>
                <p className="section-eyebrow">Patient queue</p>
                <h2 className="mt-2 text-2xl font-black text-slate-950">My Appointments</h2>
              </div>
              <button
                type="button"
                onClick={() => void loadAppointments()}
                disabled={!session || isLoadingAppointments}
                className="secondary-button px-3 py-2"
                aria-label="Refresh appointments"
              >
                <RefreshCw className={`h-4 w-4 ${isLoadingAppointments ? "animate-spin" : ""}`} />
              </button>
            </div>

            {!session ? (
              <div className="mt-5 rounded-2xl border border-amber-100 bg-amber-50 p-4 text-sm font-semibold text-amber-800">
                Login as a patient to see booked appointments.
              </div>
            ) : upcomingAppointments.length > 0 ? (
              <div className="mt-5 space-y-4">
                {upcomingAppointments.map((appointment) => {
                  const isUpdating = updatingAppointmentId === appointment.id;
                  const inputValue =
                    rescheduleValues[appointment.id] || toDateTimeInputValue(new Date(appointment.date));

                  return (
                    <article key={appointment.id} className="rounded-2xl border border-slate-200 bg-white p-4">
                      <div className="flex items-start justify-between gap-3">
                        <div>
                          <h3 className="font-black text-slate-950">{appointment.doctor_name}</h3>
                          <p className="mt-1 flex items-center gap-2 text-xs font-semibold text-slate-500">
                            <Clock className="h-3.5 w-3.5" />
                            {formatAppointmentDate(appointment.date)}
                          </p>
                        </div>
                        <span className={`rounded-full border px-3 py-1 text-xs font-bold ${statusClass(appointment.status)}`}>
                          {appointment.status.replaceAll("_", " ")}
                        </span>
                      </div>

                      {appointment.notes ? (
                        <p className="mt-3 rounded-xl bg-slate-50 p-3 text-sm leading-6 text-slate-600">
                          {appointment.notes}
                        </p>
                      ) : null}

                      <div className="mt-3 flex flex-wrap gap-2">
                        <span className={`rounded-full border px-3 py-1 text-xs font-bold ${paymentStatusClass(appointment.payment_status)}`}>
                          Payment: {appointment.payment_status}
                        </span>
                        <span className="rounded-full border border-slate-200 bg-slate-50 px-3 py-1 text-xs font-bold text-slate-600">
                          #{appointment.id}
                        </span>
                      </div>

                      <form className="mt-4 space-y-3" onSubmit={(event) => void handleRescheduleAppointment(event, appointment)}>
                        <input
                          type="datetime-local"
                          min={toDateTimeInputValue(new Date())}
                          value={inputValue}
                          onChange={(event) =>
                            setRescheduleValues((current) => ({
                              ...current,
                              [appointment.id]: event.target.value,
                            }))
                          }
                          className="form-input text-sm"
                        />
                        <div className="grid grid-cols-2 gap-2">
                          <button
                            type="submit"
                            disabled={isUpdating}
                            className="secondary-button gap-2 px-3 py-2 text-sm"
                          >
                            <RefreshCw className="h-4 w-4" />
                            Reschedule
                          </button>
                          <button
                            type="button"
                            disabled={isUpdating || appointment.status.toUpperCase() === "CANCELLED"}
                            onClick={() => void handleCancelAppointment(appointment)}
                            className="rounded-full border border-red-100 bg-red-50 px-3 py-2 text-sm font-bold text-red-700 transition hover:border-red-200 disabled:cursor-not-allowed disabled:opacity-60"
                          >
                            <span className="inline-flex items-center justify-center gap-2">
                              <XCircle className="h-4 w-4" />
                              Cancel
                            </span>
                          </button>
                        </div>
                      </form>
                    </article>
                  );
                })}
              </div>
            ) : (
              <div className="mt-5 rounded-2xl border border-dashed border-slate-200 bg-slate-50 p-5 text-sm font-semibold text-slate-500">
                No appointments booked yet.
              </div>
            )}
          </aside>
        </div>
      </section>
    </main>
  );
}
