"use client";

import { useEffect, useState } from "react";

import { api } from "@/lib/api";

const POLL_MS = 60_000;

/** How many notifications the signed-in user has not read; checked now and every minute. */
export function useUnreadCount(signedIn: boolean) {
  const [count, setCount] = useState(0);
  useEffect(() => {
    if (!signedIn) return;
    let current = true;
    const check = () =>
      api
        .notifications({ limit: 1 })
        .then((page) => current && setCount(page.unread))
        .catch(() => undefined); // a missed check just tries again next minute
    void check();
    const timer = window.setInterval(check, POLL_MS);
    return () => {
      current = false;
      window.clearInterval(timer);
    };
  }, [signedIn]);
  return signedIn ? count : 0;
}
