"use client";

import Link from "next/link";

import { plekNaam } from "@/lib/bronKandidaten";
import { duidingZin, onderbouwingKop } from "@/lib/kaartVoorstel";
import type { DefinitieOnderbouwing as Onderbouwing } from "@/lib/types";
import { bronPad } from "@/lib/werkgebiedPaden";

/** Waarop een overgenomen definitie rust (spoor M): de fragmenten uit de bron met hun vindplaats, of bij
 *  een letterlijke definitie de bepaling zelf, en de duiding van Lex. Dezelfde vorm als het fragmentblok
 *  bij een voorstel (`KaartVoorstel`), zodat de onderbouwing na het overnemen niet uit beeld verdwijnt.
 *  Alleen lezen; een link opent de bepaling. */
export function DefinitieOnderbouwing({ onderbouwing: o, werkgebiedId }: { onderbouwing: Onderbouwing; werkgebiedId: string }) {
  const bron = o.herkomst === "letterlijk" && o.definitie_bron_iri && !o.fragmenten.length ? o.definitie_bron_iri : "";
  return (
    <details className="mt-1 text-xs" data-definitie-onderbouwing>
      <summary className="focus-ring cursor-pointer rounded text-muted">{onderbouwingKop(o)}</summary>
      <ul className="mt-1 space-y-1 pl-1 text-ink">
        {o.fragmenten.map((f) => (
          <li key={`${f.bron_iri}:${f.start}:${f.eind}`}>
            “{f.tekst}”{" "}
            <Link href={bronPad(f.bron_iri, werkgebiedId)} className="focus-ring rounded text-lint hover:underline">
              {plekNaam(f.bron_iri)}
            </Link>
          </li>
        ))}
        {bron && (
          <li>
            <Link href={bronPad(bron, werkgebiedId)} className="focus-ring rounded text-lint hover:underline">
              {o.definitie_vindplaats || plekNaam(bron)}
            </Link>
          </li>
        )}
      </ul>
      {o.duiding && <p className="mt-1 text-muted">{duidingZin(o.duiding)}</p>}
    </details>
  );
}
