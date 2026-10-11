import { PageLoader } from "@/components/ui/spinner";

/** Shown by Next.js while a route segment loads. */
export default function Loading() {
  return <PageLoader message="Loading..." />;
}
