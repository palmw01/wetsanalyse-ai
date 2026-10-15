"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";

import { Dialog, type DialogVariant } from "@/components/ui/Dialog";
import { BegripVoorstellen } from "@/components/werkgebieden/BegripVoorstellen";
import { BronKandidaten } from "@/components/werkgebieden/BronKandidaten";
import { ARTEFACT_SOORT_LABEL, type WerkgebiedArtefact } from "@/lib/artefact";

const TAB: Record<WerkgebiedArtefact["soort"], string> = { begrippen: "begrippen", bronnen: "bronnen" };

/** Een artefact van een werkgebied in de werkplek, in dezelfde schil als een annotatie (een kolom naast
 *  de chat vanaf 1280px, anders een sheet):
 *
 *  - **begrippen** – de voorstellen van Lex (`BegripVoorstellen`), dezelfde inhoud als op de tab
 *    Begrippen. Een overgenomen begrip opent in het werkgebied: daar staan de kaart en de passages.
 *  - **bronnen** – de bepalingen die Lex vond (`BronKandidaten`), dezelfde inhoud als op de tab Bronnen.
 *
 *  Eén inhoud, twee schillen. */
export function WerkgebiedArtefactPaneel({ doel, variant = "side", onSluit }: {
  doel: WerkgebiedArtefact;
  variant?: DialogVariant;
  onSluit: () => void;
}) {
  const router = useRouter();
  const naarWerkgebied = `/werkgebieden/${encodeURIComponent(doel.werkgebied_id)}?tab=${TAB[doel.soort]}`;
  const soort = ARTEFACT_SOORT_LABEL[doel.soort];
  const titel = doel.titel || soort;
  return (
    <Dialog label={`${soort}: ${titel}`} variant={variant} onSluit={onSluit}>
      <div data-artefact data-artefact-soort={doel.soort} className="flex min-h-0 flex-1 flex-col">
        <div className="flex shrink-0 items-start gap-3 border-b border-line px-5 py-3.5 pt-[max(0.875rem,env(safe-area-inset-top))]">
          <div className="min-w-0 flex-1">
            <p className="text-xs text-muted">{soort} van Lex</p>
            <h2 className="truncate font-display text-base font-semibold text-lint">{titel}</h2>
            <Link href={naarWerkgebied} className="focus-ring text-xs font-medium text-lint underline-offset-2 hover:underline">
              Open het werkgebied
            </Link>
          </div>
          <button
            type="button"
            onClick={onSluit}
            aria-label="Sluiten"
            className="focus-ring -mr-1 shrink-0 rounded-kaart p-1.5 text-muted transition-colors hover:bg-surface hover:text-ink"
          >
            <svg viewBox="0 0 20 20" className="h-5 w-5" fill="none" stroke="currentColor" strokeWidth="1.6" aria-hidden="true">
              <path d="M5 5l10 10M15 5L5 15" strokeLinecap="round" />
            </svg>
          </button>
        </div>
        <div className="min-h-0 flex-1 overflow-y-auto px-5 py-4">
          {doel.soort === "begrippen" ? (
            <BegripVoorstellen
              id={doel.werkgebied_id}
              inklapbaar={false}
              onBegrip={(b) => router.push(`${naarWerkgebied}&begrip=${encodeURIComponent(b)}`)}
              // Er staat hier geen begrippenlijst naast die ververst moet worden.
              onGewijzigd={() => {}}
            />
          ) : (
            // Opnemen wijzigt het werkgebied; hier staat geen selectie naast die ververst moet worden.
            <BronKandidaten id={doel.werkgebied_id} onGewijzigd={() => {}} />
          )}
        </div>
      </div>
    </Dialog>
  );
}
