"use client";

import { aantal } from "@/lib/aantal";
import { kort } from "@/lib/begrippenOverzicht";
import { StatusLabel } from "@/components/ui/Lijst";
import { OverzichtKaart } from "@/components/ui/Pagina";
import { VerwijderKnop } from "@/components/ui/VerwijderKnop";
import { REGEL_SOORT_LABEL, REGEL_STATUS_LABEL, REGEL_STATUS_TOON } from "@/lib/regels";
import type { RegelOverzichtRij } from "@/lib/regelsOverzicht";
import { regelPad } from "@/lib/werkgebiedPaden";

/** Eén afleidingsregel in het overzicht (`OverzichtKaart`, zoals een begrip): de naam is de link naar de regel in zijn
 *  werkgebied, eronder de regeltekst, onderaan *Openen* en *Verwijderen*. */
export function RegelOverzichtKaart({ r, onVerwijder }: { r: RegelOverzichtRij; onVerwijder: () => Promise<void> }) {
  return (
    <OverzichtKaart data-regel-kaart={r.id} titel={r.naam || r.uitvoer} href={regelPad(r.werkgebied_id, r.id)}
      status={<StatusLabel toon={REGEL_STATUS_TOON[r.status]}>{REGEL_STATUS_LABEL[r.status]}</StatusLabel>}
      sub={<>{r.werkgebied_naam} · {REGEL_SOORT_LABEL[r.soort]} · {aantal(r.gevallen, "geval", "gevallen")}
        {r.brontype === "beleid" && " · beleidsregel"}</>}
      verwijder={<VerwijderKnop soort="regel" maat="sm" onBevestig={onVerwijder} />}>
      <p className="text-sm text-ink">{kort(r.regeltekst)}</p>
    </OverzichtKaart>
  );
}
