import type { Metadata } from "next";

import { SitePage } from "@/components/layout/SitePage";
import { SummarizeView } from "@/components/summarize/SummarizeView";

export const metadata: Metadata = {
  title: "Summarize a report",
  description: "Plain-language, advisory summaries of medical report text.",
};

export default function SummarizePage() {
  return (
    <SitePage>
      <SummarizeView />
    </SitePage>
  );
}
