"use client";

// Het antwoord als sjabloon (ADR-008): vaste blokken, gewoon in de tekst van het gesprek. Geen kaart, geen achtergrond:
// een sjabloon is een vorm van antwoorden, geen artefact. Elk blok hoort bij één component, en een soort zonder
// component compileert niet (`BLOKKEN`). Wat Lex schreef staat onder een eigen kop; de rest komt uit de bron.

import Link from "next/link";

import { StandMelding } from "@/components/ui/StandMelding";
import { NOG_NIET_IN_WERKING } from "@/lib/herkomst";
import { Citaat } from "@/components/ui/Citaat";
import { StatusLabel } from "@/components/ui/Lijst";
import { Vindplaats } from "./Vindplaats";
import { Markdown } from "@/components/werkplek/Markdown";
import { externGroepen, groepeerWettekst, type Antwoord as AntwoordData, type AntwoordBlok, type BlokSoort, type ExternGroep } from "@/lib/antwoord";
import { bronHref } from "@/lib/url";
import { BRONTYPE_NAAM } from "@/lib/bronnen";
import { begripPad, generiekPad } from "@/lib/werkgebiedPaden";
import { datumTekst } from "@/lib/datum";
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
                {b.nog_niet_in_werking && <StandMelding meldingen={[NOG_NIET_IN_WERKING]} />}
                <p className="text-xs text-muted"><Vindplaats vindplaats={{ ...b.vindplaats, label: `lid ${lid}` }} kort /></p>
                <Citaat>{b.tekst}</Citaat>
              </div>
            ))}
          </div>
        ) : g.items.map(({ item: b }) => (
          <div key={b.vindplaats.iri} className="space-y-1">{b.nog_niet_in_werking && <StandMelding meldingen={[NOG_NIET_IN_WERKING]} />}<Citaat>{b.tekst}</Citaat><p className="text-xs text-muted"><Vindplaats vindplaats={b.vindplaats} /></p></div>
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
        {externGroepen(blok.passages).map((g, i) => <ExternGroepWeergave key={i} groep={g} />)}
      </div>
      <p className="text-xs text-muted">
        {blok.link
          ? <a href={blok.link} target="_blank" rel="noopener noreferrer" className="focus-ring rounded underline underline-offset-2">{blok.label}</a>
          : blok.label}
        {/* De datum en het soort uit de metadata van het stuk, niet uit de tekst van Lex. */}
        {(blok.soort_stuk || blok.datum) && <span data-extern-meta> · {[blok.soort_stuk, datumTekst(blok.datum)].filter(Boolean).join(", ")}</span>}
      </p>
    </Sectie>
  ),
  // Een lijst gevonden stukken: elk feit uit de zoekrijen, met wat er gezocht is. Gevonden, niet gelezen.
  stukken: ({ blok }) => (
    <Sectie kop={blok.kop}>
      <ul className="space-y-2" data-stukken={blok.brontype}>
        {blok.items.map((s) => (
          <li key={s.id} className="space-y-0.5" data-stuk={s.id}>
            <p className="flex flex-wrap items-center gap-2">
              {s.link
                ? <a href={s.link} target="_blank" rel="noopener noreferrer" className="focus-ring rounded font-medium text-lint underline underline-offset-2">{s.label}</a>
                : <span className="font-medium">{s.label}</span>}
              {s.leesbaar === false && <StatusLabel toon="geel" klein uitleg="De tekst staat bij de bron nog alleen als PDF en is niet te lezen.">alleen PDF</StatusLabel>}
            </p>
            <p className="text-xs text-muted">
              {[s.soort, datumTekst(s.datum), s.orgaan].filter(Boolean).join(" · ")}
              {s.gepubliceerd && <> · gepubliceerd {datumTekst(s.gepubliceerd)}</>}
            </p>
            {s.titel && <p>{s.titel}</p>}
            {!!s.indieners?.length && <p className="text-xs text-muted">Ingediend door {s.indieners.join(", ")}</p>}
          </li>
        ))}
      </ul>
      {(blok.zoekvraag || (blok.totaal ?? 0) > blok.items.length) && (
        <p className="text-xs text-muted" data-stukken-zoekvraag>
          {[blok.zoekvraag, (blok.totaal ?? 0) > blok.items.length ? `${blok.items.length} van de ${blok.totaal} stukken.` : ""].filter(Boolean).join(" ")}
        </p>
      )}
      <p className="text-xs text-muted">Gevonden, niet gelezen: de lijst zegt niets over wat er in de stukken staat.</p>
    </Sectie>
  ),
  leemte: ({ blok }) => <p className="text-muted" data-leemte>{blok.tekst}</p>,
};

/** Een groep uit een bron naast de wet: een alinea als citaat, een voetnoot klein met de stukken waar ze naar verwijst,
 *  een tabel als tabel. De tekst blijft letterlijk; de tabel zet de cellen alleen in hun kolom. */
function ExternGroepWeergave({ groep }: { groep: ExternGroep }) {
  if (groep.soort === "tabel") {
    const kolommen = groep.kop?.cellen ?? [];
    return (
      <div className="space-y-1" data-extern-tabel>
        {groep.kop?.kop && <p className="text-xs font-medium text-muted">{groep.kop.kop}</p>}
        <div className="max-w-full overflow-x-auto">
          <table className="min-w-full border-collapse text-xs">
            {groep.kop && <caption className="pb-1 text-left font-medium text-ink">{groep.kop.tekst}</caption>}
            {kolommen.some(Boolean) && (
              <thead><tr>{kolommen.map((k, i) => <th key={i} scope="col" className="border-b border-line px-2 py-1 text-left font-medium">{k}</th>)}</tr></thead>
            )}
            <tbody>
              {groep.rijen.map((r) => (
                <tr key={r.nr} className="border-b border-line last:border-0">
                  {(r.cellen ?? [r.tekst]).map((c, i) => <td key={i} className="px-2 py-1 align-top">{c}</td>)}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    );
  }
  const p = groep.passage;
  if (groep.soort === "voetnoot") {
    return (
      <p className="text-xs text-muted" data-extern-voetnoot>
        <span className="font-medium">Voetnoot:</span> {p.tekst}
        {p.verwijst_naar?.map((v) => {
          const href = bronHref(v.link);
          return <span key={v.id}> · {href ? <a href={href} target="_blank" rel="noopener noreferrer" className="focus-ring rounded underline underline-offset-2">{v.label}</a> : v.label}</span>;
        })}
      </p>
    );
  }
  return (
    <div className="space-y-1">
      {p.kop && <p className="text-xs font-medium text-muted">{p.kop}</p>}
      <Citaat>{p.tekst}</Citaat>
    </div>
  );
}

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
