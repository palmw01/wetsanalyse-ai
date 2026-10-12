"use client";

import { useState } from "react";
import { ChevronOmlaag, Kruis, Richten } from "@/components/ui/Icoon";
import { LIFECYCLE_LABEL } from "@/lib/annotatie";
import { jasStyle } from "@/lib/jas";
import { SOORT_LABEL, tellingTekst, type Hoofdactie, type RelatieGroepNaam, type RelatieRegel, type Telling } from "@/lib/graaf/bediening";
import type { GraafModel, KnoopData } from "@/lib/graaf/model";
import { eigenKleur } from "@/lib/graaf/stijl";
import type { Lifecycle } from "@/lib/types";
import type { NodeElement } from "@/lib/annotatieNode";
import { WaaromUitklap } from "@/components/annotaties/WaaromUitklap";
import { verwijzingTekst, verwijzingVoor, type KnoopInfo } from "@/lib/graaf/knoopinfo";
import { KnoopFeiten } from "./KnoopFeiten";
import { KnoopTekst } from "./KnoopTekst";
import type { DetailStand } from "./useKnoopDetail";

const ICOON = "focus-ring flex h-8 w-8 items-center justify-center rounded-lg text-muted hover:bg-surface hover:text-ink coarse:h-11 coarse:w-11";
const TEKSTKNOP = "focus-ring rounded px-1 py-1 text-xs text-lint underline-offset-2 hover:underline coarse:min-h-11";
const HOOFD = "focus-ring inline-flex min-h-9 items-center justify-center rounded-button bg-accent px-3.5 text-xs font-medium text-paper transition-colors hover:bg-accent-soft disabled:opacity-50 coarse:min-h-11";
const ZICHTBAAR_PER_GROEP = 5;

/** Wat is dit? Eén kaart per gekozen knoop, meteen helemaal open: naam, de wettekst met de markeringen
 *  erin, bij een markering alles wat de reviewkaart ook weet (alleen lezen), en de relaties per soort.
 *  Je blijft in de graaf: een markering in de tekst of een relatie kiezen doet dat in de graaf, en naar
 *  de tekst gaan is een rustige link, geen hoofdknop. Zonder keuze: wat het antwoord noemt.
 *
 *  Smal (zijpaneel) staat de kaart onder de graaf, met een eigen scroll, en is hij in te klappen. De
 *  aanroeper geeft hem per keuze een `key`: een nieuwe keuze begint open en bovenaan. */
