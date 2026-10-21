"use client";

import Link from "next/link";

import { VerwijderKnop } from "@/components/ui/VerwijderKnop";
import type { WerkgebiedSamenvatting } from "@/lib/types";
import { STATUS_LABEL } from "@/lib/werkgebied";

const datum = (iso: string) =>
  new Date(iso).toLocaleDateString("nl-NL", { day: "numeric", month: "short", year: "numeric" });

/** Eén werkgebied in het overzicht, in de vorm van `AnnotatieKaart`: de naam is de link (de hele kaart
 *  aanklikbaar maken zou de knoppen onbereikbaar maken voor het toetsenbord), onderaan *Openen* en
 *  *Verwijderen*. */
export function WerkgebiedKaart({ wg, onVerwijder }: { wg: WerkgebiedSamenvatting; onVerwijder: () => Promise<void> }) {
  const href = `/werkgebieden/${encodeURIComponent(wg.id)}`;
  return (
    <article data-werkgebied-kaart={wg.id}
      className="flex min-w-0 flex-col gap-3 rounded-button border border-line bg-paper p-4 transition-shadow hover:shadow-kaart">
      <div className="flex items-start justify-between gap-3">
        <h3 className="min-w-0 truncate font-display text-sm font-semibold text-lint">
          <Link href={href} className="focus-ring rounded hover:underline">{wg.naam}</Link>
        </h3>
        <span className="inline-flex shrink-0 items-center rounded-full border border-line px-2 py-0.5 text-[11px] font-medium text-muted">
          {STATUS_LABEL[wg.status]}
        </span>
      </div>
      {wg.analysevraag && <p className="line-clamp-2 text-xs text-ink">{wg.analysevraag}</p>}
      <p className="text-xs text-muted">
        {wg.aantal_bronnen === 1 ? "1 bron" : `${wg.aantal_bronnen ?? 0} bronnen`} · gewijzigd {datum(wg.gewijzigd)}
      </p>
      <div className="flex flex-wrap items-center gap-2">
        <Link href={href}
          className="focus-ring inline-flex min-h-[24px] items-center rounded-full border border-line px-2.5 py-0.5 text-[11px] font-medium text-lint transition-colors hover:bg-surface coarse:min-h-[44px]">
          Openen
        </Link>
        <VerwijderKnop soort="werkgebied" onBevestig={onVerwijder} className="ml-auto" />
      </div>
    </article>
  );
}
