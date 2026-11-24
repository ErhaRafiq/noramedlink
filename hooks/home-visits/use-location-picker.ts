"use client";

import { useCallback, useState } from "react";

import { accuracyLabel, getBrowserLocation, parseCoordinates } from "@/lib/location";
import type { HomeVisitPlace } from "@/lib/types";

/**
 * The patient's place: tapped from the browser ("Use my current location") or typed by hand. A request cannot be
 * sent without one. On a denied, unavailable or timed-out location the typed fields are shown with a plain message.
 */
export function useLocationPicker() {
  const [place, setPlace] = useState<HomeVisitPlace | null>(null);
  const [locating, setLocating] = useState(false);
  const [message, setMessage] = useState("");
  const [typing, setTyping] = useState(false);
  const [latitude, setLatitude] = useState("");
  const [longitude, setLongitude] = useState("");
  const [typedError, setTypedError] = useState("");

  const locate = useCallback(async () => {
    setLocating(true);
    setMessage("");
    const result = await getBrowserLocation();
    setLocating(false);
    if (result.ok) {
      setPlace(result.place);
      setTyping(false);
      setTypedError("");
      setMessage("");
    } else {
      setMessage(result.message);
      setTyping(true);
    }
  }, []);

  /** Uses the typed numbers as the place, or says what is wrong with them. */
  const applyTyped = useCallback(() => {
    const parsed = parseCoordinates(latitude, longitude);
    if (!parsed.ok) {
      setTypedError(parsed.message);
      return;
    }
    setTypedError("");
    setPlace({ latitude: parsed.latitude, longitude: parsed.longitude, accuracy_m: null, source: "manual" });
  }, [latitude, longitude]);

  const clear = useCallback(() => {
    setPlace(null);
    setMessage("");
  }, []);

  return {
    place,
    locating,
    message,
    typing,
    showTyping: () => setTyping(true),
    latitude,
    longitude,
    setLatitude,
    setLongitude,
    typedError,
    locate,
    applyTyped,
    clear,
    summary: place ? (place.source === "device" ? `Location found, ${accuracyLabel(place.accuracy_m)}.` : "Location typed by you.") : "",
  };
}
