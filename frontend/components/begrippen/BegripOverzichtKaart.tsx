"use client";

import { aantal } from "@/lib/aantal";
import { Leeg } from "@/components/ui/Leeg";
import { OverzichtKaart } from "@/components/ui/Pagina";
import { VerwijderKnop } from "@/components/ui/VerwijderKnop";
import { BEGRIP_STATUS_LABEL, kaartUrl, kort, type BegripOverzichtRij } from "@/lib/begrippenOverzicht";
import type { BegripStatus } from "@/lib/types";
import { StatusLabel } from "@/components/ui/Lijst";

// Geaccordeerd is het enige oordeel; zoals elders groen (de status van een begrip in `BegripInhoud`).
const TOON: Record<BegripStatus, "groen" | "neutraal"> = { geaccordeerd: "groen", concept: "neutraal", vervangen: "neutraal" };

/** Eén begrip in het overzicht (`OverzichtKaart`): de naam is de link naar het begrip in zijn werkgebied, onderaan
 *  *Openen* en *Verwijderen* (niet bij een vervangen begrip: verwijder dan de opvolger). */
export function BegripOverzichtKaart({ b, onVerwijder }: { b: BegripOverzichtRij; onVerwijder: () => Promise<void> }) {
  return (
    <OverzichtKaart data-begrip-kaart={b.id} titel={b.naam} href={kaartUrl(b.werkgebied_id, b.id)}
      status={<StatusLabel toon={TOON[b.status]} className={b.status === "vervangen" ? "line-through" : ""}>
        {BEGRIP_STATUS_LABEL[b.status]}
      </StatusLabel>}
      sub={<>
        {b.kader === "generiek"
          ? `Generiek · gebruikt in ${aantal(b.gebruikt_in ?? 0, "werkgebied", "werkgebieden")}`
          : b.werkgebied_naam}
        {b.alternatieve_termen.length > 0 && ` · ook: ${b.alternatieve_termen.join(", ")}`}
      </>}
      verwijder={b.status !== "vervangen" && <VerwijderKnop soort="begrip" maat="sm" onBevestig={onVerwijder} />}>
      {b.definitie ? <p className="text-sm text-ink">{kort(b.definitie)}</p> : <Leeg>Nog geen definitie.</Leeg>}
      {b.vervangen_door && <p className="text-xs text-muted">Vervangen door {b.vervangen_door.naam}</p>}
      {!!b.herbeoordelen && (
        <p className="text-xs text-aandacht-geel-tekst" data-herbeoordelen>
          Herbeoordelen: {aantal(b.herbeoordelen, "dragende passage veranderde", "dragende passages veranderden")} na het accorderen.
        </p>
      )}
    </OverzichtKaart>
  );
}
