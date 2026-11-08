"use client";

// Het antwoord als sjabloon (ADR-008): vaste blokken, gewoon in de tekst van het gesprek. Geen kaart, geen achtergrond:
// een sjabloon is een vorm van antwoorden, geen artefact. Elk blok hoort bij één component, en een soort zonder
// component compileert niet (`BLOKKEN`). Wat Lex schreef staat onder een eigen kop; de rest komt uit de bron.

import Link from "next/link";

import { NogNietInWerking } from "@/components/bronnen/NogNietInWerking";
import { Citaat } from "@/components/ui/Citaat";
import { StatusLabel } from "@/components/ui/Lijst";
import { Vindplaats } from "./Vindplaats";
import { Markdown } from "@/components/werkplek/Markdown";
import { groepeerWettekst, type Antwoord as AntwoordData, type AntwoordBlok, type BlokSoort } from "@/lib/antwoord";
import { BRONTYPE_NAAM } from "@/lib/bronnen";
import { begripPad, generiekPad } from "@/lib/werkgebiedPaden";
import type { Bron } from "@/lib/types";

function Sectie({ kop, children }: { kop: string; children: React.ReactNode }) {
  return <section className="space-y-1.5"><h3 className="text-sm font-semibold text-lint">{kop}</h3>{children}</section>;
}

type Blok<S extends BlokSoort> = Extract<AntwoordBlok, { soort: S }>;
type Props<S extends BlokSoort> = { blok: Blok<S>; bronnen?: readonly Bron[]; nietLetterlijk?: readonly string[] };

const STATUS_TOON: Record<string, "groen" | "neutraal"> = { geaccordeerd: "groen" };

