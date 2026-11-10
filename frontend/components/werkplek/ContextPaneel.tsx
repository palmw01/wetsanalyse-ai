"use client";

import { HerkomstRegel } from "@/components/ui/HerkomstRegel";
import { PaneelKop } from "@/components/ui/PaneelKop";
import { StandMelding } from "@/components/ui/StandMelding";
import Link from "next/link";
import { createContext, useEffect, useState } from "react";

import { BepalingFeiten } from "@/components/werkplek/BepalingFeiten";
import { WaaromUitklap } from "@/components/annotaties/WaaromUitklap";
import { OverzichtPaneel } from "@/components/werkplek/OverzichtPaneel";
import { Dialog, type DialogVariant } from "@/components/ui/Dialog";
import { StatusLabel } from "@/components/ui/Lijst";
import { Melding } from "@/components/ui/Melding";
import { Skeleton } from "@/components/ui/Skeleton";
import { LIFECYCLE_LABEL } from "@/lib/annotatie";
import { haalElementDetail, nodeLink, type ElementDetail } from "@/lib/annotatieNode";
import { useBepaling } from "@/lib/useBron";
import { WettekstBlok } from "@/components/wettekst/WettekstBlok";
import { foutTekst, haalWerkgebied } from "@/lib/api";
import { jasStyle, klasseLabel } from "@/lib/jas";
import { herkomstKop, vindplaatsTekst, type StandMeldingData } from "@/lib/herkomst";
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
  | { soort: "overzicht"; overzicht: Overzicht; titel: string };

/** Opent een context naast het gesprek. Alleen binnen de werkplek (`WerkplekClient`); daarbuiten is er
 *  geen gesprek om naast te staan en tonen de aanroepers deze handeling niet. */
export const ContextPaneelContext = createContext<((doel: ContextDoel) => void) | null>(null);

const KOP: Record<ContextDoel["soort"], string> = {
  bron: "Bepaling", element: "JAS-element", bibliotheek: "Bronnen van dit werkgebied", overzicht: "Overzicht uit de kennisgraaf",
};

export function contextSleutel(d: ContextDoel): string {
  return d.soort === "bron" ? `bron:${d.bron_iri}:${d.werkgebied_id ?? ""}`
    : d.soort === "element" ? `element:${d.element_id}`
    : d.soort === "overzicht" ? `overzicht:${d.overzicht.gevraagd}` : `bibliotheek:${d.werkgebied_id}`;
}

export function overzichtContext(overzicht: Overzicht): ContextDoel {
  return { soort: "overzicht", overzicht, titel: overzicht.gevraagd };
}

/** De volledige pagina van wat het paneel toont: daar werk je verder (beoordelen, opnemen). Een overzicht
 *  bestaat alleen in zijn bericht en heeft er geen. */
export function paginaVanContext(d: ContextDoel): string | undefined {
  return d.soort === "bron" ? bronPad(d.bron_iri, d.werkgebied_id)
    : d.soort === "element" ? elementPad(d.element_id)
    : d.soort === "overzicht" ? undefined : projectPad(d.werkgebied_id, "bronnen");
}

/** Het contextpaneel (spoor G4, mock-up v4 `sideRail`): dezelfde schil als de artefacten – een kolom vanaf
 *  1280px, anders een sheet –, met bovenaan *Open volledige pagina*. Het paneel is om te raadplegen, niet
 *  om in te werken: beoordelen gebeurt op de pagina. Een paneel is geen vervanging van die pagina. */
