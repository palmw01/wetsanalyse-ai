"use client";

import { datumKort } from "@/lib/datum";
import { OverzichtKaart } from "@/components/ui/Pagina";
import { VerwijderKnop } from "@/components/ui/VerwijderKnop";
import type { WerkgebiedSamenvatting } from "@/lib/types";
import { STATUS_LABEL } from "@/lib/werkgebied";
import { StatusLabel } from "@/components/ui/Lijst";

const datum = datumKort;

/** Eén werkgebied in het overzicht (`OverzichtKaart`): de naam is de link, onderaan *Openen* en *Verwijderen*. */
export function WerkgebiedKaart({ wg, onVerwijder }: { wg: WerkgebiedSamenvatting; onVerwijder: () => Promise<void> }) {
  return (
    <OverzichtKaart data-werkgebied-kaart={wg.id} titel={wg.naam} href={`/werkgebieden/${encodeURIComponent(wg.id)}`}
      status={<StatusLabel>{STATUS_LABEL[wg.status]}</StatusLabel>}
      verwijder={<VerwijderKnop soort="werkgebied" maat="sm" onBevestig={onVerwijder} />}>
      {wg.analysevraag && <p className="line-clamp-2 text-xs text-ink">{wg.analysevraag}</p>}
      <p className="text-xs text-muted">
        {wg.aantal_bronnen === 1 ? "1 bron" : `${wg.aantal_bronnen ?? 0} bronnen`} · gewijzigd {datum(wg.gewijzigd)}
      </p>
    </OverzichtKaart>
  );
}
