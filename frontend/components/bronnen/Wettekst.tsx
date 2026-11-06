"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { KnoopTekst } from "@/components/graaf/KnoopTekst";
import { haalNodeWeergave, type NodeWeergave } from "@/lib/annotatieNode";
import { foutTekst } from "@/lib/api";
import { bronPad } from "@/lib/werkgebiedPaden";

/** De wettekst van een bepaling, uitgeklapt naast het gesprek: lezen zonder de werkplek te verlaten. De pagina van
 *  de bepaling blijft één klik verder. */
export function Wettekst({ bronIri, werkgebiedId, className = "mx-4 mb-2" }: { bronIri: string; werkgebiedId?: string; className?: string }) {
  const [view, setView] = useState<NodeWeergave | null>(null);
  const [fout, setFout] = useState<string | null>(null);
  useEffect(() => {
    let levend = true;
    haalNodeWeergave({ bron_iri: bronIri }).then((v) => { if (levend) setView(v); })
      .catch((e) => { if (levend) setFout(foutTekst(e, "De tekst kon niet worden geladen.")); });
    return () => { levend = false; };
  }, [bronIri]);
  const actueel = (view?.elementen ?? []).filter((e) => !e.verouderd && e.lifecycle !== "rejected");
  return (
    <div className={`rounded-kaart border border-line bg-surface/60 px-3 py-2.5 ${className}`} data-wettekst={bronIri}>
      {fout ? <p className="text-sm text-muted">{fout}</p>
        : view ? <KnoopTekst segmenten={view.segmenten} elementen={actueel} kiesbaar={() => false} onKies={() => {}} />
          : <p className="text-sm text-muted">Tekst laden…</p>}
      <Link href={bronPad(bronIri, werkgebiedId)} className="focus-ring mt-2 inline-block rounded text-xs font-medium text-lint hover:underline">
        Open de bepaling
      </Link>
    </div>
  );
}
