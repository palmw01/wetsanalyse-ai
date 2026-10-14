"use client";

import { useRouter } from "next/navigation";
import { useState, type ReactNode } from "react";

import { AppSidebar } from "@/components/werkplek/AppSidebar";
import { MobieleTopbar } from "@/components/werkplek/MobieleTopbar";
import { SkipLink, HOOFDINHOUD_ID } from "@/components/ui/SkipLink";

/** De paginaschil van de werkgebieden: sidebar (met de mobiele drawer), topbar en een scrollend
 *  hoofdgebied – dezelfde opbouw als het annotatie-overzicht. */
export function WerkgebiedSchil({ titel, onFout, children }: {
  titel: string;
  onFout: (melding: string) => void;
  children: ReactNode;
}) {
  const router = useRouter();
  // Onder `lg` is de sidebar een drawer; zonder deze state stond je hier zonder navigatie.
  const [drawerOpen, setDrawerOpen] = useState(false);

  return (
    <div className="relative flex h-screen h-[100dvh] flex-col overflow-hidden bg-surface">
      <SkipLink />
      <div className="flex min-h-0 flex-1">
        <AppSidebar
          activeId={null}
          onNieuw={() => router.push("/workbench")}
          onOpen={(id) => router.push(`/workbench?gesprek=${encodeURIComponent(id)}`)}
          onFout={onFout}
          drawerOpen={drawerOpen}
          onDrawerSluit={() => setDrawerOpen(false)}
        />
        <div className="flex min-w-0 flex-1 flex-col">
          <MobieleTopbar titel={titel} onOpenSidebar={() => setDrawerOpen(true)} />
          <main id={HOOFDINHOUD_ID} tabIndex={-1} className="min-w-0 flex-1 overflow-y-auto">
            <div className="mx-auto w-full max-w-5xl px-5 py-6 pb-[max(1.5rem,env(safe-area-inset-bottom))]">
              {children}
            </div>
          </main>
        </div>
      </div>
    </div>
  );
}
