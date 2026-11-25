"use client";

import { useState, type FormEvent } from "react";
import { Home } from "lucide-react";

import { LocationPicker } from "@/components/home-visits/LocationPicker";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { TextField } from "@/components/ui/field";
import { SkeletonCard } from "@/components/ui/skeleton";
import { ErrorState } from "@/components/ui/spinner";
import { useHomeVisitSettings } from "@/hooks/home-visits/use-home-visit-settings";
import { useLocationPicker } from "@/hooks/home-visits/use-location-picker";
import { coordinatesLabel } from "@/lib/location";
import type { HomeVisitSettings as Settings } from "@/lib/types";

/** The doctor's home-visit switch, how far they travel, and the base location requests are measured from. */
export function HomeVisitSettings() {
  const { settings, error, retry, saving, save } = useHomeVisitSettings();
  if (error && !settings) return <ErrorState message={error} onRetry={retry} />;
  if (!settings) return <SkeletonCard lines={5} />;
  return <SettingsForm settings={settings} saving={saving} onSave={save} />;
}

function SettingsForm({
  settings,
  saving,
  onSave,
}: {
  settings: Settings;
  saving: boolean;
  onSave: (input: Pick<Settings, "enabled" | "radius_km" | "latitude" | "longitude">) => Promise<string | null>;
}) {
  const picker = useLocationPicker();
  const [enabled, setEnabled] = useState(settings.enabled);
  const [radius, setRadius] = useState(settings.radius_km === null ? "" : String(settings.radius_km));
  const [message, setMessage] = useState<{ tone: "success" | "error"; text: string } | null>(null);

  // A newly chosen place replaces the saved one; otherwise the saved base is kept.
  const latitude = picker.place?.latitude ?? settings.latitude;
  const longitude = picker.place?.longitude ?? settings.longitude;

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (saving) return;
    const km = radius.trim() === "" ? null : Number(radius);
    if (km !== null && (!Number.isFinite(km) || km < 1 || km > 50)) {
      setMessage({ tone: "error", text: "The service radius must be between 1 and 50 km." });
      return;
    }
    if (enabled && (km === null || latitude === null || longitude === null)) {
      setMessage({ tone: "error", text: "Set your base location and service radius before switching home visits on." });
      return;
    }
    const failed = await onSave({ enabled, radius_km: km, latitude, longitude });
    setMessage(failed ? { tone: "error", text: failed } : { tone: "success", text: "Home-visit settings saved." });
  }

  return (
    <Card id="home-visits" aria-labelledby="home-visit-settings-title">
      <p className="section-eyebrow">Home visits</p>
      <h2 id="home-visit-settings-title" className="mb-1 mt-1.5 flex items-center gap-2 text-lg font-semibold text-ink">
        <Home className="h-5 w-5 text-brand-blue" aria-hidden />
        Visiting patients at home
      </h2>
      <p className="mb-4 text-sm leading-6 text-ink-muted">
        When this is on, patients near your base location who need a non-emergency home visit can be offered to you. You
        choose whether to accept each one. Patients never see where your base is.
      </p>
      <form className="space-y-5" onSubmit={submit} noValidate aria-label="Home-visit settings">
        <label className="flex items-start gap-3 text-sm text-ink">
          <input type="checkbox" checked={enabled} onChange={(e) => setEnabled(e.target.checked)} className="mt-1 h-4 w-4 accent-[#2563EB]" />
          <span className="font-medium">I take home visits</span>
        </label>
        <TextField
          label="Service radius (km)"
          inputMode="decimal"
          placeholder="10"
          hint="How far from your base you will travel: 1 to 50 km, measured as a straight line."
          value={radius}
          onChange={(e) => setRadius(e.target.value)}
          wrapperClassName="max-w-xs"
        />
        <LocationPicker
          picker={picker}
          legend="Your base location"
          intro={
            <>
              Tap the button to use where you are now, or type your latitude and longitude. Requests are measured as a
              straight line from here. Your device needs HTTPS or localhost for the button to work, and on a computer the
              place can be approximate.
            </>
          }
          missing={latitude !== null ? "" : "No base location is saved yet."}
        />
        {!picker.place && latitude !== null && longitude !== null ? (
          <p className="text-sm text-ink">
            Saved base: <span className="font-medium">{coordinatesLabel(latitude, longitude)}</span>
          </p>
        ) : null}
        {message ? <Alert tone={message.tone}>{message.text}</Alert> : null}
        <Button type="submit" loading={saving}>
          {saving ? "Saving..." : "Save home-visit settings"}
        </Button>
      </form>
    </Card>
  );
}
