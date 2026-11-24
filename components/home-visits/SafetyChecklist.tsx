import { PhoneCall } from "lucide-react";

import { Alert } from "@/components/ui/alert";

export type Answers = Record<string, boolean | undefined>;

/**
 * The fixed emergency questions. Every one needs an answer; a "yes" stops the request on the spot (the server
 * enforces it too) and shows the 1122 notice.
 */
export function SafetyChecklist({
  questions,
  answers,
  onChange,
  notice,
}: {
  questions: Array<{ id: string; question: string }>;
  answers: Answers;
  onChange: (id: string, value: boolean) => void;
  notice: string;
}) {
  const yes = questions.some((q) => answers[q.id] === true);
  return (
    <fieldset className="min-w-0">
      <legend className="text-sm font-medium text-slate-700">Safety questions</legend>
      <p className="mt-1 text-xs text-ink-muted">
        Home visits are only for problems that are not an emergency. Answer every question for the person who needs the doctor.
      </p>
      <ul className="mt-3 space-y-3">
        {questions.map((q) => (
          <li key={q.id}>
            <fieldset className="rounded-control border border-line bg-surface-soft px-3 py-3">
              <legend className="px-1 text-sm leading-6 text-ink">{q.question}</legend>
              <div className="mt-1 flex gap-5">
                {[
                  { label: "Yes", value: true },
                  { label: "No", value: false },
                ].map((option) => (
                  <label key={option.label} className="inline-flex min-h-[32px] items-center gap-2 text-sm text-slate-700">
                    <input
                      type="radio"
                      name={q.id}
                      checked={answers[q.id] === option.value}
                      onChange={() => onChange(q.id, option.value)}
                      className="h-4 w-4 accent-[#2563EB]"
                    />
                    {option.label}
                  </label>
                ))}
              </div>
            </fieldset>
          </li>
        ))}
      </ul>
      {yes ? (
        <Alert tone="error" className="mt-3" title="This may be an emergency">
          <span className="inline-flex items-start gap-2">
            <PhoneCall className="mt-1 h-4 w-4 flex-shrink-0" aria-hidden />
            {notice} A home visit is not the right help for this.
          </span>
        </Alert>
      ) : null}
    </fieldset>
  );
}
