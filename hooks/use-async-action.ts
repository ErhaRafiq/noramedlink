"use client";

import { useCallback, useRef, useState } from "react";

/**
 * Runs an async action with a pending flag and ignores repeat calls while one is
 * running, so a double click cannot submit a form twice.
 */
export function useAsyncAction<Args extends unknown[], Result>(action: (...args: Args) => Promise<Result>) {
  const [pending, setPending] = useState(false);
  const runningRef = useRef(false);

  const run = useCallback(
    async (...args: Args): Promise<Result | undefined> => {
      if (runningRef.current) return undefined;
      runningRef.current = true;
      setPending(true);
      try {
        return await action(...args);
      } finally {
        runningRef.current = false;
        setPending(false);
      }
    },
    [action],
  );

  return { run, pending };
}
