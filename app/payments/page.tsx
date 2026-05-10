import { Suspense } from "react";
import PaymentsClient from "./payments-client";

export default function PaymentsPage() {
  return (
    <Suspense
      fallback={
        <main className="app-shell px-4 py-8 sm:px-6 lg:px-8">
          <section className="mx-auto max-w-5xl">
            <div className="glass-card p-8 text-sm text-slate-600">
              Loading wallet checkout...
            </div>
          </section>
        </main>
      }
    >
      <PaymentsClient />
    </Suspense>
  );
}
