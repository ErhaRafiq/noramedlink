import type { ReactNode } from "react";
import { LocateFixed, MapPinOff, X } from "lucide-react";

import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { TextField } from "@/components/ui/field";
import type { useLocationPicker } from "@/hooks/home-visits/use-location-picker";
import { APPROXIMATE_OVER_M, coordinatesLabel } from "@/lib/location";

type Picker = ReturnType<typeof useLocationPicker>;

/**
 * "Use my current location" (browser location only, no map), with the typed-coordinates fallback.
 * The explanation comes before the button, so the browser's permission prompt is expected.
 */
export function LocationPicker({
  picker,
  legend = "Where is the visit?",
  intro,
  missing = "A location is needed before a request can be sent.",
}: {
  picker: Picker;
  legend?: string;
  intro?: ReactNode;
  missing?: string;
}) {
  return (
    <fieldset className="min-w-0">
      <legend className="text-sm font-medium text-slate-700">{legend}</legend>
      <p className="mt-1 text-xs leading-5 text-ink-muted">
        {intro ?? (
          <>
            Tap the button and your browser will ask to share your location. We use it only to find doctors near you. The
            doctor who accepts sees it; nobody else does. Your device needs a secure connection (HTTPS) or localhost for
            this to work, and on a computer the place can be approximate.
          </>
        )}
      </p>
      <div className="mt-3 flex flex-col gap-2 sm:flex-row sm:items-center">
        <Button
          variant="secondary"
          loading={picker.locating}
          icon={<LocateFixed className="h-4 w-4" />}
          onClick={() => void picker.locate()}
          className="w-full sm:w-auto"
        >
          {picker.locating ? "Finding your location..." : picker.place?.source === "device" ? "Update my location" : "Use my current location"}
        </Button>
        {picker.place && !picker.locating ? (
          <Button variant="ghost" size="sm" icon={<X className="h-4 w-4" />} onClick={picker.clear}>
            Clear location
          </Button>
        ) : null}
        {!picker.typing ? (
          <button type="button" onClick={picker.showTyping} className="text-left text-xs font-medium text-brand-blue underline-offset-2 hover:underline">
            Type latitude and longitude instead
          </button>
        ) : null}
      </div>
      {picker.message ? (
        <Alert tone="warning" className="mt-3">
          <span className="inline-flex items-start gap-2">
            <MapPinOff className="mt-1 h-4 w-4 flex-shrink-0" aria-hidden />
            {picker.message}
          </span>
        </Alert>
      ) : null}
      {picker.typing ? (
        <div className="mt-3 grid gap-3 sm:grid-cols-[1fr_1fr_auto] sm:items-end">
          <TextField label="Latitude" inputMode="decimal" placeholder="33.6938" value={picker.latitude} onChange={(e) => picker.setLatitude(e.target.value)} wrapperClassName="min-w-0" />
          <TextField label="Longitude" inputMode="decimal" placeholder="73.0129" value={picker.longitude} onChange={(e) => picker.setLongitude(e.target.value)} wrapperClassName="min-w-0" />
          <Button variant="secondary" onClick={picker.applyTyped}>
            Use these numbers
          </Button>
        </div>
      ) : null}
      {picker.typedError ? <p className="mt-2 text-xs font-medium text-rose-600">{picker.typedError}</p> : null}
      {picker.locating ? (
        <p role="status" className="mt-3 text-sm text-ink-muted">
          Waiting for your browser. If it asks for permission, choose Allow. This can take up to 30 seconds on a computer.
        </p>
      ) : picker.place ? (
        <div role="status" className="mt-3 text-sm">
          <p className="font-medium text-emerald-700">{picker.summary}</p>
          <p className="mt-0.5 break-words text-xs text-ink-muted">
            Coordinates used: {coordinatesLabel(picker.place.latitude, picker.place.longitude)}
          </p>
          {picker.place.accuracy_m !== null && picker.place.accuracy_m > APPROXIMATE_OVER_M ? (
            <p className="mt-1 text-xs font-medium text-amber-700">
              This place is only approximate (a computer often guesses from its network). If it is far from where you are, type your
              latitude and longitude instead, or try again on a phone.
            </p>
          ) : null}
        </div>
      ) : (
        <p className="mt-3 text-xs text-ink-muted">{missing}</p>
      )}
    </fieldset>
  );
}
