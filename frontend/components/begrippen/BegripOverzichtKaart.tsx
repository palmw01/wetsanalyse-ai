"use client";

import Link from "next/link";

import { knopKlasse } from "@/components/ui/Button";
import { VerwijderKnop } from "@/components/ui/VerwijderKnop";
import { BEGRIP_STATUS_LABEL, kaartUrl, kort, type BegripOverzichtRij } from "@/lib/begrippenOverzicht";
import type { BegripStatus } from "@/lib/types";
import { StatusLabel } from "@/components/ui/Lijst";

// Geaccordeerd is het enige oordeel; zoals elders groen (de status van een begrip in `BegripInhoud`).
const TOON: Record<BegripStatus, "groen" | "neutraal"> = { geaccordeerd: "groen", concept: "neutraal", vervangen: "neutraal" };

/** Eén begrip in het overzicht, in de vorm van `AnnotatieKaart` en `WerkgebiedKaart`: de naam is de link
 *  naar het begrip in zijn werkgebied, onderaan *Openen* en *Verwijderen* (niet bij een vervangen begrip:
 *  verwijder dan de opvolger). */
export function BegripOverzichtKaart({ b, onVerwijder }: { b: BegripOverzichtRij; onVerwijder: () => Promise<void> }) {
  const href = kaartUrl(b.werkgebied_id, b.id);
  return (
    <article data-begrip-kaart={b.id}
      className="flex min-w-0 flex-col gap-2 rounded-kaart border border-line bg-paper p-4 shadow-zacht transition hover:-translate-y-0.5 hover:border-lint/40 hover:shadow-kaart motion-reduce:hover:translate-y-0">
      <div className="flex items-start justify-between gap-3">
        <h3 className="min-w-0 font-display text-sm font-semibold text-lint">
          <Link href={href} className="focus-ring rounded hover:underline">{b.naam}</Link>
        </h3>
        <StatusLabel toon={TOON[b.status]} className={b.status === "vervangen" ? "line-through" : ""}>
          {BEGRIP_STATUS_LABEL[b.status]}
        </StatusLabel>
      </div>
      <p className="text-xs text-muted">
        {b.kader === "generiek"
          ? `Generiek · gebruikt in ${b.gebruikt_in === 1 ? "1 werkgebied" : `${b.gebruikt_in ?? 0} werkgebieden`}`
          : b.werkgebied_naam}
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
        <Link href={href} className={`focus-ring ${knopKlasse("secondary", "xs")}`}>Openen</Link>
        {b.status !== "vervangen" && <VerwijderKnop soort="begrip" onBevestig={onVerwijder} className="ml-auto" />}
      </div>
    </article>
  );
}
