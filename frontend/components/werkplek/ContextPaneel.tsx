"use client";

import { PaneelKop } from "@/components/ui/PaneelKop";
import Link from "next/link";
import { createContext, useEffect, useState } from "react";

import { KnoopTekst } from "@/components/graaf/KnoopTekst";
import { WaaromUitklap } from "@/components/annotaties/WaaromUitklap";
import { Dialog, type DialogVariant } from "@/components/ui/Dialog";
import { StatusLabel } from "@/components/ui/Lijst";
import { Melding } from "@/components/ui/Melding";
import { Skeleton } from "@/components/ui/Skeleton";
import { LIFECYCLE_LABEL } from "@/lib/annotatie";
import { haalElementDetail, haalNodeWeergave, nodeLink, type ElementDetail, type NodeWeergave } from "@/lib/annotatieNode";
import { foutTekst, haalWerkgebied } from "@/lib/api";
import { jasStyle, klasseLabel } from "@/lib/jas";
import type { Lifecycle, Werkgebied } from "@/lib/types";
import { ROL_LABEL } from "@/lib/werkgebied";
import { bronPad, elementPad, projectPad } from "@/lib/werkgebiedPaden";

/** Wat het contextpaneel naast het gesprek kan tonen naast de artefacten van een beurt (spoor G4): een
 *  bepaling, één JAS-element, of de bronnen van het werkgebied van het gesprek. Geen bericht in het
 *  gesprek: puur om te raadplegen terwijl je praat. */
export type ContextDoel =
  | { soort: "bron"; bron_iri: string; werkgebied_id?: string; titel: string }
  | { soort: "element"; element_id: string; titel: string }
  | { soort: "bibliotheek"; werkgebied_id: string; titel: string };

/** Opent een context naast het gesprek. Alleen binnen de werkplek (`WerkplekClient`); daarbuiten is er
 *  geen gesprek om naast te staan en tonen de aanroepers deze handeling niet. */
export const ContextPaneelContext = createContext<((doel: ContextDoel) => void) | null>(null);

const KOP: Record<ContextDoel["soort"], string> = {
  bron: "Bepaling", element: "JAS-element", bibliotheek: "Bronnen van dit werkgebied",
};

export function contextSleutel(d: ContextDoel): string {
  return d.soort === "bron" ? `bron:${d.bron_iri}:${d.werkgebied_id ?? ""}`
    : d.soort === "element" ? `element:${d.element_id}` : `bibliotheek:${d.werkgebied_id}`;
}

/** De volledige pagina van wat het paneel toont: daar werk je verder (beoordelen, opnemen). */
export function paginaVanContext(d: ContextDoel): string {
  return d.soort === "bron" ? bronPad(d.bron_iri, d.werkgebied_id)
    : d.soort === "element" ? elementPad(d.element_id) : projectPad(d.werkgebied_id, "bronnen");
}

/** Het contextpaneel (spoor G4, mock-up v4 `sideRail`): dezelfde schil als de artefacten – een kolom vanaf
 *  1280px, anders een sheet –, met bovenaan *Open volledige pagina*. Het paneel is om te raadplegen, niet
 *  om in te werken: beoordelen gebeurt op de pagina. Een paneel is geen vervanging van die pagina. */
export function ContextPaneel({ doel, variant, onSluit, onWissel }: {
  doel: ContextDoel;
  variant: DialogVariant;
  onSluit: () => void;
  /** Iets anders in hetzelfde paneel openen (een element uit de bepaling, een bron uit de lijst). */
  onWissel: (doel: ContextDoel) => void;
}) {
  const titel = doel.titel || KOP[doel.soort];
  return (
    <Dialog label={`${KOP[doel.soort]}: ${titel}`} variant={variant} onSluit={onSluit}>
      <div data-context-paneel={doel.soort} className="flex min-h-0 flex-1 flex-col">
        <PaneelKop soort={KOP[doel.soort]} titel={titel} pagina={paginaVanContext(doel)} onSluit={onSluit} />
        <div className="min-h-0 flex-1 space-y-4 overflow-y-auto px-5 py-4">
          {doel.soort === "bron" ? <BronInhoud doel={doel} onWissel={onWissel} />
            : doel.soort === "element" ? <ElementInhoud id={doel.element_id} />
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

function BronInhoud({ doel, onWissel }: { doel: Extract<ContextDoel, { soort: "bron" }>; onWissel: (d: ContextDoel) => void }) {
  const [view, setView] = useState<NodeWeergave | null>(null);
  const [fout, setFout] = useState<string | null>(null);
  useEffect(() => {
    let levend = true;
    haalNodeWeergave({ bron_iri: doel.bron_iri })
      .then((v) => levend && setView(v))
      .catch((e) => levend && setFout(foutTekst(e, "De bepaling kon niet worden geladen.")));
    return () => { levend = false; };
  }, [doel.bron_iri]);
  if (fout) return <Melding type="fout" compact>{fout}</Melding>;
  if (!view) return <Laden />;
  const actueel = view.elementen.filter((e) => !e.verouderd && e.lifecycle !== "rejected");
  const openElement = (id: string) => {
    const e = actueel.find((x) => x.id === id);
    onWissel({ soort: "element", element_id: id, titel: e ? `${klasseLabel(e.klasse)} · “${e.tekst}”` : "" });
  };
  return <>
    <section>
      <Kop>Wettekst</Kop>
      <KnoopTekst segmenten={view.segmenten} elementen={actueel} kiesbaar={() => true} onKies={openElement} />
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
      <KnoopTekst segmenten={d.bronnen} elementen={[el]} kiesbaar={() => false} onKies={() => {}} />
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
                  onClick={() => onWissel({ soort: "bron", bron_iri: b.bron_iri, werkgebied_id: werkgebiedId, titel: b.label || "Bepaling" })}
                  className="focus-ring block w-full rounded-md px-1 py-2 text-left hover:bg-surface">
                  <span className="block text-sm font-medium text-ink">{b.label || "Bepaling"}</span>
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