export function ContextPaneel({ doel, variant, onSluit, onVerberg, onWissel, onMaakWerkgebied }: {
  doel: ContextDoel;
  variant: DialogVariant;
  onSluit: () => void;
  /** Escape: het paneel verbergen (inklappen, of de sheet weg) zonder de tab te sluiten. Zonder: Escape sluit. */
  onVerberg?: () => void;
  /** Iets anders in hetzelfde paneel openen (een element uit de bepaling, een bron uit de lijst). */
  onWissel: (doel: ContextDoel) => void;
  /** *Maak hier een werkgebied van* bij een overzicht. */
  onMaakWerkgebied?: (overzicht: Overzicht) => void;
}) {
  // Een bepaling krijgt de kop van haar herkomst: de bepaling als titel, regeling · plek · stand · bron eronder.
  const bron = useBronHerkomst(doel.soort === "bron" ? doel : undefined);
  const kop = bron.herkomst ? herkomstKop(bron.herkomst) : { soort: KOP[doel.soort], titel: doel.titel || KOP[doel.soort] };
  return (
    <Dialog label={`${kop.soort}: ${kop.titel}`} variant={variant} onSluit={onSluit} onEscape={onVerberg}>
      <div data-context-paneel={doel.soort} className="flex min-h-0 flex-1 flex-col">
        <PaneelKop soort={kop.soort} titel={kop.titel} pagina={paginaVanContext(doel)} onSluit={onSluit}
          status={bron.herkomst && <HerkomstRegel herkomst={bron.herkomst} />} />
        <div className="min-h-0 flex-1 space-y-4 overflow-y-auto px-5 py-4">
          {doel.soort === "bron" ? <BronInhoud doel={doel} onWissel={onWissel} meldingen={bron.meldingen} />
            : doel.soort === "element" ? <ElementInhoud id={doel.element_id} />
            : doel.soort === "overzicht" ? <OverzichtPaneel overzicht={doel.overzicht} onMaakWerkgebied={onMaakWerkgebied} />
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

function BronInhoud({ doel, onWissel, meldingen }: {
  doel: Extract<ContextDoel, { soort: "bron" }>; onWissel: (d: ContextDoel) => void; meldingen: StandMeldingData[];
}) {
  const { view, actueel, fout } = useBepaling(doel.bron_iri);
  if (fout) return <Melding type="fout" compact>{fout}</Melding>;
  if (!view) return <Laden />;
  const openElement = (id: string) => {
    const e = actueel.find((x) => x.id === id);
    onWissel({ soort: "element", element_id: id, titel: e ? `${klasseLabel(e.klasse)} · “${e.tekst}”` : "" });
  };
  return <>
    <StandMelding meldingen={meldingen} />
    <section>
      <Kop>Wettekst</Kop>
      <WettekstBlok segmenten={view.segmenten} elementen={actueel} kiesbaar={() => true} onKies={openElement} />
    </section>
    <section>
      <Kop>JAS-elementen ({actueel.length})</Kop>
      {actueel.length === 0 ? <p className="text-sm text-muted">Nog niet geannoteerd.</p> : (
        <ul className="divide-y divide-line">
          {actueel.map((e) => (
            <li key={e.id}>
              <button type="button" onClick={() => openElement(e.id)} data-context-element={e.id}
                className="focus-ring flex w-full items-center gap-2 rounded-md px-1 py-2 text-left hover:bg-surface">
                <span className={`shrink-0 rounded border px-1.5 text-[0.7rem] ${jasStyle(e.klasse)}`}>{klasseLabel(e.klasse)}</span>
                <span className="min-w-0 flex-1 truncate text-sm text-ink">“{e.tekst}”</span>
                <span className="shrink-0 text-xs text-muted">{LIFECYCLE_LABEL[e.lifecycle as Lifecycle] ?? e.lifecycle}</span>
              </button>
            </li>
          ))}
        </ul>
      )}
      <Link href={nodeLink({ bron_iri: doel.bron_iri })} className="focus-ring mt-2 inline-block rounded text-xs font-medium text-lint hover:underline">
        Beoordelen in de annotatie
      </Link>
    </section>
    <BepalingFeiten key={doel.bron_iri} bronIri={doel.bron_iri}
      onOpen={(v) => onWissel({ soort: "bron", bron_iri: v.iri, werkgebied_id: doel.werkgebied_id, titel: vindplaatsTekst(v) })} />
  </>;
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
