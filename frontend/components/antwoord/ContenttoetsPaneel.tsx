"use client";

// Het rapport van een contenttoets naast het gesprek (plan contenttoets, C6 en C7; de mockup "Bekijk de contenttoets"):
// de content zelf met elke bewering gemarkeerd in de kleur van haar oordeel, de telling als filter, een legenda, en
// daaronder per bevinding de bron en het voorstel. Een klik op een markering kiest haar bevinding; een klik op het nummer
// van een bevinding zet haar markering in beeld.
//
// C7: per bevinding het oordeel van de mens (eens of oneens met Lex, en het voorstel overgenomen, aangepast of
// afgewezen), bewaard op het bericht (api `toetsbesluiten`). De tekst kan met de overgenomen voorstellen erin, en het
// geheel gaat als Markdown naar het klembord of in een bestand.

import { useEffect, useMemo, useState } from "react";

import { knopKlasse } from "@/components/ui/Button";
import { StatusLabel, TOON } from "@/components/ui/Lijst";
import { Melding } from "@/components/ui/Melding";
import { Bevinding, GetoetstTegen, Rest, VoorRedacteur } from "./ContenttoetsBlok";
import { downloadTekst, foutTekst, haalToetsbesluiten, zetToetsbesluit } from "@/lib/api";
import { bestandsnaam } from "@/lib/artefactMarkdown";
import {
  OORDEEL_LABEL, OORDEEL_TOON, OORDELEN, TOETSOORDEEL_LABEL, TOETSOORDELEN, VOORSTELBESLUIT_LABEL, aantallen, beoordeeld,
  contentDelen, nieuweTekst, parseToetsbesluiten, tellingTekst, toetsMarkdown,
  type ContenttoetsBlok, type Oordeel, type ToetsBericht, type Toetsbesluit, type ToetsbesluitInvoer, type Toetsbevinding,
} from "@/lib/contenttoets";
import { useKopieer } from "@/lib/kopieer";

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

const KEUZE = "focus-ring rounded-full border px-2.5 py-0.5 text-xs";
const keuze = (aan: boolean) => `${KEUZE} ${aan ? "border-lint bg-lint text-white" : "border-line bg-surface text-ink hover:border-lint/40"}`;