export function GraafInspector({ model, id, detail, info, element, ongedekt, hoofdactie, laadt, groepen, telling, doelen, smal,
  onCentreer, onSluit, onHoofdactie, onVraag, onKies }: {
  model: GraafModel;
  id: string | null;
  /** De wettekst van de gekozen bepaling, of voor een markering die van haar anker. */
  detail: DetailStand;
  /** Wat de kennisgraaf over de knoop weet (`GET knoop`); `null` bij een markering of klasse. */
  info: KnoopInfo | "laden" | "fout" | null;
  /** Het element achter een markeringsknoop: toelichting, alternatieven, spoor. */
  element?: NodeElement | "laden" | "fout";
  /** Wat het antwoord noemt, voor de inspector zonder keuze. */
  doelen: string[];
  /** De zinsdelen zonder detectortreffer van deze bronknoop (de laag Dekking). */
  ongedekt?: string[];
  hoofdactie: Hoofdactie; laadt: boolean;
  groepen: { naam: RelatieGroepNaam; regels: RelatieRegel[] }[];
  telling: Telling;
  smal: boolean;
  onCentreer: () => void; onSluit: () => void; onHoofdactie: () => void; onVraag?: () => void;
  onKies: (id: string) => void;
}) {
  const [klapstand, setIngeklapt] = useState(false);
  // Inklappen bestaat alleen smal; vergroot je, dan staan de details altijd open.
  const ingeklapt = smal && klapstand;
  // "Alle n tonen" geldt per knoop en groep, niet voor de volgende knoop die je kiest.
  const [allesOpen, setAllesOpen] = useState<Record<string, boolean>>({});
  const knoop: (KnoopData & { id: string }) | undefined = id && model.hasNode(id) ? { ...model.getNodeAttributes(id), id } : undefined;
  if (!knoop) {
    const genoemd = doelen.filter((d) => model.hasNode(d));
    return <div className="min-h-0 overflow-y-auto p-4 text-xs text-muted" data-testid="graaf-detail">
      {genoemd.length > 0 && <>
        <p className="text-[10px] font-semibold uppercase tracking-wide text-faint">Dit antwoord</p>
        <ul className="mb-3 mt-1 space-y-0.5">
          {genoemd.map((d) => { const a = model.getNodeAttributes(d); const n = markeringenOp(model, d); return <li key={d}>
            <button type="button" onClick={() => onKies(d)} className="focus-ring flex w-full items-baseline gap-2 rounded px-1 py-0.5 text-left text-xs hover:bg-surface coarse:min-h-11">
              <span className="mt-1 h-2 w-2 shrink-0 self-start rounded-full border border-black/10" style={{ background: eigenKleur(a) }} />
              <span className="truncate text-lint">{a.naam}</span>
              {n > 0 && <span className="shrink-0 text-faint">{n === 1 ? "1 markering" : `${n} markeringen`}</span>}
            </button>
          </li>; })}
        </ul>
      </>}
      <p className="text-ink">{tellingTekst(telling) || "Nog niets geladen."}</p>
      <p className="mt-1 text-faint">Klik een knoop of een markering aan: hier zie je meteen alles erover. Klik op de achtergrond om terug te gaan naar het antwoord.</p>
    </div>;
  }

  // De gevulde knop alleen voor wat in de graaf blijft; naar de tekst of een ander artikel is een link.
  const tekstLabel = hoofdactie === "tekst" ? (knoop.soort === "markering" ? "Beoordeel in de tekst" : "Bekijk in de tekst")
    : hoofdactie === "wissel" ? "Open in het paneel" : "";
  const el = typeof element === "object" ? element : undefined;

  return <div className="flex min-h-0 flex-col" data-testid="graaf-detail">
    <div className="flex items-start gap-2 px-4 pb-2 pt-3">
      <div className="min-w-0 flex-1">
        <p className="flex items-center gap-1.5 text-[10px] font-semibold uppercase tracking-wide text-faint">
          <span className="h-2 w-2 shrink-0 rounded-full border border-black/10" style={{ background: eigenKleur(knoop) }} />
          {SOORT_LABEL[knoop.soort]}{knoop.rand && knoop.soort !== "extern" ? " · buiten wat geladen is" : ""}
        </p>
        <h3 className="mt-0.5 text-sm font-semibold leading-snug text-ink">{knoop.naam}</h3>
      </div>
      <button type="button" className={ICOON} onClick={onCentreer} aria-label="Centreren" title="Centreren"><Richten /></button>
      {smal && <button type="button" className={ICOON} onClick={() => setIngeklapt((v) => !v)} aria-expanded={!ingeklapt}
        aria-label={ingeklapt ? "Details tonen" : "Details inklappen"} title={ingeklapt ? "Details tonen" : "Details inklappen"}>
        <ChevronOmlaag className={ingeklapt ? "rotate-180" : ""} /></button>}
      <button type="button" className={ICOON} onClick={onSluit} aria-label="Selectie opheffen" title="Selectie opheffen"><Kruis /></button>
    </div>

    {(hoofdactie || onVraag) && <div className="flex flex-wrap items-center gap-x-3 gap-y-2 px-4 pb-3">
      {hoofdactie === "laden" && <button type="button" className={HOOFD} onClick={onHoofdactie} disabled={laadt}>{laadt ? "Laden…" : "In de graaf laden"}</button>}
      {tekstLabel && <button type="button" className={TEKSTKNOP} onClick={onHoofdactie}>{tekstLabel}</button>}
      {onVraag && <button type="button" className={TEKSTKNOP} onClick={onVraag}>Vraag Lex</button>}
    </div>}

    {!ingeklapt && <div className="min-h-0 space-y-3 overflow-y-auto border-t border-line px-4 py-3">
      {knoop.soort === "markering" && <div className="flex flex-wrap items-center gap-2">
        <span className={`inline-block rounded border px-2 py-0.5 text-[11px] ${jasStyle(knoop.klasse)}`}>{knoop.klasse}</span>
        {knoop.lifecycle && <span className="text-[11px] text-muted">{LIFECYCLE_LABEL[knoop.lifecycle as Lifecycle] || knoop.lifecycle}</span>}
        {/* Een onbeoordeeld voorstel zegt zijn herkomst al ("voorstel van Lex"). */}
        {knoop.herkomst && !(knoop.herkomst !== "mens" && knoop.lifecycle === "voorgesteld") && <span className="rounded-full border border-line px-2 py-0.5 text-[11px] text-muted">
          {knoop.herkomst === "mens" ? "door een jurist" : "voorstel van Lex"}</span>}
        {knoop.aandacht === "geel" && <span className="rounded-full border border-aandacht-geel-rand bg-aandacht-geel-bg px-2 py-0.5 text-[11px] text-aandacht-geel-tekst">Keuze voor jou</span>}
        {knoop.aandacht === "groen" && <span className="rounded-full border border-aandacht-groen-rand bg-aandacht-groen-bg px-2 py-0.5 text-[11px] text-aandacht-groen-tekst">Bevestigd door review</span>}
      </div>}
      {knoop.soort === "markering" && el && <MarkeringDetail el={el} />}
      <Wettekst detail={detail} knoop={knoop} gekozen={knoop.soort === "markering" ? knoop.element_id : undefined}
        kiesbaar={(e) => model.hasNode(`element:${e}`)} onKies={(e) => onKies(`element:${e}`)} />
      {knoop.soort === "markering" && element === "laden" && <p className="text-xs text-faint">Details ophalen…</p>}
      {knoop.soort === "markering" && element === "fout" && <p className="text-xs text-faint">De details van deze markering konden niet worden opgehaald.</p>}
      {knoop.soort === "markering" && el && <WaaromUitklap key={knoop.id} el={el} beginOpen />}
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
      {info && <KnoopFeiten info={info} opKaart={(iri) => model.hasNode(iri)} onKies={onKies} />}
      {groepen.map(({ naam, regels }) => {
        // Een lijn draagt alleen de ankertekst; soort, doel en betrouwbaarheid staan op de verwijzing.
        const richting = naam === "Verwijst naar" ? "uit" : naam === "Wordt verwezen door" ? "in" : undefined;
        const verwijzingen = richting && info && typeof info === "object" ? info.verwijzingen : [];
        const sleutel = `${knoop.id}|${naam}`;
        const toon = allesOpen[sleutel] ? regels : regels.slice(0, ZICHTBAAR_PER_GROEP);
        return <details key={naam} open={regels.length <= ZICHTBAAR_PER_GROEP} className="group">
          <summary className="focus-ring flex cursor-pointer list-none items-center gap-1.5 rounded py-0.5 text-[11px] font-semibold text-muted">
            <ChevronOmlaag className="-rotate-90 transition-transform group-open:rotate-0" />{naam} <span className="font-normal text-faint">({regels.length})</span>
          </summary>
          <ul className="mt-1 space-y-0.5 pl-4">
            {toon.map(({ id: ander, anker_tekst }) => { const a = model.getNodeAttributes(ander); return <li key={ander}>
              <button type="button" onClick={() => onKies(ander)} className="focus-ring flex w-full items-baseline gap-2 rounded px-1 py-0.5 text-left text-xs hover:bg-surface coarse:min-h-11">
                <span className="mt-1 h-2 w-2 shrink-0 self-start rounded-full border border-black/10" style={{ background: eigenKleur(a) }} />
                <span className="min-w-0">
                  <span className="flex items-baseline gap-2">
                    <span className="truncate text-lint">{a.naam}</span>
                    {anker_tekst && <span className="truncate text-faint">“{anker_tekst}”</span>}
                  </span>
                  {richting && (() => {
                    const v = verwijzingVoor(verwijzingen, richting, ander, anker_tekst);
                    if (!v) return null;
                    return <span className="mt-0.5 flex flex-wrap items-center gap-1.5 text-[10px] text-faint" data-testid="graaf-verwijzing">
                      {verwijzingTekst(v)}
                      {v.betrouwbaarheid === "laag" && <span className="rounded-full border border-aandacht-geel-rand bg-aandacht-geel-bg px-1.5 text-aandacht-geel-tekst">lage betrouwbaarheid</span>}
                    </span>;
                  })()}
                </span>
              </button>
            </li>; })}
          </ul>
          {regels.length > ZICHTBAAR_PER_GROEP && !allesOpen[sleutel] && <button type="button" className={`${TEKSTKNOP} ml-4`}
            onClick={() => setAllesOpen((a) => ({ ...a, [sleutel]: true }))}>Alle {regels.length} tonen</button>}
        </details>;
      })}
    </div>}
  </div>;
}

