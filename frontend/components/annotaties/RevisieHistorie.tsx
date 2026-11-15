"use client";

import { datumTijd } from "@/lib/datum";
import { Uitklap } from "@/components/ui/Uitklap";
import { Leeg } from "@/components/ui/Leeg";
import { useEffect, useState } from "react";
import { foutTekst } from "@/lib/api";
import type { NodeElement, NodeLaag } from "@/lib/annotatieNode";
import { jasStyle } from "@/lib/jas";
import { geraakteElementen, haalRevisies, revisieSamenvatting, type Revisie } from "@/lib/revisies";

/** Wie deed wat, wanneer – per revisie van de lagen in beeld. Alleen-lezend: de getoonde stand blijft
 *  de huidige, want de api bewaart geen oude inhoud. Een element dat in een revisie geraakt is, kies
 *  je met één klik, zodat het in tekst en lijst oplicht.
 *
 *  Pas bij openklappen geladen, en opnieuw zodra een laag in beeld een nieuwe revisie heeft. */
export function RevisieHistorie({ lagen, labelVan, elementen, onKies }: {
  lagen: NodeLaag[];
  labelVan: (bronIri: string) => string;
  elementen: NodeElement[];
  onKies: (elementId: string) => void;
}) {
  const stand = lagen.map((l) => `${l.id}:${l.revisie}`).join("|");
  const [geladen, setGeladen] = useState<Record<string, Revisie[]>>();
  const [fout, setFout] = useState("");
  const [open, setOpen] = useState(false);

  useEffect(() => {
    if (!open) return;
    let weg = false;
    Promise.all(stand.split("|").map((s) => s.split(":")[0]).filter(Boolean)
      .map((id) => haalRevisies(id).then((r) => [id, r] as const)))
      .then((paren) => { if (!weg) { setGeladen(Object.fromEntries(paren)); setFout(""); } },
        (e) => { if (!weg) setFout(foutTekst(e)); });
    return () => { weg = true; };
  }, [open, stand]);

  const perId = new Map(elementen.map((e) => [e.id, e]));
  const totaal = lagen.reduce((s, l) => s + l.revisie, 0);
  return (
    <Uitklap vorm="kader" data-testid="revisies"
      onToggle={(e) => setOpen((e.currentTarget as HTMLDetailsElement).open)} samenvatting={<>Historie <span className="font-normal text-faint">({totaal} {totaal === 1 ? "revisie" : "revisies"})</span></>}>
      {fout ? <p className="mt-2 text-xs text-aandacht-rood-tekst">{fout}</p>
        : !geladen ? <p className="mt-2 text-xs text-muted">Laden…</p>
        : lagen.map((laag) => {
          const lijst = geladen[laag.id] ?? [];
          return <div key={laag.id} className="mt-2">
            {lagen.length > 1 && <h4 className="text-[11px] font-semibold text-muted">{labelVan(laag.bron_iri)}</h4>}
            {!lijst.length ? <Leeg klein>Geen historie vastgelegd.</Leeg> : (
              <ol className="mt-1 space-y-1.5">
                {lijst.map((r) => <li key={r.revisie} className="text-xs">
                  <p className="text-ink">
                    <span className="font-mono text-faint">r{r.revisie}</span>{" "}
                    {revisieSamenvatting(r)}
                    <span className="text-muted"> · {r.actor} · {datumTijd(r.tijdstip)}</span>
                  </p>
                  {(() => {
                    const ids = geraakteElementen(r).filter((id) => perId.has(id));
                    if (!ids.length) return null;
                    return <span className="mt-0.5 flex flex-wrap gap-1">
                      {ids.map((id) => {
                        const el = perId.get(id)!;
                        return <button key={id} type="button" onClick={() => onKies(id)} title="Toon deze markering"
                          className={`focus-ring inline-flex min-h-[24px] max-w-[14rem] items-center truncate rounded px-1.5 py-0.5 text-[11px] coarse:min-h-[44px] ${jasStyle(el.klasse)} hover:ring-1 hover:ring-lint`}>
                          {el.tekst}
                        </button>;
                      })}
                    </span>;
                  })()}
                </li>)}
              </ol>
            )}
          </div>;
        })}
    </Uitklap>
  );
}