export function ContenttoetsPaneel({ toets, bericht }: { toets: ContenttoetsBlok; bericht?: ToetsBericht }) {
  const n = aantallen(toets);
  const delen = useMemo(() => contentDelen(toets), [toets]);
  const [filter, setFilter] = useState<Oordeel | null>(null);
  const [gekozen, setGekozen] = useState<number>();
  const [metVoorstellen, setMetVoorstellen] = useState(false);
  const [besluiten, setBesluiten] = useState<Toetsbesluit[]>([]);
  const [fout, setFout] = useState<string>();
  const { stand: kopieerStand, kopieer } = useKopieer();
  const zichtbaar = (o: Oordeel) => !filter || filter === o;
  const bevindingen = toets.bevindingen.filter((b) => zichtbaar(b.oordeel));
  const per = useMemo(() => new Map(besluiten.map((d) => [d.nr, d])), [besluiten]);
  const bevindingVan = useMemo(() => new Map(toets.bevindingen.map((b) => [b.nr, b])), [toets]);

  // De besluiten staan bij het bericht, niet in het paneel: vers lezen bij elke opening, zodat een ander tabblad of
  // herladen hetzelfde toont.
  const gesprekId = bericht?.gesprek_id, runId = bericht?.run_id;
  useEffect(() => {
    if (!gesprekId || !runId) return;
    let levend = true;
    haalToetsbesluiten(gesprekId, runId).then((x) => levend && setBesluiten(parseToetsbesluiten(x)))
      .catch((e) => levend && setFout(foutTekst(e, "De besluiten bij deze toets konden niet worden geladen.")));
    return () => { levend = false; };
  }, [gesprekId, runId]);

  async function besluit(nr: number, invoer: ToetsbesluitInvoer): Promise<boolean> {
    if (!gesprekId || !runId) return false;
    setFout(undefined);
    try {
      setBesluiten(parseToetsbesluiten(await zetToetsbesluit(gesprekId, runId, nr, invoer)));
      return true;
    } catch (e) {
      setFout(foutTekst(e, "Het besluit kon niet worden bewaard."));
      return false;
    }
  }

  function kies(nr: number, naar: "tekst" | "bevinding") {
    setGekozen(nr);
    const doel = naar === "tekst" ? `[data-toets-mark="${nr}"]` : `[data-toetsbevinding="${nr}"]`;
    requestAnimationFrame(() => document.querySelector(`[data-contenttoets-paneel] ${doel}`)?.scrollIntoView({ block: "center" }));
  }

  const markdown = () => toetsMarkdown(toets, besluiten);
  const aantalBeoordeeld = beoordeeld(toets, besluiten);
  const aantalOvergenomen = besluiten.filter((d) => {
    const b = bevindingVan.get(d.nr);
    return b && nieuweTekst(b, d);
  }).length;

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
        <div className="flex flex-wrap items-center gap-2 pt-1">
          {bericht && (
            <span className="mr-auto text-xs text-muted" data-toets-voortgang>
              Beoordeeld: {aantalBeoordeeld} van {toets.bevindingen.length}
            </span>
          )}
          <button type="button" className={knopKlasse("secondary", "xs")} data-toets-kopieer
            onClick={() => void kopieer(markdown())}>
            {kopieerStand === "gekopieerd" ? "Gekopieerd" : kopieerStand === "mislukt" ? "Kopiëren lukte niet" : "Kopieer als Markdown"}
          </button>
          <button type="button" className={knopKlasse("secondary", "xs")} data-toets-download
            onClick={() => downloadTekst(markdown(), bestandsnaam("contenttoets"), "text/markdown")}>
            Download (.md)
          </button>
        </div>
        {fout && <Melding type="fout" compact>{fout}</Melding>}
      </div>

      <VoorRedacteur blok={toets} />

      <section className="space-y-2">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <h4 className="text-sm font-semibold text-ink">De tekst</h4>
          {aantalOvergenomen > 0 && (
            <label className="flex items-center gap-1.5 text-xs text-muted">
              <input type="checkbox" checked={metVoorstellen} onChange={(e) => setMetVoorstellen(e.target.checked)} data-toets-met-voorstellen />
              Met de overgenomen voorstellen ({aantalOvergenomen})
            </label>
          )}
        </div>
        <div className="whitespace-pre-wrap break-words rounded-kaart border border-line bg-surface px-4 py-3 text-sm leading-7" data-toets-content>
          {delen.map((d, i) => {
            if (d.nr == null || !d.oordeel) return <span key={i}>{d.tekst}</span>;
            const nieuw = metVoorstellen ? nieuweTekst(bevindingVan.get(d.nr)!, per.get(d.nr)) : "";
            if (nieuw) {
              return (
                <span key={i} data-toets-vervangen={d.nr}>
                  <del className="text-muted">{d.tekst}</del>{" "}
                  <ins className="rounded-sm bg-aandacht-groen-bg px-0.5 text-ink no-underline">{nieuw}</ins>
                  <sup className="ml-0.5 font-semibold tabular-nums text-muted" aria-hidden>{d.nr}</sup>
                </span>
              );
            }
            return (
              // De markering is zelf de knop: een <button> is in Chrome altijd een blok in de regel en breekt de tekst.
              <mark key={i} data-toets-mark={d.nr} data-oordeel={d.oordeel} role="button" tabIndex={0}
                aria-label={`${d.tekst} – bevinding ${d.nr}, ${OORDEEL_LABEL[d.oordeel].toLowerCase()}`}
                onClick={() => kies(d.nr!, "bevinding")}
                onKeyDown={(e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); kies(d.nr!, "bevinding"); } }}
                className={`focus-ring cursor-pointer rounded-sm px-0.5 text-ink [box-decoration-break:clone] underline decoration-2 underline-offset-4 ${MARK[d.oordeel]} ${zichtbaar(d.oordeel) ? "" : "opacity-30"} ${gekozen === d.nr ? "outline outline-2 outline-lint" : ""}`}>
                {d.tekst}<sup className="ml-0.5 font-semibold tabular-nums text-muted" aria-hidden>{d.nr}</sup>
              </mark>
            );
          })}
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
          {bevindingen.map((b) => (
            <Bevinding key={b.nr} b={b} actief={gekozen === b.nr} onKies={() => kies(b.nr, "tekst")}
              beoordeling={bericht && <Beoordeling b={b} besluit={per.get(b.nr)} onBesluit={(i) => besluit(b.nr, i)} />} />
          ))}
        </ol>
      </section>

      <Rest blok={toets} />
    </div>
  );
}

/** Het oordeel van de mens over één bevinding: twee losse vragen, elk met een knop die je nog eens indrukt om het terug
 *  te nemen. Aanpassen opent een veld met het voorstel van Lex; een reden kan bij oneens en afwijzen. */
