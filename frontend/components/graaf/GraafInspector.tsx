"use client";

import { useState } from "react";
import { ChevronOmlaag, Kruis, Richten } from "@/components/ui/Icoon";
import { LIFECYCLE_LABEL } from "@/lib/annotatie";
import { jasStyle } from "@/lib/jas";
import { SOORT_LABEL, type GraafKnoop, type Hoofdactie, type RelatieGroepNaam, type RelatieRegel } from "@/lib/samenhang";
import type { Lifecycle } from "@/lib/types";
import type { WaaromBron } from "@/lib/waarom";
import { WaaromUitklap } from "@/components/annotaties/WaaromUitklap";

const ICOON = "focus-ring flex h-8 w-8 items-center justify-center rounded-lg text-muted hover:bg-surface hover:text-ink coarse:h-11 coarse:w-11";
const TEKSTKNOP = "focus-ring rounded px-1 py-1 text-xs text-lint underline-offset-2 hover:underline coarse:min-h-11";
const HOOFD = "focus-ring inline-flex min-h-9 items-center justify-center rounded-button bg-accent px-3.5 text-xs font-medium text-paper transition-colors hover:bg-accent-soft disabled:opacity-50 coarse:min-h-11";
const ZICHTBAAR_PER_GROEP = 5;

/** Wat is dit? Eén kaart per gekozen knoop: naam, inhoud, één hoofdactie, rustige extra's en de
 *  relaties per soort. Zonder selectie een korte stand van zaken. Smal (zijpaneel) staat de kaart
 *  onder de graaf en is hij in te klappen tot kop + hoofdactie, zodat het canvas zijn hoogte houdt. */
