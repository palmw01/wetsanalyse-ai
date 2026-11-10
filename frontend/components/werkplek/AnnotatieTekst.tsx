"use client";

import { useMemo } from "react";

import { WettekstBlok } from "@/components/wettekst/WettekstBlok";
import { bronVan } from "@/lib/annotatie";
import type { SegmentPlek } from "@/lib/annotatieNodeAdapter";
import { klasseLabel } from "@/lib/jas";
import { markeringVan, type Markeerbaar } from "@/lib/markeerlaag";
import { lidUitOffset, type LidRegel } from "@/lib/selectie";

/** De wettekst van een annotatie (ontdubbelen PR 4): dezelfde weergave als het leesvenster (`WettekstBlok`), met de
 *  markeerlaag erop – de ene gekozen markering, de zinsdelen zonder detectortreffer en het zelf selecteren. Geen eigen
 *  tekstweergave meer (`app/wettekst.test.ts`); deze schil voegt alleen de twee regels erboven toe.
 *
 *  De tekst toont hoogstens één markering: de gekozen. Twee markeringen kunnen niet op dezelfde tekst liggen, dus alles
 *  tegelijk kleuren is onleesbaar en onvolledig; de reviewlijst is de ingang. */
export function AnnotatieTekst({ regels, plekken, elementen, actiefId, onKies, onSelectie, ongedekt = [], toonOngedekt = true, onToonOngedekt }: {
  /** De artikeltekst als regels mét hun lidnummer (`regelsVan`): de samengestelde bron waarin alles rekent. */
  regels: LidRegel[];
  /** Waar elk segment in die bron begint (`nodeBronVan`). */
  plekken: readonly SegmentPlek[];
  elementen: Markeerbaar[];
  actiefId?: string;
  onKies?: (id?: string) => void;
  /** De jurist heeft tekst geselecteerd om zelf te markeren. Weglaten = alleen-lezen. */
  onSelectie?: (sel: {
    fragment: string; start: number; eind: number; lid: string; bron: string;
    x: number; y: number; yBoven: number;
  }) => void;
  /** Zinsdelen waar geen detector iets vond (de dekkingsmeting), in de offsets van de bron. */
  ongedekt?: { start: number; eind: number }[];
  toonOngedekt?: boolean;
  onToonOngedekt?: (toon: boolean) => void;
}) {
  const bron = useMemo(() => bronVan(regels), [regels]);
  const markering = useMemo(() => markeringVan(bron, elementen, actiefId), [bron, elementen, actiefId]);
  const gekozen = actiefId ? elementen.find((e) => e.id === actiefId) : undefined;
  const meld = (start: number, eind: number, plek: { x: number; y: number; yBoven: number }) => onSelectie?.({
    fragment: bron.slice(start, eind), start, eind, lid: lidUitOffset(regels, start), bron, ...plek,
  });

  return (
    <div data-tour="wettekst">
      {elementen.length > 0 && (
        <div className="mb-3 flex items-center justify-between gap-3 rounded-kaart bg-lint/5 px-3 py-2 text-xs text-muted">
          {gekozen ? (
            <>
              <span><span className="font-medium text-ink">{klasseLabel(gekozen.klasse)}</span> in beeld</span>
              <button type="button" onClick={() => onKies?.(undefined)}
                className="focus-ring shrink-0 rounded font-medium text-lint underline underline-offset-2 hover:no-underline">
                Verbergen
              </button>
            </>
          ) : (
            <span>Kies een markering in de lijst om te zien waar hij staat, of selecteer tekst om zelf te markeren.</span>
          )}
        </div>
      )}
      {ongedekt.length > 0 && (
        // Het vangnet: zinsdelen waar geen enkele detector iets vond. Een meting, geen oordeel – dus geen aandachtskleur op
        // de balk, alleen de stippellijn in de tekst. Bij nul: niets, ook geen groen vinkje.
        <div className="mb-3 flex items-center justify-between gap-3 px-3 text-xs text-muted" data-testid="dekking-balk">
          <span title="Een meting van de detectoren: hier is niets gezien. Dat zegt niet dat er iets ontbreekt.">
            {ongedekt.length} {ongedekt.length === 1 ? "zinsdeel" : "zinsdelen"} zonder treffer van een detector
            {toonOngedekt && onSelectie ? " – klik om zelf te markeren" : ""}
          </span>
          {onToonOngedekt && (
            <button type="button" aria-pressed={toonOngedekt} onClick={() => onToonOngedekt(!toonOngedekt)}
              className="focus-ring shrink-0 rounded font-medium text-lint underline underline-offset-2 hover:no-underline">
              {toonOngedekt ? "Verbergen" : "Tonen"}
            </button>
          )}
        </div>
      )}
      <WettekstBlok groot laag={{
        bron, plekken, markering, onKies,
        ongedekt: toonOngedekt ? ongedekt : [],
        onKiesOngedekt: onSelectie ? (deel, el) => {
          const r = el.getBoundingClientRect();
          meld(deel.start, deel.eind, { x: r.left + r.width / 2, y: r.bottom, yBoven: r.top });
        } : undefined,
        onSelectie: onSelectie ? ({ start, eind, ...plek }) => meld(start, eind, plek) : undefined,
      }} />
    </div>
  );
}