function Beoordeling({ b, besluit: d, onBesluit }: {
  b: Toetsbevinding; besluit?: Toetsbesluit; onBesluit: (invoer: ToetsbesluitInvoer) => Promise<boolean>;
}) {
  const [bewerk, setBewerk] = useState<"tekst" | "reden" | null>(null);
  const [tekst, setTekst] = useState("");
  const [reden, setReden] = useState("");
  const huidig: ToetsbesluitInvoer = { oordeel: d?.oordeel ?? null, voorstel: d?.voorstel ?? null, tekst: d?.tekst ?? "", reden: d?.reden ?? "" };
  const met = (w: ToetsbesluitInvoer) => {
    const nieuw = { ...huidig, ...w };
    if (nieuw.voorstel !== "aangepast") nieuw.tekst = "";
    return onBesluit(nieuw);
  };
  const vraagReden = d?.oordeel === "oneens" || d?.voorstel === "afgewezen";

  return (
    <div className="space-y-2 rounded-kaart border border-line bg-paper px-3 py-2.5" data-toets-beoordeling={b.nr}>
      <div className="flex flex-wrap items-center gap-1.5" role="group" aria-label={`Klopt het oordeel van Lex bij bevinding ${b.nr}?`}>
        <span className="mr-1 text-xs font-medium text-muted">Klopt het oordeel?</span>
        {TOETSOORDELEN.map((o) => (
          <button key={o} type="button" aria-pressed={d?.oordeel === o} data-toets-oordeel={o} className={keuze(d?.oordeel === o)}
            onClick={() => void met({ oordeel: d?.oordeel === o ? null : o })}>
            {TOETSOORDEEL_LABEL[o]}
          </button>
        ))}
      </div>
      {b.voorstel && (
        <div className="flex flex-wrap items-center gap-1.5" role="group" aria-label={`Het voorstel bij bevinding ${b.nr}`}>
          <span className="mr-1 text-xs font-medium text-muted">Het voorstel</span>
          <button type="button" aria-pressed={d?.voorstel === "overgenomen"} data-toets-voorstel="overgenomen"
            className={keuze(d?.voorstel === "overgenomen")}
            onClick={() => void met({ voorstel: d?.voorstel === "overgenomen" ? null : "overgenomen" })}>Overnemen</button>
          <button type="button" aria-pressed={d?.voorstel === "aangepast"} data-toets-voorstel="aangepast"
            className={keuze(d?.voorstel === "aangepast")}
            onClick={() => { setTekst(d?.voorstel === "aangepast" ? d.tekst : b.voorstel); setBewerk("tekst"); }}>Aanpassen</button>
          <button type="button" aria-pressed={d?.voorstel === "afgewezen"} data-toets-voorstel="afgewezen"
            className={keuze(d?.voorstel === "afgewezen")}
            onClick={() => void met({ voorstel: d?.voorstel === "afgewezen" ? null : "afgewezen" })}>Afwijzen</button>
        </div>
      )}
      {bewerk === "tekst" && (
        <form className="space-y-1.5" data-toets-aanpassen
          onSubmit={async (e) => { e.preventDefault(); if (tekst.trim() && await met({ voorstel: "aangepast", tekst: tekst.trim() })) setBewerk(null); }}>
          <label className="block text-xs font-medium text-muted" htmlFor={`toets-tekst-${b.nr}`}>Jouw tekst</label>
          <textarea id={`toets-tekst-${b.nr}`} value={tekst} onChange={(e) => setTekst(e.target.value)} rows={3} maxLength={4000}
            className="w-full rounded-md border border-line bg-paper px-2 py-1.5 text-sm text-ink focus-ring" />
          <div className="flex gap-2">
            <button type="submit" className={knopKlasse("primary", "xs")} disabled={!tekst.trim()}>Bewaar</button>
            <button type="button" className={knopKlasse("ghost", "xs")} onClick={() => setBewerk(null)}>Annuleer</button>
          </div>
        </form>
      )}
      {bewerk === "reden" && (
        <form className="space-y-1.5" data-toets-reden
          onSubmit={async (e) => { e.preventDefault(); if (await met({ reden: reden.trim() })) setBewerk(null); }}>
          <label className="block text-xs font-medium text-muted" htmlFor={`toets-reden-${b.nr}`}>Waarom?</label>
          <textarea id={`toets-reden-${b.nr}`} value={reden} onChange={(e) => setReden(e.target.value)} rows={2} maxLength={2000}
            className="w-full rounded-md border border-line bg-paper px-2 py-1.5 text-sm text-ink focus-ring" />
          <div className="flex gap-2">
            <button type="submit" className={knopKlasse("primary", "xs")}>Bewaar</button>
            <button type="button" className={knopKlasse("ghost", "xs")} onClick={() => setBewerk(null)}>Annuleer</button>
          </div>
        </form>
      )}
      {d?.voorstel === "aangepast" && bewerk !== "tekst" && (
        <p className="text-sm text-ink" data-toets-nieuwe-tekst><span className="text-xs font-medium text-muted">Jouw tekst: </span>{d.tekst}</p>
      )}
      {d?.reden && bewerk !== "reden" && (
        <p className="text-sm text-ink"><span className="text-xs font-medium text-muted">Reden: </span>{d.reden}</p>
      )}
      {vraagReden && bewerk === null && (
        <button type="button" className="focus-ring rounded text-xs text-lint underline underline-offset-2" data-toets-reden-knop
          onClick={() => { setReden(d?.reden ?? ""); setBewerk("reden"); }}>
          {d?.reden ? "Reden wijzigen" : "Reden toevoegen"}
        </button>
      )}
      {d && (
        <p className="text-2xs text-muted" data-toets-besluit-door>
          {[d.oordeel && `${TOETSOORDEEL_LABEL[d.oordeel]} met Lex`, d.voorstel && `voorstel ${VOORSTELBESLUIT_LABEL[d.voorstel].toLowerCase()}`]
            .filter(Boolean).join(", ")} · {d.door}
        </p>
      )}
    </div>
  );
}
