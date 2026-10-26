"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { Mapje, Meer } from "@/components/ui/Icoon";
import { Popover } from "@/components/ui/Popover";
import { GesprekActies } from "@/components/werkplek/GesprekActies";
import { haalWerkgebied } from "@/lib/api";

/** De kop van het gesprek (spoor G1, naar de mock-up): de titel, waar het gesprek bij hoort – een
 *  werkgebied of *Los gesprek* – en het menu met archiveren, verplaatsen en verwijderen. Eén
 *  chatvenster voor elk gesprek; het werkgebied bepaalt alleen welke context Lex meekrijgt.
 *
 *  Vervangt de werkgebiedbalk met *Verlaten*: uit de context stappen heet nu *Naar recente
 *  gesprekken* en maakt het gesprek ook echt los, zodat het niet bij het volgende openen weer in
 *  het werkgebied staat. De naam laden mag mislukken: dan staat er het id. */
export function ChatKop({
  titel, gesprekId, werkgebiedId, gearchiveerd = false, onArchiveer, onVerplaats, onVerwijder, onBronnen,
}: {
  titel: string;
  /** `null` = een nieuw gesprek dat nog geen beurt had: er valt nog niets te archiveren. */
  gesprekId: string | null;
  werkgebiedId: string | null;
  gearchiveerd?: boolean;
  onArchiveer: (gearchiveerd: boolean) => void;
  onVerplaats: (werkgebiedId: string) => void;
  onVerwijder: () => void;
  /** De bronnen van het werkgebied naast het gesprek openen (spoor G4). */
  onBronnen?: () => void;
}) {
  // De naam hoort bij het id waarvoor hij geladen is: na een verplaatsing staat er tot het laden "…",
  // niet de naam van het vorige werkgebied.
  const [geladen, setGeladen] = useState<{ id: string; naam: string } | null>(null);
  const naam = geladen && geladen.id === werkgebiedId ? geladen.naam : null;
  useEffect(() => {
    if (!werkgebiedId) return;
    let levend = true;
    haalWerkgebied(werkgebiedId)
      .then((w) => levend && setGeladen({ id: werkgebiedId, naam: w.naam }))
      .catch(() => levend && setGeladen({ id: werkgebiedId, naam: "" }));
    return () => { levend = false; };
  }, [werkgebiedId]);

  return (
    <div
      data-chatkop
      {...(werkgebiedId ? { "data-werkgebied": werkgebiedId } : {})}
      className="flex shrink-0 items-center gap-3 border-b border-line px-4 py-2"
    >
      <div className="min-w-0 flex-1">
        {/* Op een smal scherm staat de titel al in de mobiele topbar. */}
        <h1 className="hidden truncate text-sm font-semibold text-ink lg:block">{titel}</h1>
        <p className="truncate text-xs text-muted">
          {werkgebiedId ? (
            <>
              Werkgebied:{" "}
              <Link
                href={`/werkgebieden/${encodeURIComponent(werkgebiedId)}`}
                className="focus-ring rounded font-medium text-lint underline-offset-2 hover:underline"
              >
                {naam || (naam === null ? "…" : werkgebiedId)}
              </Link>
              {" "}· Lex werkt binnen deze analyse
            </>
          ) : (
            "Los gesprek · Recente gesprekken"
          )}
          {gearchiveerd && " · Gearchiveerd"}
        </p>
      </div>
      {werkgebiedId && onBronnen && (
        <button type="button" onClick={onBronnen} data-chatkop-bronnen
          className="focus-ring inline-flex min-h-[32px] items-center gap-1.5 rounded-button border border-line px-3 text-xs font-medium text-lint hover:bg-surface coarse:min-h-[44px]">
          Bronnen
        </button>
      )}
      {werkgebiedId && (
        <Link
          href={`/werkgebieden/${encodeURIComponent(werkgebiedId)}`}
          className="focus-ring hidden min-h-[32px] items-center gap-1.5 rounded-button border border-line px-3 text-xs font-medium text-lint hover:bg-surface sm:inline-flex"
        >
          <Mapje /> Werkgebied
        </Link>
      )}
      {gesprekId && (
        <Popover
          ariaLabel="Gesprek"
          className="w-64 rounded-kaart border border-line bg-paper shadow-kaart"
          trigger={(open, toggle) => (
            <button
              type="button"
              onClick={toggle}
              aria-expanded={open}
              aria-label="Acties voor dit gesprek"
              className="focus-ring inline-flex min-h-[32px] min-w-[32px] items-center justify-center rounded-button border border-line text-muted hover:bg-surface hover:text-lint coarse:min-h-[44px] coarse:min-w-[44px]"
            >
              <Meer />
            </button>
          )}
        >
          {(sluit) => (
            <GesprekActies
              werkgebiedId={werkgebiedId ?? ""}
              gearchiveerd={gearchiveerd}
              onArchiveer={onArchiveer}
              onVerplaats={onVerplaats}
              onVerwijder={onVerwijder}
              onKlaar={sluit}
            />
          )}
        </Popover>
      )}
    </div>
  );
}
