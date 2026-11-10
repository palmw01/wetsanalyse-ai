"use client";

import { GraafIcoon } from "@/components/graaf/GraafIcoon";
import { knopKlasse } from "@/components/ui/Button";
import { HerkomstRegel } from "@/components/ui/HerkomstRegel";
import { BronVenster } from "@/components/wettekst/BronVenster";
import { PaneelKop } from "@/components/ui/PaneelKop";
import { createContext, useEffect, useState } from "react";

import { WaaromUitklap } from "@/components/annotaties/WaaromUitklap";
import { OverzichtPaneel } from "@/components/werkplek/OverzichtPaneel";
import { Dialog, type DialogVariant } from "@/components/ui/Dialog";
import { StatusLabel } from "@/components/ui/Lijst";
import { Melding } from "@/components/ui/Melding";
import { Skeleton } from "@/components/ui/Skeleton";
import { LIFECYCLE_LABEL } from "@/lib/annotatie";
import { haalElementDetail, type ElementDetail } from "@/lib/annotatieNode";
import { WettekstBlok } from "@/components/wettekst/WettekstBlok";
import { foutTekst, haalWerkgebied } from "@/lib/api";
import { jasStyle, klasseLabel } from "@/lib/jas";
import { herkomstKop, vindplaatsTekst } from "@/lib/herkomst";
import { stukHerkomst, type StukPassage } from "@/lib/bronStuk";
import { useStuk } from "@/lib/useStuk";
import { StukVenster } from "@/components/wettekst/StukVenster";
import { contextSleutelVan } from "@/lib/paneelTabs";
import type { Lifecycle, Overzicht, Werkgebied } from "@/lib/types";
import { useBronHerkomst } from "@/lib/useBronHerkomst";
import { ROL_LABEL } from "@/lib/werkgebied";
import { bronPad, elementPad, projectPad } from "@/lib/werkgebiedPaden";

/** Wat het contextpaneel naast het gesprek kan tonen naast de artefacten van een beurt (spoor G4): een
 *  bepaling, één JAS-element, de bronnen van het werkgebied van het gesprek, of het overzicht van een
 *  onderwerp. Dat laatste komt uit het bericht zelf: het hoort bij een antwoord, niet bij een werkgebied. */
export type ContextDoel =
  | { soort: "bron"; bron_iri: string; werkgebied_id?: string; titel: string; /** De jci die Lex las, met de toestand. */ jci?: string }
  | { soort: "element"; element_id: string; titel: string }
  | { soort: "bibliotheek"; werkgebied_id: string; titel: string }
  | { soort: "overzicht"; overzicht: Overzicht; titel: string }
  /** Een stuk uit een bronconnector (ADR-013, het bronvenster PR 6): het brontype (of de naam) van de connector en het
   *  id. `gelezen` en `voorbeeld` komen uit het antwoord: wat Lex las, en wat het venster toont als de bron weg is. */
  | { soort: "stuk"; brontype: string; id: string; titel: string;
      gelezen?: { bron_hash: string; passages: number[] }; voorbeeld?: StukPassage[] };

/** Opent een context naast het gesprek. Alleen binnen de werkplek (`WerkplekClient`); daarbuiten is er
 *  geen gesprek om naast te staan en tonen de aanroepers deze handeling niet. */
export const ContextPaneelContext = createContext<((doel: ContextDoel) => void) | null>(null);

const KOP: Record<ContextDoel["soort"], string> = {
  bron: "Bepaling", element: "JAS-element", bibliotheek: "Bronnen van dit werkgebied", overzicht: "Overzicht uit de kennisgraaf",
  stuk: "Stuk",
};

/** De sleutel van een context: één plek (`lib/paneelTabs.ts`), ook voor de tabs. */
export function contextSleutel(d: ContextDoel): string {
  return contextSleutelVan(d);
}

export function overzichtContext(overzicht: Overzicht): ContextDoel {
  return { soort: "overzicht", overzicht, titel: overzicht.gevraagd };
}

/** De volledige pagina van wat het paneel toont: daar werk je verder (beoordelen, opnemen). Een overzicht
 *  bestaat alleen in zijn bericht en heeft er geen. */
