"use client";

// Het rapport van een contenttoets naast het gesprek (plan contenttoets, C6; de mockup "Bekijk de contenttoets"): de
// content zelf met elke bewering gemarkeerd in de kleur van haar oordeel, de telling als filter, een legenda, en
// daaronder per bevinding de bron en het voorstel. Een klik op een markering kiest haar bevinding; een klik op het nummer
// van een bevinding zet haar markering in beeld. Het paneel is om te lezen: overnemen en beoordelen komt met C7.

import { useMemo, useState } from "react";

import { StatusLabel, TOON } from "@/components/ui/Lijst";
import { Bevinding, GetoetstTegen, Rest, VoorRedacteur } from "./ContenttoetsBlok";
import { OORDEEL_LABEL, OORDEEL_TOON, OORDELEN, aantallen, contentDelen, tellingTekst,
  type ContenttoetsBlok, type Oordeel } from "@/lib/contenttoets";

/** De markering in de content: de kleur van het oordeel, zoals het label. */
const MARK: Record<Oordeel, string> = {
  mogelijk_onjuist: "bg-aandacht-rood-bg decoration-aandacht-rood-rand",
  onvolledig: "bg-aandacht-geel-bg decoration-aandacht-geel-rand",
  niet_in_de_bron: "bg-surface-2 decoration-line",
  juist: "bg-aandacht-groen-bg decoration-aandacht-groen-rand",
};

/** Wat elke kleur betekent, in de woorden van de skill (references/rapport.md). */
const UITLEG: Record<Oordeel, string> = {
  mogelijk_onjuist: "de tekst zegt iets anders dan de bron",
  onvolledig: "er ontbreekt een voorwaarde, gevolg of uitzondering",
  niet_in_de_bron: "Lex vond hiervoor geen bron",
  juist: "klopt met de bron",
};

export function ContenttoetsPaneel({ toets }: { toets: ContenttoetsBlok }) {
  const n = aantallen(toets);
  const delen = useMemo(() => contentDelen(toets), [toets]);
  const [filter, setFilter] = useState<Oordeel | null>(null);
  const [gekozen, setGekozen] = useState<number>();
  const zichtbaar = (o: Oordeel) => !filter || filter === o;
  const bevindingen = toets.bevindingen.filter((b) => zichtbaar(b.oordeel));

  function kies(nr: number, naar: "tekst" | "bevinding") {
    setGekozen(nr);
    const doel = naar === "tekst" ? `[data-toets-mark="${nr}"]` : `[data-toetsbevinding="${nr}"]`;
    requestAnimationFrame(() => document.querySelector(`[data-contenttoets-paneel] ${doel}`)?.scrollIntoView({ block: "center" }));
  }

  return (
    <div className="space-y-5" data-contenttoets-paneel>
      <div className="space-y-2">
        <GetoetstTegen blok={toets} />
        <p className="sr-only" aria-live="polite">{tellingTekst(toets)}</p>
        <div className="flex flex-wrap gap-1.5" role="group" aria-label="Toon alleen">
          <button type="button" aria-pressed={!filter} onClick={() => setFilter(null)} data-toets-filter="alle"
            className={`focus-ring rounded-full border px-2.5 py-0.5 text-xs ${!filter ? "border-lint bg-lint text-white" : "border-line bg-surface text-muted"}`}>
            Alle {toets.bevindingen.length}
          </button>
          {OORDELEN.filter((o) => n[o]).map((o) => (
            <button key={o} type="button" aria-pressed={filter === o} onClick={() => setFilter(filter === o ? null : o)} data-toets-filter={o}
              className={`focus-ring rounded-full border px-2.5 py-0.5 text-xs ${TOON[OORDEEL_TOON[o]]} ${filter === o ? "ring-2 ring-lint ring-offset-1" : ""}`}>
              {n[o]} {OORDEEL_LABEL[o].toLowerCase()}
            </button>
          ))}
        </div>
      </div>

      <VoorRedacteur blok={toets} />

      <section className="space-y-2">
        <h4 className="text-sm font-semibold text-ink">De tekst</h4>
        <div className="whitespace-pre-wrap break-words rounded-kaart border border-line bg-surface px-4 py-3 text-sm leading-7" data-toets-content>
          {delen.map((d, i) => (d.nr == null || !d.oordeel ? <span key={i}>{d.tekst}</span> : (
            // De markering is zelf de knop: een <button> is in Chrome altijd een blok in de regel en breekt de tekst.
            <mark key={i} data-toets-mark={d.nr} data-oordeel={d.oordeel} role="button" tabIndex={0}
              aria-label={`${d.tekst} – bevinding ${d.nr}, ${OORDEEL_LABEL[d.oordeel].toLowerCase()}`}
              onClick={() => kies(d.nr!, "bevinding")}
              onKeyDown={(e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); kies(d.nr!, "bevinding"); } }}
              className={`focus-ring cursor-pointer rounded-sm px-0.5 text-ink [box-decoration-break:clone] underline decoration-2 underline-offset-4 ${MARK[d.oordeel]} ${zichtbaar(d.oordeel) ? "" : "opacity-30"} ${gekozen === d.nr ? "outline outline-2 outline-lint" : ""}`}>
              {d.tekst}<sup className="ml-0.5 font-semibold tabular-nums text-muted" aria-hidden>{d.nr}</sup>
            </mark>
          )))}
        </div>
        <ul className="flex flex-wrap gap-x-4 gap-y-1 text-xs text-muted" aria-label="Legenda" data-toets-legenda>
          {OORDELEN.map((o) => (
            <li key={o} className="flex items-center gap-1.5">
              <span className={`inline-block h-3 w-3 rounded-sm border ${TOON[OORDEEL_TOON[o]]}`} aria-hidden />
              <span><span className="font-medium text-ink">{OORDEEL_LABEL[o]}</span>: {UITLEG[o]}</span>
            </li>
          ))}
        </ul>
      </section>

      <section className="space-y-2">
        <h4 className="text-sm font-semibold text-ink">
          Per bewering{filter && <StatusLabel toon={OORDEEL_TOON[filter]} klein className="ml-2">{OORDEEL_LABEL[filter]}</StatusLabel>}
        </h4>
        <ol className="space-y-3">
          {bevindingen.map((b) => <Bevinding key={b.nr} b={b} actief={gekozen === b.nr} onKies={() => kies(b.nr, "tekst")} />)}
        </ol>
      </section>

      <Rest blok={toets} />
    </div>
  );
}
