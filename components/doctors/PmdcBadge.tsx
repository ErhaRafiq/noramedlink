import { BadgeCheck } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/cn";
import { formatDateTime } from "@/lib/datetime";

/**
 * "PMDC verified": the doctor's registration number was found ACTIVE on the PMDC public register under
 * their name (or an administrator confirmed it). It says the registration was checked, not that the doctor
 * is good, and it is shown only when it is true.
 */
export function PmdcBadge({ verified, checkedAt, className }: { verified: boolean; checkedAt?: string | null; className?: string }) {
  if (!verified) return null;
  const when = checkedAt ? ` on ${formatDateTime(checkedAt)}` : "";
  return (
    <span title={`Registration number checked on the PMDC public register${when}`} className={cn("inline-flex", className)}>
      <Badge tone="success">
        <BadgeCheck className="mr-1 inline h-3 w-3" aria-hidden />
        PMDC verified
      </Badge>
    </span>
  );
}
