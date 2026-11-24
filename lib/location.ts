import type { HomeVisitPlace } from "@/lib/types";

/**
 * Where the patient is, for a home visit. Browser location only (navigator.geolocation): no map, geocoding or
 * routing service, no key. It needs HTTPS or localhost, and on a computer it can be approximate.
 */

export type LocationFailure = "unsupported" | "insecure" | "denied" | "unavailable" | "timeout";

/** Under this many metres the place is treated as precise; over it the patient is warned it is approximate. */
export const APPROXIMATE_OVER_M = 1000;

export const LOCATION_FAILURE_MESSAGE: Record<LocationFailure, string> = {
  unsupported: "This browser cannot share your location. Type your latitude and longitude instead.",
  insecure: "Your browser only shares location on a secure page (HTTPS) or on localhost. Open the site that way, or type your latitude and longitude.",
  denied:
    "Location access is blocked for this site. Click the lock or location icon next to the address bar, allow location, then tap the button again. Or type your latitude and longitude.",
  unavailable: "Your device could not work out where you are. Try again, or type your latitude and longitude.",
  timeout: "Finding your location took too long. Try again, or type your latitude and longitude.",
};

export type LocationResult = { ok: true; place: HomeVisitPlace } | { ok: false; reason: LocationFailure; message: string };

const failure = (reason: LocationFailure): LocationResult => ({ ok: false, reason, message: LOCATION_FAILURE_MESSAGE[reason] });

type Attempt = { position: GeolocationPosition } | { error: GeolocationPositionError };

function ask(options: PositionOptions): Promise<Attempt> {
  return new Promise((resolve) => {
    navigator.geolocation.getCurrentPosition(
      (position) => resolve({ position }),
      (error) => resolve({ error }),
      options,
    );
  });
}

const reasonOf = (error: GeolocationPositionError): LocationFailure => (error.code === 1 ? "denied" : error.code === 3 ? "timeout" : "unavailable");

/**
 * Asks the browser for the current position. It never rejects: a failure is a result with a plain message.
 * First a fresh, precise reading (GPS or Wi-Fi) for up to 10 seconds; if that times out or the device cannot
 * give one (common on a computer), a looser reading is tried before giving up. A refusal is final.
 */
export async function getBrowserLocation(): Promise<LocationResult> {
  if (typeof navigator === "undefined" || !("geolocation" in navigator)) return failure("unsupported");
  if (typeof window !== "undefined" && window.isSecureContext === false) return failure("insecure");
  let attempt = await ask({ enableHighAccuracy: true, timeout: 10_000, maximumAge: 0 });
  if ("error" in attempt && attempt.error.code !== 1) {
    attempt = await ask({ enableHighAccuracy: false, timeout: 20_000, maximumAge: 60_000 });
  }
  if ("error" in attempt) return failure(reasonOf(attempt.error));
  const { coords } = attempt.position;
  return {
    ok: true,
    place: {
      latitude: coords.latitude,
      longitude: coords.longitude,
      accuracy_m: Number.isFinite(coords.accuracy) ? coords.accuracy : null,
      source: "device",
    },
  };
}

export type CoordinateResult = { ok: true; latitude: number; longitude: number } | { ok: false; message: string };

/** Typed coordinates, checked like the server does: latitude -90 to 90, longitude -180 to 180. */
export function parseCoordinates(latitude: string, longitude: string): CoordinateResult {
  const lat = latitude.trim() === "" ? NaN : Number(latitude);
  const lon = longitude.trim() === "" ? NaN : Number(longitude);
  if (!Number.isFinite(lat) || !Number.isFinite(lon)) return { ok: false, message: "Enter the latitude and longitude as numbers." };
  if (lat < -90 || lat > 90) return { ok: false, message: "Latitude must be between -90 and 90." };
  if (lon < -180 || lon > 180) return { ok: false, message: "Longitude must be between -180 and 180." };
  return { ok: true, latitude: lat, longitude: lon };
}

/** "33.69380, 73.01290": the numbers the request will use, so the patient can check them. */
export function coordinatesLabel(latitude: number, longitude: number): string {
  return `${latitude.toFixed(5)}, ${longitude.toFixed(5)}`;
}

/** "accurate to about 120 m", or "typed by you" when there is no accuracy. */
export function accuracyLabel(accuracyM: number | null): string {
  if (accuracyM === null) return "Typed by you";
  const metres = Math.round(accuracyM);
  return metres < 1000 ? `accurate to about ${metres} m` : `accurate to about ${(metres / 1000).toFixed(1)} km`;
}
