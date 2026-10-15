"use client";

import { useEffect, useId, useState } from "react";
import { Search } from "lucide-react";

import { api } from "@/lib/api";
import { cn } from "@/lib/cn";
import type { MedicineOption } from "@/lib/types";
import { useDebouncedValue } from "@/hooks/use-debounced-value";

/** Type a generic or brand name (misspellings are matched approximately), then pick one. */
export function MedicineSearch({ onPick }: { onPick: (option: MedicineOption) => void }) {
  const [query, setQuery] = useState("");
  const [result, setResult] = useState<{ query: string; options: MedicineOption[]; error: string | null }>({
    query: "",
    options: [],
    error: null,
  });
  const [active, setActive] = useState(0);
  const debounced = useDebouncedValue(query.trim(), 250);
  const listId = useId();
  const inputId = useId();

  useEffect(() => {
    if (debounced.length < 2) return;
    const controller = new AbortController();
    api
      .searchMedicines(debounced, { signal: controller.signal })
      .then((options) => setResult({ query: debounced, options, error: null }))
      .catch((error: unknown) => {
        if (!controller.signal.aborted) setResult({ query: debounced, options: [], error: error instanceof Error ? error.message : "Search failed." });
      });
    return () => controller.abort();
  }, [debounced]);

  const showing = query.trim().length >= 2 && result.query === debounced;
  const options = showing ? result.options : [];

  function pick(option: MedicineOption) {
    onPick(option);
    setQuery("");
    setActive(0);
  }

  return (
    <div className="relative">
      <label htmlFor={inputId} className="mb-1.5 block text-sm font-medium text-ink">
        Add a medicine
      </label>
      <div className="relative">
        <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" aria-hidden />
        <input
          id={inputId}
          role="combobox"
          aria-expanded={options.length > 0}
          aria-controls={listId}
          aria-autocomplete="list"
          aria-activedescendant={options[active] ? `${listId}-${active}` : undefined}
          className="form-field pl-9"
          placeholder="Generic or brand name, e.g. Glucophage"
          value={query}
          onChange={(event) => {
            setQuery(event.target.value);
            setActive(0);
          }}
          onKeyDown={(event) => {
            if (!options.length) return;
            if (event.key === "ArrowDown") {
              event.preventDefault();
              setActive((i) => Math.min(i + 1, options.length - 1));
            } else if (event.key === "ArrowUp") {
              event.preventDefault();
              setActive((i) => Math.max(i - 1, 0));
            } else if (event.key === "Enter") {
              event.preventDefault();
              pick(options[active]);
            } else if (event.key === "Escape") {
              setQuery("");
            }
          }}
        />
      </div>
      {showing && result.error ? <p className="mt-1 text-xs text-rose-700">{result.error}</p> : null}
      {showing && !result.error && options.length === 0 ? (
        <p className="mt-1 text-xs text-ink-muted">
          Not in the knowledge base.{" "}
          <button
            type="button"
            className="font-semibold text-brand-blue hover:underline"
            onClick={() => pick({ name: query.trim(), generic: query.trim(), brand: null, classes: [], match: 0 })}
          >
            Add &ldquo;{query.trim()}&rdquo; anyway
          </button>{" "}
          (it can&apos;t be checked: &ldquo;no data&rdquo;).
        </p>
      ) : null}
      {options.length > 0 ? (
        <ul id={listId} role="listbox" className="absolute z-20 mt-1 max-h-72 w-full overflow-auto rounded-control border border-line bg-white py-1 shadow-card">
          {options.map((option, index) => (
            <li
              key={`${option.generic}-${option.brand ?? option.name}`}
              id={`${listId}-${index}`}
              role="option"
              aria-selected={index === active}
              onMouseDown={(event) => {
                event.preventDefault();
                pick(option);
              }}
              className={cn("cursor-pointer px-3 py-2 text-sm", index === active ? "bg-blue-50" : "hover:bg-surface-soft")}
            >
              <span className="font-medium text-ink">{option.brand ?? option.name}</span>
              {option.brand ? <span className="text-ink-muted"> · {option.generic}</span> : null}
              <span className="block text-xs text-ink-muted">{option.classes.join(", ")}</span>
            </li>
          ))}
        </ul>
      ) : null}
    </div>
  );
}