export function paginaVanContext(d: ContextDoel): string | undefined {
  return d.soort === "bron" ? bronPad(d.bron_iri, d.werkgebied_id)
    : d.soort === "element" ? elementPad(d.element_id)
    : d.soort === "overzicht" || d.soort === "stuk" ? undefined : projectPad(d.werkgebied_id, "bronnen");
}

/** Het contextpaneel (spoor G4, mock-up v4 `sideRail`): dezelfde schil als de artefacten – een kolom vanaf
 *  1280px, anders een sheet –, met bovenaan *Open volledige pagina*. Het paneel is om te raadplegen, niet
 *  om in te werken: beoordelen gebeurt op de pagina. Een paneel is geen vervanging van die pagina. */
export function ContextPaneel({ doel, variant, onSluit, onVerberg, onWissel, onMaakWerkgebied, onSamenhang }: {
  doel: ContextDoel;
  variant: DialogVariant;
  onSluit: () => void;
  /** Escape: het paneel verbergen (inklappen, of de sheet weg) zonder de tab te sluiten. Zonder: Escape sluit. */
  onVerberg?: () => void;
  /** Iets anders in hetzelfde paneel openen (een element uit de bepaling, een bron uit de lijst). */
  onWissel: (doel: ContextDoel) => void;
  /** *Samenhang* in de kop van een bepaling: haar plek in de graaf, als tab naast deze (de werkplek, als de api de
   *  samenhang kent). */
  onSamenhang?: (bronIri: string) => void;
  /** *Maak hier een werkgebied van* bij een overzicht. */
  onMaakWerkgebied?: (overzicht: Overzicht) => void;
}) {
  // Een bepaling krijgt de kop van haar herkomst: de bepaling als titel, regeling · plek · stand · bron eronder.
  const bron = useBronHerkomst(doel.soort === "bron" ? doel : undefined);
  // Een stuk uit een bronconnector: dezelfde kop, uit de beschrijving van de connector en de metadata van het stuk.
  const stuk = useStuk(doel.soort === "stuk" ? doel : null);
  const herkomst = bron.herkomst ?? (doel.soort === "stuk"
    ? stukHerkomst(stuk.stand?.antwoord.beschrijving, stuk.stand?.antwoord.deel.stuk, doel.titel) : undefined);
  const kop = herkomst ? { soort: doel.soort === "stuk" ? stuk.stand?.antwoord.beschrijving.label ?? KOP.stuk : herkomstKop(herkomst).soort,
    titel: herkomst.bepaling } : { soort: KOP[doel.soort], titel: doel.titel || KOP[doel.soort] };
  return (
    <Dialog label={`${kop.soort}: ${kop.titel}`} variant={variant} onSluit={onSluit} onEscape={onVerberg}>
      <div data-context-paneel={doel.soort} className="flex min-h-0 flex-1 flex-col">
        <PaneelKop soort={kop.soort} titel={kop.titel} pagina={paginaVanContext(doel)} onSluit={onSluit}
          status={herkomst && <HerkomstRegel herkomst={herkomst} />}
          hoofdactie={doel.soort === "bron" && onSamenhang && (
            <button type="button" onClick={() => onSamenhang(doel.bron_iri)} data-bron-samenhang
              className={`${knopKlasse("secondary", "xs")} gap-1`}><GraafIcoon />Samenhang</button>
          )} />
        <div className="min-h-0 flex-1 space-y-4 overflow-y-auto px-5 py-4">
          {doel.soort === "bron" ? <BronVenster bronIri={doel.bron_iri} meldingen={bron.meldingen}
              onOpenElement={(id, titel) => onWissel({ soort: "element", element_id: id, titel })}
              onOpenBron={(v) => onWissel({ soort: "bron", bron_iri: v.iri, werkgebied_id: doel.werkgebied_id, titel: vindplaatsTekst(v) })} />
            : doel.soort === "element" ? <ElementInhoud id={doel.element_id} />
            : doel.soort === "overzicht" ? <OverzichtPaneel overzicht={doel.overzicht} onMaakWerkgebied={onMaakWerkgebied} />
            : doel.soort === "stuk" ? <StukVenster stuk={stuk} gelezen={doel.gelezen} voorbeeld={doel.voorbeeld}
              onOpenStuk={(v) => onWissel({ soort: "stuk", brontype: doel.brontype, id: v.id, titel: v.label })} />
            : <BibliotheekInhoud werkgebiedId={doel.werkgebied_id} onWissel={onWissel} />}
        </div>
      </div>
    </Dialog>
  );
}

