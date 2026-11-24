"use client";

import { useState, type FormEvent } from "react";
import { Search, Send } from "lucide-react";

import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { TextAreaField, TextField } from "@/components/ui/field";
import { useLocationPicker } from "@/hooks/home-visits/use-location-picker";
import type { useHomeVisitRequest } from "@/hooks/home-visits/use-home-visit-request";
import type { HomeVisitCheck } from "@/lib/types";
import { DoctorChoices } from "./DoctorChoices";
import { LocationPicker } from "./LocationPicker";
import { SafetyChecklist, type Answers } from "./SafetyChecklist";

type Request = ReturnType<typeof useHomeVisitRequest>;

const PHONE = /^[0-9+()\- ]{7,20}$/;

export function RequestForm({
  questions,
  notice,
  request,
}: {
  questions: Array<{ id: string; question: string }>;
  notice: string;
  request: Request;
}) {
  const picker = useLocationPicker();
  const [reason, setReason] = useState("");
  const [answers, setAnswers] = useState<Answers>({});
  const [phone, setPhone] = useState("");
  const [address, setAddress] = useState("");
  const [mode, setMode] = useState<"auto" | "choose">("auto");
  const [showErrors, setShowErrors] = useState(false);

  const answered = questions.every((q) => answers[q.id] !== undefined);
  const anyYes = questions.some((q) => answers[q.id] === true);
  const problems = {
    reason: reason.trim().length < 5 ? "Describe the problem in a few words." : "",
    checklist: !answered ? "Answer every safety question." : "",
    place: picker.place ? "" : "Add your location first.",
    phone: PHONE.test(phone.trim()) ? "" : "Enter a phone number the doctor can call.",
    address: address.trim().length < 5 ? "Write your address in words." : "",
  };
  const ready = !anyYes && Object.values(problems).every((p) => p === "");
  const busy = request.pending !== null;

  function check(): HomeVisitCheck | null {
    if (!picker.place) return null;
    return {
      reason: reason.trim(),
      checklist: Object.fromEntries(questions.map((q) => [q.id, answers[q.id] === true])),
      location: picker.place,
    };
  }

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (busy) return;
    setShowErrors(true);
    const payload = check();
    if (!ready || !payload) return;
    if (mode === "choose") void request.search(payload);
    else void request.send({ ...payload, mode: "auto", phone: phone.trim(), address_text: address.trim() });
  }

  function choose(doctorId: number) {
    const payload = check();
    if (!payload || busy) return;
    void request.send({ ...payload, mode: "choose", doctor_id: doctorId, phone: phone.trim(), address_text: address.trim() });
  }

  if (request.choices) {
    return <DoctorChoices choices={request.choices} sending={request.pending === "send"} disabled={busy} onChoose={choose} onBack={request.clearChoices} />;
  }

  return (
    <form className="space-y-6" onSubmit={submit} noValidate aria-label="Home visit request">
      <TextAreaField
        label="What is the problem?"
        rows={3}
        maxLength={1000}
        placeholder="For example: fever and a cold since two days"
        hint="Only for problems that are not an emergency. A doctor offered this request will read it."
        value={reason}
        onChange={(e) => setReason(e.target.value)}
        error={showErrors ? problems.reason : ""}
      />
      <SafetyChecklist questions={questions} answers={answers} notice={notice} onChange={(id, value) => setAnswers((a) => ({ ...a, [id]: value }))} />
      {showErrors && problems.checklist ? <p className="-mt-3 text-xs font-medium text-rose-600">{problems.checklist}</p> : null}
      <LocationPicker picker={picker} />
      {showErrors && problems.place ? <p className="-mt-3 text-xs font-medium text-rose-600">{problems.place}</p> : null}
      <TextField
        label="Phone number"
        type="tel"
        autoComplete="tel"
        placeholder="03XX XXXXXXX"
        hint="Only the doctor who accepts sees it."
        value={phone}
        onChange={(e) => setPhone(e.target.value)}
        error={showErrors ? problems.phone : ""}
      />
      <TextAreaField
        label="Your address in words"
        autoComplete="street-address"
        rows={3}
        maxLength={300}
        placeholder="House, street, area, city"
        hint="Typed, never looked up on a map. Shown to the doctor only after they accept."
        value={address}
        onChange={(e) => setAddress(e.target.value)}
        error={showErrors ? problems.address : ""}
      />
      <fieldset>
        <legend className="text-sm font-medium text-slate-700">Who should come?</legend>
        <div className="mt-2 space-y-2">
          {[
            { value: "auto" as const, label: "Match me with a doctor automatically", hint: "The best-matched doctor is asked first, with 2 minutes to answer, then the next, up to 5 doctors." },
            { value: "choose" as const, label: "I will choose a doctor", hint: "You see doctors near you and send the request to one." },
          ].map((option) => (
            <label key={option.value} className="flex items-start gap-3 rounded-control border border-line px-3 py-3 text-sm">
              <input type="radio" name="mode" checked={mode === option.value} onChange={() => setMode(option.value)} className="mt-1 h-4 w-4 accent-[#2563EB]" />
              <span className="min-w-0">
                <span className="block font-medium text-ink">{option.label}</span>
                <span className="block text-xs leading-5 text-ink-muted">{option.hint}</span>
              </span>
            </label>
          ))}
        </div>
      </fieldset>
      {request.error ? <Alert tone="error">{request.error}</Alert> : null}
      <Button
        type="submit"
        size="lg"
        loading={busy}
        disabled={anyYes}
        icon={mode === "choose" ? <Search className="h-4 w-4" /> : <Send className="h-4 w-4" />}
        className="w-full"
      >
        {request.pending === "search" ? "Searching..." : request.pending === "send" ? "Sending..." : mode === "choose" ? "Find doctors near me" : "Send request"}
      </Button>
      <p className="text-xs leading-5 text-ink-muted">
        Advisory only. Nothing here is a diagnosis, and a home visit is not an ambulance service.
      </p>
    </form>
  );
}
