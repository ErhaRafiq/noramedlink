import { useId } from "react";
import type { ComponentProps, ReactNode } from "react";

import { cn } from "@/lib/cn";

type FieldShellProps = {
  label: ReactNode;
  hint?: ReactNode;
  error?: ReactNode;
  className?: string;
  children: (ids: { inputId: string; describedBy: string | undefined; invalid: boolean }) => ReactNode;
};

/** Label + control + hint/error, with the ids wired for screen readers. */
function FieldShell({ label, hint, error, className, children }: FieldShellProps) {
  const inputId = useId();
  const hintId = `${inputId}-hint`;
  const errorId = `${inputId}-error`;
  const describedBy = [error ? errorId : null, hint ? hintId : null].filter(Boolean).join(" ") || undefined;

  return (
    <div className={className}>
      <label htmlFor={inputId} className="text-sm font-medium text-slate-700">
        {label}
      </label>
      <div className="mt-1.5">{children({ inputId, describedBy, invalid: Boolean(error) })}</div>
      {error ? (
        <p id={errorId} className="mt-1.5 text-xs font-medium text-rose-600">
          {error}
        </p>
      ) : hint ? (
        <p id={hintId} className="mt-1.5 text-xs text-ink-muted">
          {hint}
        </p>
      ) : null}
    </div>
  );
}

type SharedProps = { label: ReactNode; hint?: ReactNode; error?: ReactNode; wrapperClassName?: string };

const invalidClass = "border-rose-300 focus:border-rose-500";

export function TextField({ label, hint, error, wrapperClassName, className, ...props }: SharedProps & ComponentProps<"input">) {
  return (
    <FieldShell label={label} hint={hint} error={error} className={wrapperClassName}>
      {({ inputId, describedBy, invalid }) => (
        <input
          id={inputId}
          aria-describedby={describedBy}
          aria-invalid={invalid || undefined}
          className={cn("form-field", invalid && invalidClass, className)}
          {...props}
        />
      )}
    </FieldShell>
  );
}

export function TextAreaField({ label, hint, error, wrapperClassName, className, ...props }: SharedProps & ComponentProps<"textarea">) {
  return (
    <FieldShell label={label} hint={hint} error={error} className={wrapperClassName}>
      {({ inputId, describedBy, invalid }) => (
        <textarea
          id={inputId}
          aria-describedby={describedBy}
          aria-invalid={invalid || undefined}
          className={cn("form-field min-h-24", invalid && invalidClass, className)}
          {...props}
        />
      )}
    </FieldShell>
  );
}

export function SelectField({ label, hint, error, wrapperClassName, className, children, ...props }: SharedProps & ComponentProps<"select">) {
  return (
    <FieldShell label={label} hint={hint} error={error} className={wrapperClassName}>
      {({ inputId, describedBy, invalid }) => (
        <select
          id={inputId}
          aria-describedby={describedBy}
          aria-invalid={invalid || undefined}
          className={cn("form-field", invalid && invalidClass, className)}
          {...props}
        >
          {children}
        </select>
      )}
    </FieldShell>
  );
}
