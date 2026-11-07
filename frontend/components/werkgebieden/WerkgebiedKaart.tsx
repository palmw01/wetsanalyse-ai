"use client";

import Link from "next/link";

import { knopKlasse } from "@/components/ui/Button";
import { KaartActies } from "@/components/ui/Pagina";
import { VerwijderKnop } from "@/components/ui/VerwijderKnop";
import type { WerkgebiedSamenvatting } from "@/lib/types";
import { STATUS_LABEL } from "@/lib/werkgebied";
import { StatusLabel } from "@/components/ui/Lijst";

const datum = (iso: string) =>
  new Date(iso).toLocaleDateString("nl-NL", { day: "numeric", month: "short", year: "numeric" });

/** Eén werkgebied in het overzicht, in de vorm van `AnnotatieKaart`: de naam is de link (de hele kaart
 *  aanklikbaar maken zou de knoppen onbereikbaar maken voor het toetsenbord), onderaan *Openen* en
 *  *Verwijderen*. */
export function WerkgebiedKaart({ wg, onVerwijder }: { wg: WerkgebiedSamenvatting; onVerwijder: () => Promise<void> }) {
  const href = `/werkgebieden/${encodeURIComponent(wg.id)}`;
  return (
    <article data-werkgebied-kaart={wg.id}
      className="flex min-w-0 flex-col gap-3 rounded-kaart border border-line bg-paper p-4 shadow-zacht transition hover:-translate-y-0.5 hover:border-lint/40 hover:shadow-kaart motion-reduce:hover:translate-y-0">
      <div className="flex items-start justify-between gap-3">
        <h3 className="min-w-0 truncate font-display text-sm font-semibold text-lint">
          <Link href={href} className="focus-ring rounded hover:underline">{wg.naam}</Link>
        </h3>
        <StatusLabel>{STATUS_LABEL[wg.status]}</StatusLabel>
      </div>
      {wg.analysevraag && <p className="line-clamp-2 text-xs text-ink">{wg.analysevraag}</p>}
      <p className="text-xs text-muted">
        {wg.aantal_bronnen === 1 ? "1 bron" : `${wg.aantal_bronnen ?? 0} bronnen`} · gewijzigd {datum(wg.gewijzigd)}
      </p>
      <KaartActies>
        <Link href={href} className={`focus-ring ${knopKlasse("secondary", "sm")}`}>Openen</Link>
        <VerwijderKnop soort="werkgebied" maat="sm" onBevestig={onVerwijder} />
      </KaartActies>
    </article>
  );
}
