"use client";

// Het toetsrapport van de contenttoets (plan contenttoets): twee lagen, eerst wat de redacteur moet veranderen, dan per
// bewering de juridische kern met de letterlijke bron. Lijsten, geen tabel: het rapport blijft heel als je het kopieert.
// In de werkplek staat in het gesprek een korte toelichting met de kaart *Bekijk de contenttoets*, en het rapport naast
// het gesprek met de markeringen in de content zelf (fase 2, `ContenttoetsPaneel`); daarbuiten staat het hele rapport hier.

import { Citaat } from "@/components/ui/Citaat";
import { PaneelChip, chipSub } from "@/components/ui/PaneelChip";
import { useContext } from "react";
import { BerichtRunContext, useOpenBron, contenttoetsContext } from "@/components/werkplek/ContextPaneel";
import { StatusLabel } from "@/components/ui/Lijst";
import { Vindplaats } from "./Vindplaats";
import { OORDEEL_LABEL, OORDEEL_TOON, OORDELEN, aantallen, criteriumTekst, tellingTekst,
  type ContenttoetsBlok as Blok, type Toetsbevinding, type ToetsBron } from "@/lib/contenttoets";
import { datumTekst } from "@/lib/datum";

export function Bronnen({ bronnen }: { bronnen: readonly ToetsBron[] }) {
  return (
    <div className="space-y-2">
      {bronnen.map((b, i) => (
        <div key={`${b.vindplaats.iri}-${i}`} className="space-y-1">
          <Citaat>{b.tekst}</Citaat>
          <p className="text-xs text-muted"><Vindplaats vindplaats={b.vindplaats} /></p>
        </div>
      ))}
    </div>
  );
}

export function Bevinding({ b, actief = false, onKies, beoordeling }: { b: Toetsbevinding; actief?: boolean; onKies?: () => void;
  /** Het oordeel van de mens onder de bevinding (C7), alleen in het paneel. */
  beoordeling?: React.ReactNode }) {
  return (
    <li className={`space-y-2 border-t border-line pt-3 first:border-t-0 first:pt-0 ${actief ? "rounded-kaart bg-lint/5 px-3 pb-3 ring-2 ring-inset ring-lint/40 first:pt-3" : ""}`}
      data-toetsbevinding={b.nr} data-oordeel={b.oordeel} data-actief={actief || undefined}>
      <p className="flex flex-wrap items-center gap-2">
        {onKies
          ? <button type="button" onClick={onKies} data-toon-in-tekst={b.nr} aria-label={`Bevinding ${b.nr} in de tekst tonen`}
              className="focus-ring rounded font-semibold tabular-nums text-lint underline underline-offset-2">[{b.nr}]</button>
          : <span className="font-semibold tabular-nums text-muted">[{b.nr}]</span>}
        <StatusLabel toon={OORDEEL_TOON[b.oordeel]} klein>{OORDEEL_LABEL[b.oordeel]}</StatusLabel>
        {b.criterium && <span className="text-xs text-muted">{criteriumTekst(b.criterium)}</span>}
      </p>
      <div>
        <p className="text-xs font-medium text-muted">De tekst</p>
        <p className="break-words">“{b.citaat}”</p>
      </div>
      {b.bronnen.length > 0 && (
        <div className="space-y-1">
          <p className="text-xs font-medium text-muted">De bron</p>
          <Bronnen bronnen={b.bronnen} />
        </div>
      )}
      {b.toelichting && (
        <div data-door="lex">
          <p className="text-xs font-medium text-muted">Toelichting van Lex</p>
          <p className="break-words">{b.toelichting}</p>
        </div>
      )}
      {b.twijfel && (
        <div data-door="lex">
          <p className="text-xs font-medium text-muted">Twijfel of aanname</p>
          <p className="break-words">{b.twijfel}</p>
        </div>
      )}
      {b.voorstel && (
        <div className="border-l-2 border-l-aandacht-geel-rand bg-aandacht-geel-bg/40 py-2 pl-3 pr-2" data-toets-voorstel>
          <p className="text-xs font-medium text-aandacht-geel-tekst">
            {b.oordeel === "niet_in_de_bron" ? "Vraag van Lex" : "Voorstel van Lex"}
          </p>
          <p className="break-words">{b.voorstel}</p>
        </div>
      )}
      {beoordeling}
    </li>
  );
}

