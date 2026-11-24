import Link from "next/link";

import { nodeLink } from "@/lib/annotatieNode";
import { bronVerwijderdZin, type BronVerwijderd } from "@/lib/annotatiePrullenbak";

/** Bij een begripkoppeling of de drager van een afleidingsregel waarvan de markering verdween omdat haar annotatie werd
 *  verwijderd: wanneer en door wie, en – zolang ze in de prullenbak ligt – de weg naar de bepaling, waar *Terugzetten*
 *  staat. In plaats van een passage die stil leeg is. */
export function BronVerwijderdRegel({ b }: { b: BronVerwijderd }) {
  return (
    <span className="mt-1 block text-xs text-aandacht-geel-tekst" data-bron-verwijderd={b.prullenbak_id ? "prullenbak" : "definitief"}>
      {bronVerwijderdZin(b)}
      {b.prullenbak_id && b.weergave && <>
        {" · "}
        <Link href={nodeLink({ bron_iri: b.weergave })} className="focus-ring rounded text-lint underline underline-offset-2 hover:no-underline">
          Naar de bepaling
        </Link>
      </>}
    </span>
  );
}