const BLOKKEN: { [S in BlokSoort]: (p: Props<S>) => React.ReactNode } = {
  definities: ({ blok }) => (
    <Sectie kop={blok.items.length === 1 ? "Wettelijke definitie" : "Wettelijke definities"}>
      <div className="space-y-3">
        {blok.items.map((d) => (
          <div key={d.vindplaats.iri} className="space-y-1">
            <Citaat>{d.tekst}</Citaat>
            <p className="text-xs text-muted"><Vindplaats vindplaats={d.vindplaats} />{d.bereik && <> · geldt voor „{d.bereik}”</>}</p>
          </div>
        ))}
      </div>
    </Sectie>
  ),
  begrippen: ({ blok }) => (
    <Sectie kop="Vastgelegd begrip">
      <p className="text-xs text-muted">Een analyse-uitkomst van juristen, geen wettelijke definitie.</p>
      <ul className="space-y-2">
        {blok.items.map((b) => (
          <li key={b.id} className="space-y-0.5">
            <p className="flex flex-wrap items-center gap-2">
              <Link href={b.werkgebied_id ? begripPad(b.werkgebied_id, b.id) : generiekPad(b.id)} className="focus-ring rounded font-medium text-lint underline underline-offset-2">{b.naam}</Link>
              <StatusLabel toon={STATUS_TOON[b.status] ?? "neutraal"} klein>{b.status}</StatusLabel>
              {b.herbeoordelen && <StatusLabel toon="geel" klein>herbeoordelen</StatusLabel>}
            </p>
            {b.definitie && <p>{b.definitie}</p>}
            {b.werkgebied && <p className="text-xs text-muted">Werkgebied {b.werkgebied}</p>}
          </li>
        ))}
      </ul>
    </Sectie>
  ),
  wettekst: ({ blok }) => (
    <Sectie kop="Wettekst">
      <div className="space-y-4">
        {groepeerWettekst(blok.items).map((g) => g.artikel ? (
          // Leden van één artikel onder één kop; elk lid houdt zijn eigen link (naast het gesprek, of naar de bron).
          <div key={g.artikel.iri} className="space-y-2" data-wettekst-artikel={g.artikel.iri}>
            <p className="text-xs font-medium text-muted"><Vindplaats vindplaats={g.artikel} /></p>
            {g.items.map(({ item: b, lid }) => (
              <div key={b.vindplaats.iri} className="space-y-1">
                {b.nog_niet_in_werking && <NogNietInWerking />}
                <p className="text-xs text-muted"><Vindplaats vindplaats={{ ...b.vindplaats, label: `lid ${lid}`, regeling: "" }} /></p>
                <Citaat>{b.tekst}</Citaat>
              </div>
            ))}
          </div>
        ) : g.items.map(({ item: b }) => (
          <div key={b.vindplaats.iri} className="space-y-1">{b.nog_niet_in_werking && <NogNietInWerking />}<Citaat>{b.tekst}</Citaat><p className="text-xs text-muted"><Vindplaats vindplaats={b.vindplaats} /></p></div>
        )))}
      </div>
    </Sectie>
  ),
  citaten: ({ blok, bronnen, nietLetterlijk }) => (
    <Sectie kop="Onderbouwing">
      <div className="space-y-3">
        {blok.items.map((c, i) => (
          <div key={`${c.vindplaats.iri}-${i}`} className="space-y-1">
            <Citaat>{c.tekst}</Citaat>
            <p className="text-xs text-muted"><Vindplaats vindplaats={c.vindplaats} /></p>
            {c.waarom && (
              <div data-door="lex">
                <p className="text-xs text-muted">Toelichting van Lex</p>
                <Markdown tekst={c.waarom} bronnen={bronnen} nietLetterlijk={nietLetterlijk} />
              </div>
            )}
          </div>
        ))}
      </div>
    </Sectie>
  ),
  verwijzingen: ({ blok }) => (
    <Sectie kop="Verwijzingen">
      <ul className="ml-4 list-disc space-y-0.5">{blok.items.map((v) => <li key={v.iri}><Vindplaats vindplaats={v} /></li>)}</ul>
    </Sectie>
  ),
  annotaties: ({ blok }) => (
    <Sectie kop={`Markeringen (${blok.totaal})`}>
      <ul className="ml-4 list-disc space-y-0.5">
        {blok.items.map((m) => <li key={m.id}><span className="font-medium">{m.klasse}:</span> {m.tekst}{m.vindplaats && <span className="text-xs text-muted"> · {m.vindplaats}</span>}</li>)}
      </ul>
      {!blok.volledig && <p className="text-xs text-muted">Dit zijn niet alle markeringen.</p>}
    </Sectie>
  ),
  toelichting: ({ blok, bronnen, nietLetterlijk }) => (
    <Sectie kop={blok.kop}><Markdown tekst={blok.tekst} bronnen={bronnen} nietLetterlijk={nietLetterlijk} /></Sectie>
  ),
  twijfel: ({ blok, bronnen, nietLetterlijk }) => (
    <Sectie kop="Twijfel en aannames">
      <ul className="ml-4 list-disc space-y-0.5">{blok.punten.map((p) => <li key={p}><Markdown tekst={p} bronnen={bronnen} nietLetterlijk={nietLetterlijk} /></li>)}</ul>
    </Sectie>
  ),
  // Een bron naast de wet (ADR-013): letterlijk, met haar eigen vindplaats, en zichtbaar geen wettekst.
  extern: ({ blok }) => (
    <Sectie kop={blok.kop}>
      <p className="text-xs text-muted">{BRONTYPE_NAAM[blok.brontype] ?? "Bron naast de wet"}, geen wettekst: het onderbouwt een uitleg, niet wat de wet zegt.</p>
      <div className="space-y-3" data-extern={blok.id}>
        {blok.passages.map((p) => (
          <div key={p.nr} className="space-y-1">
            {p.kop && <p className="text-xs font-medium text-muted">{p.kop}</p>}
            <Citaat>{p.tekst}</Citaat>
          </div>
        ))}
      </div>
      <p className="text-xs text-muted">
        {blok.link
          ? <a href={blok.link} target="_blank" rel="noopener noreferrer" className="focus-ring rounded underline underline-offset-2">{blok.label}</a>
          : blok.label}
      </p>
    </Sectie>
  ),
  leemte: ({ blok }) => <p className="text-muted" data-leemte>{blok.tekst}</p>,
};

function BlokWeergave({ blok, ...rest }: { blok: AntwoordBlok; bronnen?: readonly Bron[]; nietLetterlijk?: readonly string[] }) {
  const Teken = BLOKKEN[blok.soort] as (p: Props<BlokSoort>) => React.ReactNode;
  return <>{Teken({ blok, ...rest })}</>;
}

export function Antwoord({ antwoord, bronnen, nietLetterlijk }: { antwoord: AntwoordData; bronnen?: readonly Bron[]; nietLetterlijk?: readonly string[] }) {
  return (
    <div data-testid="antwoord-sjabloon" data-sjabloon={antwoord.sjabloon} className="space-y-4 text-sm leading-relaxed text-ink">
      {antwoord.blokken.map((b, i) => <BlokWeergave key={`${b.soort}-${i}`} blok={b} bronnen={bronnen} nietLetterlijk={nietLetterlijk} />)}
    </div>
  );
}