/** Hoeveel markeringen er op een bronknoop of iets daaronder liggen. */
function markeringenOp(g: GraafModel, id: string): number {
  let n = 0;
  const stapel = [id];
  while (stapel.length) {
    const x = stapel.pop()!;
    g.forEachInEdge(x, (_, a) => { if (a.soort === "markeert") n++; });
    g.forEachOutEdge(x, (_, a, __, doel) => { if (a.soort === "bevat") stapel.push(doel); });
  }
  return n;
}

/** De wettekst bij de keuze: met de markeringen erin als die er is, anders wat het model weet. */
function Wettekst({ detail, knoop, gekozen, kiesbaar, onKies }: {
  detail: DetailStand; knoop: KnoopData; gekozen?: string; kiesbaar: (elementId: string) => boolean; onKies: (elementId: string) => void;
}) {
  if (detail === "laden") return <p className="border-l-2 border-lint/20 pl-3 text-xs text-faint">Tekst ophalen…</p>;
  if (detail && detail !== "fout" && detail.segmenten.some((s) => s.tekst.trim())) {
    return <KnoopTekst segmenten={detail.segmenten} elementen={detail.elementen} gekozen={gekozen} kiesbaar={kiesbaar} onKies={onKies} />;
  }
  // Een markering zonder tekst eromheen: het fragment zelf, letterlijk.
  if (knoop.soort === "markering") return knoop.tekst ? <blockquote className="border-l-2 border-lint/20 pl-3 text-xs leading-relaxed text-ink">“{knoop.tekst}”</blockquote> : null;
  if (knoop.tekst) return <p className="border-l-2 border-lint/20 pl-3 text-xs leading-relaxed text-muted">{knoop.tekst}</p>;
  if (detail === "fout") return <p className="text-xs text-faint">De tekst kon niet worden opgehaald.</p>;
  return null;
}

/** Wat de reviewkaart over een markering weet, alleen lezen: toelichting, de uitleg van de review en
 *  de alternatieven. Beoordelen gebeurt in de tekst. */
function MarkeringDetail({ el }: { el: NodeElement }) {
  return <div className="space-y-2 text-xs" data-testid="graaf-markering">
    {el.toelichting && <p className="text-ink"><span className="font-semibold text-muted">Toelichting: </span>{el.toelichting}</p>}
    {el.review_uitleg && <p className="text-ink"><span className="font-semibold text-muted">Review: </span>{el.review_uitleg}</p>}
    {!!el.alternatieven?.length && <div>
      <p className="text-[11px] font-semibold text-muted">Alternatieven</p>
      <div className="mt-1 flex flex-wrap gap-1">
        {el.alternatieven.map((a) => <span key={a.klasse} title={a.motivatie || undefined}
          className={`inline-block rounded border px-1.5 py-0.5 text-[11px] ${jasStyle(a.klasse)}`}>{a.klasse}</span>)}
      </div>
    </div>}
  </div>;
}
