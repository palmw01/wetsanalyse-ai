"use client";

import Link from "next/link";
import type { ReactNode } from "react";

import { Sectie, StatusLabel } from "@/components/ui/Lijst";
import { Melding } from "@/components/ui/Melding";
import { ObjectRij, ObjectRijen } from "@/components/ui/Pagina";
import { Skeleton } from "@/components/ui/Skeleton";
import { StandMelding } from "@/components/ui/StandMelding";
import { BepalingFeiten } from "@/components/werkplek/BepalingFeiten";
import { WettekstBlok } from "@/components/wettekst/WettekstBlok";
import { LIFECYCLE_LABEL } from "@/lib/annotatie";
import { nodeLink } from "@/lib/annotatieNode";
import type { AntwoordVindplaats } from "@/lib/antwoord";
import type { StandMeldingData } from "@/lib/herkomst";
import { jasStyle, klasseLabel } from "@/lib/jas";
import type { Lifecycle } from "@/lib/types";
import { useBepaling } from "@/lib/useBron";
import { elementPad } from "@/lib/werkgebiedPaden";

/** Het bronvenster van een bepaling (het bronvenster, PR 4): wat er onder de herkomstkop staat, in vaste blokken.
 *  1. de stand (alleen als er iets te melden is);
 *  2. de wettekst met de markeringen in hun JAS-kleur – een klik opent het element;
 *  3. de markeringen als lijst, met *Beoordelen in de annotatie*;
 *  4. wat de graaf weet: plek, geldigheid, verwijzingen in beide richtingen, grondslag, bevoegdheid, genoemd in, en de
 *     begrippen die ze definieert (`BepalingFeiten`). Een verwijzing opent als eigen tab.
 *  De kop (herkomst, *Samenhang*, ↗ naar de bronpagina) zet de schil: `ContextPaneel` naast het gesprek, `BronPagina` op
 *  de volledige pagina (`variant="pagina"`: de tekst groot, de markeringen als rijen naar hun pagina). Alleen lezen. */
export function BronVenster({ bronIri, meldingen, onOpenElement, onOpenBron, variant = "paneel", naGraaf, gekozen, beoordelenInKop = false }: {
  bronIri: string;
  /** *Beoordelen* staat in de kop (naast het gesprek: de laag op dezelfde tab); dan geen link naar de annotatiepagina. */
  beoordelenInKop?: boolean;
  /** De markering die in de graaf gekozen was (*Bekijk in de tekst*): extra nadruk in de wettekst. */
  gekozen?: string;
  variant?: "paneel" | "pagina";
  /** Op de pagina: wat er onder *Wat de graaf weet* nog bij hoort (alle gegevens uit de kennisgraaf, ingeklapt). */
  naGraaf?: ReactNode;
  meldingen: readonly StandMeldingData[];
  onOpenElement: (id: string, titel: string) => void;
  onOpenBron: (v: AntwoordVindplaats) => void;
}) {
  const { view, actueel, fout } = useBepaling(bronIri);
  if (fout) return <Melding type="fout" compact>{fout}</Melding>;
  if (!view) return <div className="space-y-2"><Skeleton className="h-4 w-48" /><Skeleton className="h-16 w-full" /></div>;
  const openElement = (id: string) => {
    const e = actueel.find((x) => x.id === id);
    onOpenElement(id, e ? `${klasseLabel(e.klasse)} · “${e.tekst}”` : "");
  };
  return (
    <div className="space-y-5" data-bronvenster={bronIri}>
      <StandMelding meldingen={meldingen} />
      <Sectie titel="Wettekst" niveau={3} data-blok="wettekst">
        <WettekstBlok groot={variant === "pagina"} segmenten={view.segmenten} elementen={actueel} gekozen={gekozen} kiesbaar={() => true} onKies={openElement} />
      </Sectie>
      <Sectie titel="Markeringen" telling={actueel.length} niveau={3} data-blok="markeringen"
        acties={!beoordelenInKop && <Link href={nodeLink({ bron_iri: bronIri })} className="focus-ring rounded text-xs font-medium text-lint hover:underline">
          Beoordelen in de annotatie</Link>}>
        {variant === "pagina" ? (
          <ObjectRijen label="JAS-elementen" leeg="Deze bepaling is nog niet geannoteerd. Vraag Lex in het gesprek om haar te annoteren.">
            {actueel.map((e) => (
              <ObjectRij key={e.id} href={elementPad(e.id)} data-element-rij={e.id} titel={<>“{e.tekst}”</>}
                sub={<span className={`inline-block rounded border px-1.5 text-[0.7rem] ${jasStyle(e.klasse)}`}>{klasseLabel(e.klasse)}</span>}
                status={<StatusLabel toon={e.lifecycle === "human_approved" ? "groen" : "neutraal"}>
                  {LIFECYCLE_LABEL[e.lifecycle as Lifecycle] ?? e.lifecycle}</StatusLabel>} />
            ))}
          </ObjectRijen>
        ) : actueel.length === 0 ? <p className="text-sm text-muted">Nog niet geannoteerd.</p> : (
          <ul className="divide-y divide-line">
            {actueel.map((e) => (
              <li key={e.id}>
                <button type="button" onClick={() => openElement(e.id)} data-context-element={e.id}
                  className="focus-ring flex w-full items-center gap-2 rounded-md px-1 py-2 text-left hover:bg-surface">
                  <span className={`shrink-0 rounded border px-1.5 text-[0.7rem] ${jasStyle(e.klasse)}`}>{klasseLabel(e.klasse)}</span>
                  <span className="min-w-0 flex-1 truncate text-sm text-ink">“{e.tekst}”</span>
                  <StatusLabel>{LIFECYCLE_LABEL[e.lifecycle as Lifecycle] ?? e.lifecycle}</StatusLabel>
                </button>
              </li>
            ))}
          </ul>
        )}
      </Sectie>
      <Sectie titel="Wat de graaf weet" niveau={3} data-blok="graaf">
        <BepalingFeiten key={bronIri} bronIri={bronIri} onOpen={onOpenBron} />
        {naGraaf}
      </Sectie>
    </div>
  );
}
