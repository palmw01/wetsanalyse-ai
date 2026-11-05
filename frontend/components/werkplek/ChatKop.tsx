"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { Mapje } from "@/components/ui/Icoon";
import { MeerKnop } from "@/components/ui/MeerMenu";
import { MENU_PANEEL } from "@/components/ui/Menu";
import { Popover } from "@/components/ui/Popover";
import { BewerkVoet, useBewerken } from "@/components/ui/Bewerkbaar";
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
  titel, gesprekId, werkgebiedId, gearchiveerd = false, onArchiveer, onVerplaats, onVerwijder, onBronnen, onHernoem,
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
  /** Hernoemen ter plekke (4 nov 2026), zoals in de lijst van gesprekken. */
  onHernoem?: (titel: string) => Promise<unknown> | void;
}) {
  const bw = useBewerken({ begin: titel, opslaan: async (t: string) => { if (t.trim()) await onHernoem?.(t.trim()); } });
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
        {/* Op een smal scherm staat de titel al in de mobiele topbar; hernoemen gebeurt ter plekke. */}
        {bw.open ? (
          <div data-bewerken className="py-1">
            <input autoFocus aria-label="Naam van het gesprek" value={bw.concept} onChange={(e) => bw.zet(e.target.value)}
              onKeyDown={bw.toetsen(true)}
              className="w-full rounded-field border border-lint bg-paper px-2 py-1 text-sm text-ink focus:outline-none" />
            <BewerkVoet onAnnuleer={bw.annuleer} onOpslaan={() => void bw.slaOp()} bezig={bw.bezig}
              gewijzigd={bw.gewijzigd && !!bw.concept.trim()} fout={bw.fout} />
          </div>
        ) : (
          <h1 className="hidden truncate text-sm font-semibold text-ink lg:block">{titel}</h1>
        )}
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
          className="focus-ring inline-flex min-h-[32px] items-center gap-1.5 rounded-knop border border-line px-3 text-xs font-medium text-lint hover:bg-surface coarse:min-h-[44px]">
          Bronnen
        </button>
      )}
      {werkgebiedId && (
        <Link
          href={`/werkgebieden/${encodeURIComponent(werkgebiedId)}`}
          className="focus-ring hidden min-h-[32px] items-center gap-1.5 rounded-knop border border-line px-3 text-xs font-medium text-lint hover:bg-surface sm:inline-flex"
        >
          <Mapje /> Werkgebied
        </Link>
      )}
      {gesprekId && (
        <Popover
          ariaLabel="Gesprek"
          className={`w-64 ${MENU_PANEEL}`}
          trigger={(open, toggle) => <MeerKnop label="Acties voor dit gesprek" open={open} onClick={toggle} maat="sm" />}
        >
          {(sluit) => (
            <GesprekActies
              werkgebiedId={werkgebiedId ?? ""}
              gearchiveerd={gearchiveerd}
              onArchiveer={onArchiveer}
              onVerplaats={onVerplaats}
              onVerwijder={onVerwijder}
              {...(onHernoem ? { onHernoem: bw.start } : {})}
              onKlaar={sluit}
            />
          )}
        </Popover>
      )}
    </div>
  );
}
