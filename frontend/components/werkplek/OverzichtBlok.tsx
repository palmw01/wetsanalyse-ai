"use client";

// Het overzicht van een onderwerp onder de duiding van Lex: per regeling de delen met al hun
// bepalingen, wat het onderwerp verder noemt (met zijn plek in de opbouw), de wettelijke definitie en
// het redactionele trefwoord.
//
// De inhoud komt uit de graaf (graph-qa `agent/overzicht.py`), niet uit de tekst van het model: elk
// nummer staat er zoals de graaf het heeft, nooit als bereik, en dezelfde vraag geeft hetzelfde blok –
// ook na herladen, want het reist mee in het bericht. De rekenkern staat in `lib/overzicht.ts`.

import { memo, useState } from "react";

import { ChevronOmlaag } from "@/components/ui/Icoon";
import { bepalingNaam, deelKop, telling, zoekverantwoording } from "@/lib/overzicht";
import type { Overzicht, OverzichtBepaling, OverzichtRegeling } from "@/lib/types";
import { bronHref } from "@/lib/url";

function Verwijzing({ label, iri, jci }: { label: string; iri: string; jci?: string }) {
  // Bij voorkeur de jci (die kent wetten.overheid.nl), anders de graaf-IRI; `bronHref` weigert al het
  // andere, en dan is het platte tekst.
  const href = bronHref(jci || iri);
  return href ? (
    <a href={href} target="_blank" rel="noopener noreferrer"
      className="text-lint underline underline-offset-2 [overflow-wrap:anywhere]">{label}</a>
  ) : <span>{label}</span>;
}

function Lijst({ bepalingen }: { bepalingen: OverzichtBepaling[] }) {
  return <>{bepalingen.map((b, i) => (
    <span key={b.iri}>{i > 0 && ", "}<Verwijzing label={bepalingNaam(b)} iri={b.iri} jci={b.jci} /></span>
  ))}</>;
}

function OokGenoemd({ regeling }: { regeling: OverzichtRegeling }) {
  const [open, setOpen] = useState(false);
  if (!regeling.ook_genoemd.length) return null;
  return (
    <div className="mt-1">
      <button type="button" onClick={() => setOpen((o) => !o)} aria-expanded={open}
        className="focus-ring inline-flex min-h-[24px] items-center gap-1.5 rounded text-xs text-muted transition-colors hover:text-ink">
        <ChevronOmlaag className={`-rotate-90 transition-transform ${open ? "rotate-0" : ""}`} />
        Noemt het onderwerp ook ({regeling.ook_genoemd.length})
      </button>
      {open && (
        <ul className="mt-1 space-y-0.5 pl-5 text-xs text-muted">
          {regeling.ook_genoemd.map((b) => (
            <li key={b.iri}>
              <Verwijzing label={bepalingNaam(b)} iri={b.iri} jci={b.jci} />
              {b.label && !/^Artikel\s/.test(b.label) && <> – {b.label}</>}
              {b.in_deel && <span className="text-muted"> · in {b.in_deel.label}</span>}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

export const OverzichtBlok = memo(function OverzichtBlok({ overzicht }: { overzicht: Overzicht }) {
  const t = telling(overzicht);
  return (
    <section data-testid="overzicht" aria-label={`Overzicht: ${overzicht.gevraagd}`}
      className="mt-3 rounded-kaart border border-line bg-surface px-4 py-3 text-sm text-ink">
      <header className="mb-2">
        <h3 className="text-xs font-semibold uppercase tracking-wide text-muted">Overzicht uit de kennisgraaf</h3>
        <p className="text-xs text-muted">
          {t.regelingen} regeling{t.regelingen === 1 ? "" : "en"} · {t.delen} {t.delen === 1 ? "deel" : "delen"} met
          {" "}{t.bepalingen} bepaling{t.bepalingen === 1 ? "" : "en"}
          {t.ookGenoemd > 0 && <> · {t.ookGenoemd} die het onderwerp verder noemen</>}
        </p>
      </header>

      {overzicht.definities.length > 0 && (
        <p className="mb-2 text-xs">
          <span className="font-medium">Wettelijke definitie:</span>{" "}
          {overzicht.definities.map((d, i) => (
            <span key={d.iri}>{i > 0 && "; "}„{d.begrip}” – {d.citeertitel},{" "}
              <Verwijzing label={d.label || "vindplaats"} iri={d.iri} jci={d.jci} /></span>
          ))}
        </p>
      )}

      {overzicht.regelingen.length === 0 && (
        <p className="text-xs text-muted">De graaf bevat geen deel of bepaling over dit onderwerp.</p>
      )}

      <ul className="space-y-3">
        {overzicht.regelingen.map((r) => (
          <li key={r.bwb_id}>
            <p className="font-medium"><Verwijzing label={r.citeertitel} iri={`urn:bwb:${r.bwb_id}`} /></p>
            {r.delen.length > 0 && (
              <ul className="mt-1 space-y-1">
                {r.delen.map((d) => (
                  <li key={d.iri} className="border-l-2 border-line pl-3">
                    <Verwijzing label={deelKop(d)} iri={d.iri} jci={d.jci} />
                    <span className="block text-xs text-muted [overflow-wrap:anywhere]"><Lijst bepalingen={d.bepalingen} /></span>
                    {d.subdelen.map((s) => (
                      <span key={s.iri} className="block text-xs text-muted">waarin <Verwijzing label={s.label} iri={s.iri} /></span>
                    ))}
                  </li>
                ))}
              </ul>
            )}
            <OokGenoemd regeling={r} />
          </li>
        ))}
      </ul>

      <footer className="mt-3 space-y-0.5 text-xs text-muted">
        {overzicht.trefwoorden.map((tw) => (
          <p key={tw.trefwoord}>Trefwoord „{tw.trefwoord}” (redactioneel) bij: {tw.regelingen.map((x) => x.citeertitel).join(", ")}</p>
        ))}
        <p>{zoekverantwoording(overzicht)}</p>
        {!overzicht.volledig && <p>Dit overzicht raakte zijn bovengrens; er kan meer over het onderwerp zijn.</p>}
      </footer>
    </section>
  );
});
