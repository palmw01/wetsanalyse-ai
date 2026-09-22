"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState, type ReactNode } from "react";

import { AppSidebar } from "@/components/werkplek/AppSidebar";
import { MobieleTopbar } from "@/components/werkplek/MobieleTopbar";
import { ChevronOmlaag } from "@/components/ui/Icoon";
import { SkipLink, HOOFDINHOUD_ID } from "@/components/ui/SkipLink";

/** De paginaschil om één annotatie: sidebar (met de mobiele drawer), een kop met de weg terug naar
 *  het overzicht, en het hoofdgebied. Gedeeld door `/annotaties/<slug>` en `/annotaties/node`, zodat
 *  een bronnode-annotatie op eigen benen er net zo uitziet als een artikeldocument. */
export function AnnotatiePaginaSchil({ titel, werkplekHref, onFout, children }: {
  titel: string;
  /** Knop "Openen in de werkplek"; weglaten als er geen werkplek-ingang voor deze annotatie is. */
  werkplekHref?: string;
  onFout?: (melding: string) => void;
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
          onFout={onFout ?? (() => {})}
          drawerOpen={drawerOpen}
          onDrawerSluit={() => setDrawerOpen(false)}
        />

        <main id={HOOFDINHOUD_ID} tabIndex={-1} className="flex min-w-0 flex-1 flex-col bg-paper">
          <MobieleTopbar titel={titel} onOpenSidebar={() => setDrawerOpen(true)} />
          {/* Zelfde afweging als de kop van het artefact hieronder: wrappen in plaats van de titel
              laten wegdrukken door een knop die niet mag krimpen. */}
          <div className="flex shrink-0 flex-wrap items-center gap-x-3 gap-y-2 border-b border-line px-5 py-3 lg:pt-[max(0.75rem,env(safe-area-inset-top))]">
            <div className="min-w-0 flex-1 basis-56">
              <Link
                href="/annotaties"
                className="focus-ring inline-flex items-center gap-1 rounded text-xs text-muted transition-colors hover:text-ink"
              >
                <ChevronOmlaag className="rotate-90" /> Alle annotaties
              </Link>
              <p className="truncate text-sm font-medium text-lint">{titel}</p>
            </div>
            {werkplekHref && (
              <Link
                href={werkplekHref}
                className="focus-ring ml-auto inline-flex min-h-[24px] shrink-0 items-center rounded-full border border-line px-2.5 py-0.5 text-[11px] font-medium text-lint transition-colors hover:bg-surface coarse:min-h-[44px]"
              >
                Openen in de werkplek
              </Link>
            )}
          </div>
          {children}
        </main>
      </div>
    </div>
  );
}