function Laden() {
  return <div className="space-y-2"><Skeleton className="h-4 w-48" /><Skeleton className="h-16 w-full" /></div>;
}

function Kop({ children }: { children: React.ReactNode }) {
  return <h3 className="mb-1.5 text-xs font-semibold uppercase tracking-wide text-faint">{children}</h3>;
}

function ElementInhoud({ id }: { id: string }) {
  const [d, setD] = useState<ElementDetail | null>(null);
  const [fout, setFout] = useState<string | null>(null);
  useEffect(() => {
    let levend = true;
    haalElementDetail(id).then((x) => levend && setD(x))
      .catch((e) => levend && setFout(foutTekst(e, "Dit element kon niet worden geladen.")));
    return () => { levend = false; };
  }, [id]);
  if (fout) return <Melding type="fout" compact>{fout}</Melding>;
  if (!d) return <Laden />;
  const el = d.element;
  return <>
    <div className="flex flex-wrap items-center gap-1.5">
      <span className={`rounded border px-2 py-0.5 text-xs font-medium ${jasStyle(el.klasse)}`}>{klasseLabel(el.klasse)}</span>
      <StatusLabel toon={el.lifecycle === "human_approved" ? "groen" : "neutraal"}>
        {LIFECYCLE_LABEL[el.lifecycle as Lifecycle] ?? el.lifecycle}
      </StatusLabel>
      {el.aandacht === "geel" && <StatusLabel toon="geel">Keuze voor jou</StatusLabel>}
    </div>
    <section>
      <Kop>Bronvoorkomen</Kop>
      <WettekstBlok segmenten={d.bronnen} elementen={[el]} />
    </section>
    {el.toelichting?.trim() && <section><Kop>Toelichting</Kop><p className="text-sm text-ink">{el.toelichting}</p></section>}
    {el.review_uitleg && <section><Kop>Review</Kop><p className="text-sm text-ink">{el.review_uitleg}</p></section>}
    <WaaromUitklap el={el} />
    <p className="text-xs text-muted">Accorderen of afwijzen doe je op de volledige pagina.</p>
  </>;
}

function BibliotheekInhoud({ werkgebiedId, onWissel }: { werkgebiedId: string; onWissel: (d: ContextDoel) => void }) {
  const [wg, setWg] = useState<Werkgebied | null>(null);
  const [fout, setFout] = useState<string | null>(null);
  useEffect(() => {
    let levend = true;
    haalWerkgebied(werkgebiedId).then((w) => levend && setWg(w))
      .catch((e) => levend && setFout(foutTekst(e, "Het werkgebied kon niet worden geladen.")));
    return () => { levend = false; };
  }, [werkgebiedId]);
  if (fout) return <Melding type="fout" compact>{fout}</Melding>;
  if (!wg) return <Laden />;
  return <>
    <p className="text-xs text-muted">Open een bron naast het gesprek; je blijft in hetzelfde gesprek.</p>
    {(["analyseren", "context"] as const).map((rol) => {
      const lijst = wg.bronnen.filter((b) => b.rol === rol);
      if (!lijst.length) return null;
      return (
        <section key={rol}>
          <Kop>{rol === "analyseren" ? "Om te analyseren" : ROL_LABEL.context}</Kop>
          <ul className="divide-y divide-line">
            {lijst.map((b) => (
              <li key={b.id}>
                <button type="button" data-context-bron={b.id}
                  onClick={() => onWissel({ soort: "bron", bron_iri: b.bron_iri, werkgebied_id: werkgebiedId, titel: vindplaatsTekst({ iri: b.bron_iri, label: b.label }) })}
                  className="focus-ring block w-full rounded-md px-1 py-2 text-left hover:bg-surface">
                  <span className="block text-sm font-medium text-ink">{vindplaatsTekst({ iri: b.bron_iri, label: b.label })}</span>
                  {b.reden && <span className="block text-xs text-muted">{b.reden}</span>}
                </button>
              </li>
            ))}
          </ul>
        </section>
      );
    })}
    {wg.bronnen.length === 0 && <p className="text-sm text-muted">Nog geen bronnen in dit werkgebied.</p>}
  </>;
}
