import { Alert } from "@/components/ui/alert";

export type NoticeState = { tone: "success" | "error"; text: string } | null;

/** The result of the last save, shown under a form. */
export function Notice({ state }: { state: NoticeState }) {
  return state ? <Alert tone={state.tone}>{state.text}</Alert> : null;
}
