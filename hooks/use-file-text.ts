"use client";

import { useCallback, useRef, useState } from "react";

import { api } from "@/lib/api";
import { MAX_UPLOAD_BYTES, shrinkLargeImage } from "@/lib/image";
import type { FileText } from "@/lib/types";

export type FileTextState =
  | { status: "idle" }
  | { status: "reading"; fileName: string }
  | { status: "done"; fileName: string; result: FileText }
  | { status: "error"; fileName: string; message: string };

/**
 * Reads the text out of one picked file (PDF, Word or a photo) on the server, which keeps nothing. A second
 * pick while one is being read is ignored, and a result that arrives after the person reset is dropped.
 */
export function useFileText(onText: (text: string) => void) {
  const [state, setState] = useState<FileTextState>({ status: "idle" });
  const latest = useRef(0);
  const busy = useRef(false);

  const read = useCallback(
    async (picked: File) => {
      if (busy.current) return;
      if (picked.size > MAX_UPLOAD_BYTES && !picked.type.startsWith("image/")) {
        setState({ status: "error", fileName: picked.name, message: "That file is over 10 MB. Choose a smaller one." });
        return;
      }
      busy.current = true;
      const mine = ++latest.current;
      setState({ status: "reading", fileName: picked.name });
      try {
        const file = await shrinkLargeImage(picked);
        if (file.size > MAX_UPLOAD_BYTES) throw new Error("That photo is over 10 MB even after shrinking. Try a smaller one.");
        const result = await api.readFileText(file);
        if (mine !== latest.current) return;
        onText(result.text);
        setState({ status: "done", fileName: picked.name, result });
      } catch (err) {
        if (mine !== latest.current) return;
        setState({ status: "error", fileName: picked.name, message: err instanceof Error ? err.message : "The file could not be read." });
      } finally {
        busy.current = false;
      }
    },
    [onText],
  );

  const reset = useCallback(() => {
    latest.current++;
    setState({ status: "idle" });
  }, []);

  return { state, read, reset };
}
