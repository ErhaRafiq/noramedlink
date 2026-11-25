"use client";

import { useState } from "react";
import { Siren } from "lucide-react";

import { Button } from "@/components/ui/button";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";

/**
 * "This is an emergency": the patient is told to call 1122 or go to the nearest emergency department and the
 * request ends. Available at every live step, with a confirmation, because it cannot be undone.
 */
export function EmergencyReferral({ busy, onRefer }: { busy: boolean; onRefer: () => void }) {
  const [open, setOpen] = useState(false);
  return (
    <>
      <Button variant="danger" size="sm" icon={<Siren className="h-4 w-4" />} onClick={() => setOpen(true)} disabled={busy}>
        This is an emergency
      </Button>
      <ConfirmDialog
        open={open}
        title="Tell the patient to get emergency care?"
        description="The patient will be told to call 1122 or go to the nearest emergency department, and this request will end. Use it when you judge the problem is an emergency."
        confirmLabel="Refer to emergency care"
        pendingLabel="Referring..."
        pending={busy}
        onConfirm={() => {
          setOpen(false);
          onRefer();
        }}
        onCancel={() => setOpen(false)}
      />
    </>
  );
}
