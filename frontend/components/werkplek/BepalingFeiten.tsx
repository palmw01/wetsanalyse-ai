"use client";

import { useEffect, useState } from "react";

import { Melding } from "@/components/ui/Melding";
import { Skeleton } from "@/components/ui/Skeleton";
import type { AntwoordVindplaats } from "@/lib/antwoord";
import { afwijkendeToestand, haalBepalingDetail, plaatsZin, type BepalingDetail, type Telling } from "@/lib/bepalingDetail";
import { datumTekst } from "@/lib/graaf/knoopinfo";

/** Wat de graaf verder over de bepaling weet, onder de wettekst in het paneel naast het gesprek (ADR-008, *Detail bij een
 *  antwoord*): de plek in de opbouw, de geldigheid, de verwijzingen in beide richtingen, grondslag en bevoegdheid, waar ze
 *  genoemd wordt en welke begrippen ze definieert. Alleen lezen; de gegevens komen uit de graaf via de api, nooit uit wat
 *  Lex schreef. Een bepaling in de graaf opent in hetzelfde paneel. De ouder geeft een `key` per bepaling: een andere bepaling
 *  begint met een lege stand. */
export function BepalingFeiten({ bronIri, gelezenJci, onOpen }: {
  bronIri: string;
  /** De jci die Lex in de beurt las (met `&g=`): wijkt de toestand nu af, dan zegt het paneel dat. */
  gelezenJci?: string;
  onOpen: (v: AntwoordVindplaats) => void;
}) {
  const [d, setD] = useState<BepalingDetail | null | "fout">(null);
  useEffect(() => {
    let levend = true;
    haalBepalingDetail(bronIri).then((x) => levend && setD(x ?? "fout")).catch(() => levend && setD("fout"));
    return () => { levend = false; };
  }, [bronIri]);

  if (d === null) return <div className="space-y-2" data-bepaling-feiten="laden"><Skeleton className="h-4 w-40" /><Skeleton className="h-10 w-full" /></div>;
  if (d === "fout" || !d.beschikbaar) {
    return <Melding type="uitleg" compact><span data-bepaling-feiten="niet-beschikbaar">Wat de kennisgraaf verder over deze bepaling weet, is nu niet te lezen. De wettekst hierboven staat er wel.</span></Melding>;
  }
  const plek = plaatsZin(d.plaats);
  const toestand = afwijkendeToestand(gelezenJci, d.geldig_vanaf);
  return (
    <div className="space-y-4" data-bepaling-feiten="gereed">
      {(plek || d.vindplaats.regeling) && (
        <Blok kop="Plek in de regeling">
          <p className="text-sm text-ink" data-feit="plek">{[d.vindplaats.regeling, plek].filter(Boolean).join(" › ")}</p>
        </Blok>
      )}
      <Blok kop="Geldigheid">
        <ul className="space-y-0.5 text-sm text-ink">
          {d.inwerking && <li data-feit="inwerking">In werking sinds {datumTekst(d.inwerking)}</li>}
          {d.terugwerkend_tot && <li>Terugwerkende kracht tot {datumTekst(d.terugwerkend_tot)}</li>}
          {d.gewijzigd_bij && <li data-feit="gewijzigd">Laatst gewijzigd bij {d.gewijzigd_bij}</li>}
          {d.geldig_vanaf && <li data-feit="toestand">Tekst in de graaf geldt vanaf {datumTekst(d.geldig_vanaf)}</li>}
          {!d.inwerking && !d.gewijzigd_bij && !d.geldig_vanaf && <li className="text-muted">De graaf noemt geen datums.</li>}
        </ul>
        {toestand && (
          <p className="mt-1.5 text-xs text-muted" data-feit="toestand-afwijkend">
            Lex las de tekst die gold vanaf {datumTekst(toestand)}. De graaf draagt nu een nieuwere toestand: de tekst kan zijn veranderd.
          </p>
        )}
      </Blok>
      {d.verwijst_naar.length > 0 && (
        <Blok kop={`Verwijst naar (${d.verwijst_naar.length}${d.verwijst_naar_volledig ? "" : "+"})`}>
          <ul className="divide-y divide-line">
            {d.verwijst_naar.map((v) => (
              <li key={`${v.van.iri}|${v.naar.iri}|${v.anker}`} className="py-1.5 text-sm" data-feit="verwijst-naar">
                <span className="text-muted">{v.van.label}: </span>
                <Doel v={v.naar} open={v.in_graaf} onOpen={onOpen} />
                {v.anker && v.anker !== v.naar.label && <span className="block text-xs text-muted">“{v.anker}”</span>}
              </li>
            ))}
          </ul>
        </Blok>
      )}
      <TellingBlok kop="Wordt genoemd in" t={d.verwezen_door} open onOpen={onOpen} feit="verwezen-door" />
      <TellingBlok kop="Grondslag voor" t={d.grondslag_voor} onOpen={onOpen} feit="grondslag-voor" />
      <TellingBlok kop="Bevoegdheid voor" t={d.bevoegdheid_voor} onOpen={onOpen} feit="bevoegdheid-voor" />
      <TellingBlok kop="Regelingen die deze bepaling noemen" t={d.genoemd_in} onOpen={onOpen} feit="genoemd-in" />
      {d.definieert.length > 0 && (
        <Blok kop="Definieert">
          <p className="text-sm text-ink" data-feit="definieert">{d.definieert.join(", ")}</p>
        </Blok>
      )}
    </div>
  );
}

function Blok({ kop, children }: { kop: string; children: React.ReactNode }) {
  return <section><h3 className="mb-1.5 text-xs font-semibold uppercase tracking-wide text-faint">{kop}</h3>{children}</section>;
}

function Doel({ v, open, onOpen }: { v: AntwoordVindplaats; open: boolean; onOpen: (v: AntwoordVindplaats) => void }) {
  const tekst = v.regeling ? `${v.label}, ${v.regeling}` : v.label;
  if (!open || !v.iri.startsWith("urn:bwb:")) return <span className="text-ink">{tekst}</span>;
  return (
    <button type="button" onClick={() => onOpen(v)} className="focus-ring rounded text-left text-lint hover:underline">{tekst}</button>
  );
}

/** Een aantal met de eerste voorbeelden; de rest zit achter het aantal (het paneel is geen zoeklijst). */
function TellingBlok({ kop, t, open = false, onOpen, feit }: {
  kop: string; t: Telling; open?: boolean; onOpen: (v: AntwoordVindplaats) => void; feit: string;
}) {
  if (!t.aantal) return null;
  const meer = t.aantal - t.items.length;
  return (
    <Blok kop={`${kop} (${t.aantal})`}>
      <ul className="space-y-0.5 text-sm" data-feit={feit}>
        {t.items.map((v) => <li key={v.iri}><Doel v={v} open={open} onOpen={onOpen} /></li>)}
      </ul>
      {meer > 0 && <p className="mt-1 text-xs text-muted">en {meer} meer</p>}
    </Blok>
  );
}