/** Waartegen getoetst is: de regelingen en de peildatum. */
export function GetoetstTegen({ blok }: { blok: Blok }) {
  const tegen = blok.getoetst_tegen.length ? blok.getoetst_tegen.join(", ") : "de wet- en regelgeving in de graaf";
  return (
    <p className="text-xs text-muted">
      Getoetst tegen {tegen}{blok.peildatum ? `, geldend op ${datumTekst(blok.peildatum)}` : ""}. Lex stelt voor; beoordeel het zelf.
    </p>
  );
}

/** De telling als labels; de voorlezer krijgt de zin. */
function Telling({ blok }: { blok: Blok }) {
  const n = aantallen(blok);
  return (
    <>
      <p className="sr-only">{tellingTekst(blok)}</p>
      <p className="flex flex-wrap gap-1.5" aria-hidden>
        {OORDELEN.filter((o) => n[o]).map((o) => (
          <StatusLabel key={o} toon={OORDEEL_TOON[o]} klein>{n[o]} {OORDEEL_LABEL[o].toLowerCase()}</StatusLabel>
        ))}
        {blok.ontbreekt.length > 0 && <StatusLabel toon="geel" klein>{blok.ontbreekt.length} ontbreekt</StatusLabel>}
      </p>
    </>
  );
}

export function VoorRedacteur({ blok }: { blok: Blok }) {
  if (!blok.voor_redacteur.length) return null;
  return (
    <div className="space-y-1.5" data-voor-redacteur>
      <h4 className="text-sm font-semibold text-ink">Voor de redacteur</h4>
      <ul className="list-disc space-y-1 pl-5">{blok.voor_redacteur.map((r, i) => <li key={i}>{r}</li>)}</ul>
    </div>
  );
}

const TOETSICOON = (
  <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <path d="M9 11l3 3 8-8" /><path d="M20 12v7a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h9" />
  </svg>
);

export function ContenttoetsBlok({ blok }: { blok: Blok }) {
  const opener = useOpenBron();
  const bericht = useContext(BerichtRunContext);
  // In de werkplek: een korte toelichting en de kaart; het rapport staat naast het gesprek.
  if (opener) {
    return (
      <section className="space-y-3" data-contenttoets="kort">
        <div className="space-y-1.5">
          <h3 className="text-sm font-semibold text-lint">Contenttoets</h3>
          <GetoetstTegen blok={blok} />
          <Telling blok={blok} />
        </div>
        <VoorRedacteur blok={blok} />
        <PaneelChip titel="Bekijk de contenttoets" sub={chipSub(tellingTekst(blok), "bekijken")} icoon={TOETSICOON}
          onClick={() => opener(contenttoetsContext(blok, bericht))} data-contenttoets-chip />
      </section>
    );
  }
  return (
    <section className="space-y-4" data-contenttoets>
      <div className="space-y-1.5">
        <h3 className="text-sm font-semibold text-lint">Contenttoets</h3>
        <GetoetstTegen blok={blok} />
        <Telling blok={blok} />
      </div>
      <VoorRedacteur blok={blok} />
      <div className="space-y-1.5">
        <h4 className="text-sm font-semibold text-ink">Per bewering</h4>
        <ol className="space-y-3">{blok.bevindingen.map((b) => <Bevinding key={b.nr} b={b} />)}</ol>
      </div>
      <Rest blok={blok} />
    </section>
  );
}

/** Wat ontbreekt en wat niet getoetst is: onder de bevindingen, in het gesprek en in het paneel. */
export function Rest({ blok }: { blok: Blok }) {
  return (
    <>
      {blok.ontbreekt.length > 0 && (
        <div className="space-y-1.5" data-toets-ontbreekt>
          <h4 className="text-sm font-semibold text-ink">Ontbreekt</h4>
          <ul className="space-y-3">
            {blok.ontbreekt.map((o, i) => <li key={i} className="space-y-1"><p>{o.tekst}</p><Bronnen bronnen={o.bronnen} /></li>)}
          </ul>
        </div>
      )}
      {blok.niet_getoetst.length > 0 && (
        <div className="space-y-1.5">
          <h4 className="text-sm font-semibold text-ink">Niet getoetst</h4>
          <ul className="list-disc space-y-1 pl-5 text-muted">{blok.niet_getoetst.map((r, i) => <li key={i}>{r}</li>)}</ul>
        </div>
      )}
    </>
  );
}
