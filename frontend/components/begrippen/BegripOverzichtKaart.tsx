"use client";

import Link from "next/link";

import { VerwijderKnop } from "@/components/ui/VerwijderKnop";
import { BEGRIP_STATUS_LABEL, kaartUrl, kort, type BegripOverzichtRij } from "@/lib/begrippenOverzicht";
import type { BegripStatus } from "@/lib/types";

const PIL: Record<BegripStatus, string> = {
  geaccordeerd: "border-lint/40 bg-lint/10 text-lint",
  concept: "border-line text-muted",
  vervangen: "border-line text-faint line-through",
};

/** Eén begrip in het overzicht, in de vorm van `AnnotatieKaart` en `WerkgebiedKaart`: de naam is de link
 *  naar de kaart in zijn werkgebied, onderaan *Openen* en *Verwijderen* (niet bij een vervangen begrip:
 *  verwijder dan de opvolger). */
export function BegripOverzichtKaart({ b, onVerwijder }: { b: BegripOverzichtRij; onVerwijder: () => Promise<void> }) {
  const href = kaartUrl(b.werkgebied_id, b.id);
  return (
    <article data-begrip-kaart={b.id}
      className="flex flex-col gap-2 rounded-button border border-line bg-paper p-4 transition-shadow hover:shadow-kaart">
      <div className="flex items-start justify-between gap-3">
        <h3 className="min-w-0 font-display text-sm font-semibold text-lint">
          <Link href={href} className="focus-ring rounded hover:underline">{b.naam}</Link>
        </h3>
        <span className={`inline-flex shrink-0 items-center rounded-full border px-2 py-0.5 text-[11px] font-medium ${PIL[b.status]}`}>
          {BEGRIP_STATUS_LABEL[b.status]}
        </span>
      </div>
      <p className="text-xs text-muted">
        {b.werkgebied_naam}
        {b.alternatieve_termen.length > 0 && ` · ook: ${b.alternatieve_termen.join(", ")}`}
      </p>
      {b.definitie ? (
        <p className="text-sm text-ink">{kort(b.definitie)}</p>
      ) : (
        <p className="text-sm italic text-faint">Nog geen definitie.</p>
      )}
      {b.vervangen_door && <p className="text-xs text-muted">Vervangen door {b.vervangen_door.naam}</p>}
      {!!b.herbeoordelen && (
        <p className="text-xs text-aandacht-geel-tekst" data-herbeoordelen>
          Herbeoordelen: {b.herbeoordelen === 1 ? "1 dragende passage veranderde" : `${b.herbeoordelen} dragende passages veranderden`} na het accorderen.
        </p>
      )}
      <div className="mt-auto flex flex-wrap items-center gap-2 pt-1">
        <Link href={href}
          className="focus-ring inline-flex min-h-[24px] items-center rounded-full border border-line px-2.5 py-0.5 text-[11px] font-medium text-lint transition-colors hover:bg-surface coarse:min-h-[44px]">
          Openen
        </Link>
        {b.status !== "vervangen" && <VerwijderKnop soort="begrip" onBevestig={onVerwijder} className="ml-auto" />}
      </div>
    </article>
  );
}