export function GraafInspector({ knoop, element, laadElement, ongedekt, hoofdactie, uitgeklapt, verborgenBuren, laadt, groepen, samenvatting, smal,
  onCentreer, onSluit, onHoofdactie, onVraag, onVerbindingen, onKies }: {
  knoop?: GraafKnoop;
  /** Het element achter een markeringsknoop, voor de Waarom-uitklap; de graaf zelf draagt het spoor niet. */
  element?: WaaromBron;
  /** Voor een markering buiten de weergave van het paneel: het element op aanvraag. */
  laadElement?: () => Promise<WaaromBron>;
  /** De zinsdelen zonder detectortreffer van deze bronknoop (de laag Dekking). */
  ongedekt?: string[];
  hoofdactie: Hoofdactie; uitgeklapt: boolean; verborgenBuren: number; laadt: boolean;
  groepen: { naam: RelatieGroepNaam; regels: RelatieRegel[] }[];
  samenvatting: { leden: number; markeringen: number; verwijzingen: number };
  smal: boolean;
  onCentreer: () => void; onSluit: () => void; onHoofdactie: () => void; onVraag?: () => void;
  onVerbindingen: () => void; onKies: (id: string) => void;
}) {
  const [klapstand, setIngeklapt] = useState(true);
  // Inklappen bestaat alleen smal; vergroot je, dan staan de details altijd open.
  const ingeklapt = smal && klapstand;
  // "Alle n tonen" geldt per knoop en groep, niet voor de volgende knoop die je kiest.
  const [allesOpen, setAllesOpen] = useState<Record<string, boolean>>({});
  if (!knoop) return <div className="p-4 text-xs text-muted" data-testid="graaf-detail">
    <p><span className="text-ink">{samenvatting.leden}</span> leden en onderdelen <span className="px-1 text-faint">·</span>
      <span className="text-ink">{samenvatting.markeringen}</span> markeringen <span className="px-1 text-faint">·</span>
      <span className="text-ink">{samenvatting.verwijzingen}</span> verwijzingen</p>
    <p className="mt-1 text-faint">Kies een knoop in de graaf, of zoek er een.</p>
  </div>;

  const hoofdLabel = hoofdactie === "tekst" ? "Toon in tekst"
    : hoofdactie === "openen" ? (laadt ? "Laden…" : "Artikel openen") : "";
  // De schakelaar is dezelfde handeling als dubbelklikken; weg als er niets te tonen of te verbergen is.
  const schakelaar = uitgeklapt || verborgenBuren > 0;

  return <div className="flex min-h-0 flex-col" data-testid="graaf-detail">
    <div className="flex items-start gap-2 px-4 pb-2 pt-3">
      <div className="min-w-0 flex-1">
        <p className="flex items-center gap-1.5 text-[10px] font-semibold uppercase tracking-wide text-faint">
          <span className="h-2 w-2 shrink-0 rounded-full" style={{ background: knoop.kleur }} />
          {SOORT_LABEL[knoop.soort]}{knoop.rand && knoop.soort !== "extern" ? " · buiten dit artikel" : ""}
        </p>
        <h3 className="mt-0.5 text-sm font-semibold leading-snug text-ink">{knoop.label}</h3>
      </div>
      <button type="button" className={ICOON} onClick={onCentreer} aria-label="Centreren" title="Centreren"><Richten /></button>
      {smal && <button type="button" className={ICOON} onClick={() => setIngeklapt((v) => !v)} aria-expanded={!ingeklapt}
        aria-label={ingeklapt ? "Details tonen" : "Details inklappen"} title={ingeklapt ? "Details tonen" : "Details inklappen"}>
        <ChevronOmlaag className={ingeklapt ? "rotate-180" : ""} /></button>}
      <button type="button" className={ICOON} onClick={onSluit} aria-label="Selectie opheffen" title="Selectie opheffen"><Kruis /></button>
    </div>

    <div className="flex flex-wrap items-center gap-x-3 gap-y-2 px-4 pb-3">
      {hoofdactie && <button type="button" className={HOOFD} onClick={onHoofdactie} disabled={laadt}>{hoofdLabel}</button>}
      {onVraag && <button type="button" className={TEKSTKNOP} onClick={onVraag}>Vraag Lex</button>}
      {schakelaar && <button type="button" role="switch" aria-checked={uitgeklapt} onClick={onVerbindingen}
        className="focus-ring inline-flex items-center gap-2 rounded px-1 py-1 text-xs text-ink coarse:min-h-11">
        <span aria-hidden="true" className={`relative h-4 w-7 rounded-full transition-colors ${uitgeklapt ? "bg-accent" : "bg-line"}`}>
          <span className={`absolute top-0.5 h-3 w-3 rounded-full bg-paper shadow transition-all ${uitgeklapt ? "left-3.5" : "left-0.5"}`} />
        </span>
        Verbindingen tonen{!uitgeklapt && verborgenBuren > 0 ? ` (${verborgenBuren})` : ""}
      </button>}
    </div>

    {!ingeklapt && <div className="min-h-0 space-y-3 overflow-y-auto border-t border-line px-4 py-3">
      {knoop.soort === "markering" && <div className="flex flex-wrap items-center gap-2">
        <span className={`inline-block rounded border px-2 py-0.5 text-[11px] ${jasStyle(knoop.klasse)}`}>{knoop.klasse}</span>
        {knoop.lifecycle && <span className="text-[11px] text-muted">{LIFECYCLE_LABEL[knoop.lifecycle as Lifecycle] || knoop.lifecycle}</span>}
      </div>}
      {knoop.soort === "markering" && (element || laadElement) && <WaaromUitklap key={knoop.id} el={element} laad={laadElement} />}
      {knoop.tekst && knoop.soort !== "markering" && <p className="border-l-2 border-lint/20 pl-3 text-xs leading-relaxed text-muted">{knoop.tekst}</p>}
      {ongedekt && ongedekt.length > 0 && (() => {
        const sleutel = `${knoop.id}|dekking`;
        const toon = allesOpen[sleutel] ? ongedekt : ongedekt.slice(0, ZICHTBAAR_PER_GROEP);
        return <div data-testid="graaf-dekking">
          <p className="text-[11px] font-semibold text-muted">Zonder detectortreffer <span className="font-normal text-faint">({ongedekt.length})</span></p>
          <ul className="mt-1 space-y-0.5 pl-4">
            {toon.map((t, i) => <li key={i} className="text-xs text-muted">“{t}”</li>)}
          </ul>
          {ongedekt.length > ZICHTBAAR_PER_GROEP && !allesOpen[sleutel] && <button type="button" className={`${TEKSTKNOP} ml-4`}
            onClick={() => setAllesOpen((a) => ({ ...a, [sleutel]: true }))}>Alle {ongedekt.length} tonen</button>}
          <p className="mt-1 pl-4 text-[10px] text-faint">Een meting van de detectoren, geen oordeel. Markeren doe je in de tekst.</p>
        </div>;
      })()}
      {knoop.soort === "extern" && <p className="text-xs text-muted">Deze bepaling staat niet in de kennisgraaf; alleen de verwijzing ernaar is bekend.</p>}
      {groepen.map(({ naam, regels }) => {
        const sleutel = `${knoop.id}|${naam}`;
        const toon = allesOpen[sleutel] ? regels : regels.slice(0, ZICHTBAAR_PER_GROEP);
        return <details key={naam} open={regels.length <= ZICHTBAAR_PER_GROEP} className="group">
          <summary className="focus-ring flex cursor-pointer list-none items-center gap-1.5 rounded py-0.5 text-[11px] font-semibold text-muted">
            <ChevronOmlaag className="-rotate-90 transition-transform group-open:rotate-0" />{naam} <span className="font-normal text-faint">({regels.length})</span>
          </summary>
          <ul className="mt-1 space-y-0.5 pl-4">
            {toon.map(({ knoop: ander, anker_tekst }) => <li key={ander.id}>
              <button type="button" onClick={() => onKies(ander.id)} className="focus-ring flex w-full items-baseline gap-2 rounded px-1 py-0.5 text-left text-xs hover:bg-surface">
                <span className="mt-1 h-2 w-2 shrink-0 self-start rounded-full" style={{ background: ander.kleur }} />
                <span className="truncate text-lint">{ander.label}</span>
                {anker_tekst && <span className="truncate text-faint">“{anker_tekst}”</span>}
              </button>
            </li>)}
          </ul>
          {regels.length > ZICHTBAAR_PER_GROEP && !allesOpen[sleutel] && <button type="button" className={`${TEKSTKNOP} ml-4`}
            onClick={() => setAllesOpen((a) => ({ ...a, [sleutel]: true }))}>Alle {regels.length} tonen</button>}
        </details>;
      })}
    </div>}
  </div>;
}
