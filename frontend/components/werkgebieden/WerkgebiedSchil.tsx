"use client";

import { useRouter } from "next/navigation";
import { useState, type ReactNode } from "react";

import { AppSidebar } from "@/components/werkplek/AppSidebar";
import { MobieleTopbar } from "@/components/werkplek/MobieleTopbar";
import { SkipLink, HOOFDINHOUD_ID } from "@/components/ui/SkipLink";

/** De paginaschil van de werkgebieden: sidebar (met de mobiele drawer), topbar en een scrollend
 *  hoofdgebied – dezelfde opbouw als het annotatie-overzicht. */
export function WerkgebiedSchil({ titel, onFout, breed = false, bewaak = (doe) => doe(), children }: {
  titel: string;
  onFout: (melding: string) => void;
  /** Laat een navigatie vanuit de sidebar eerst langs de vraag over niet-bewaarde wijzigingen gaan
   *  (`useOnbewaardBewaker`); links vangt die zelf. */
  bewaak?: (doe: () => void) => void;
  /** Ruimer dan de leesbreedte: voor de begrippen (drie kolommen) en de graaf. */
  breed?: boolean;
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
          onNieuw={() => bewaak(() => router.push("/workbench"))}
          onOpen={(id) => bewaak(() => router.push(`/workbench?gesprek=${encodeURIComponent(id)}`))}
          onFout={onFout}
          drawerOpen={drawerOpen}
          onDrawerSluit={() => setDrawerOpen(false)}
        />
        <div className="flex min-w-0 flex-1 flex-col">
          <MobieleTopbar titel={titel} onOpenSidebar={() => setDrawerOpen(true)} />
          <main id={HOOFDINHOUD_ID} tabIndex={-1} className="min-w-0 flex-1 overflow-y-auto">
            <div className={`mx-auto w-full ${breed ? "max-w-7xl" : "max-w-5xl"} px-5 py-6 pb-[max(1.5rem,env(safe-area-inset-bottom))]`}>
              {children}
            </div>
          </main>
        </div>
      </div>
    </div>
  );
}
