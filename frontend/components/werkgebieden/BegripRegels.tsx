"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { Regel as RegelVeld, Regels, StatusLabel } from "@/components/ui/Lijst";
import { Kaart } from "@/components/ui/Pagina";
import { lijstRegels } from "@/lib/api";
import { REGEL_STATUS_LABEL, REGEL_STATUS_TOON, regelsBijBegrip, type Regel } from "@/lib/regels";
import { regelPad } from "@/lib/werkgebiedPaden";

/** Op de begripskaart (ADR-018, U4): de regels die dit begrip afleiden en de regels die het gebruiken. Faalt stil, en
 *  staat er niet zolang geen regel het begrip noemt. */
export function BegripRegels({ werkgebiedId, begripId, revisie }: { werkgebiedId: string; begripId: string; revisie: number }) {
  const [regels, setRegels] = useState<Regel[] | null>(null);
  useEffect(() => {
    let levend = true;
    lijstRegels(werkgebiedId).then((r) => levend && setRegels(r)).catch(() => levend && setRegels(null));
    return () => { levend = false; };
  }, [werkgebiedId, begripId, revisie]);
  if (!regels) return null;
  const { afgeleidDoor, gebruiktIn } = regelsBijBegrip(regels, begripId);
  if (!afgeleidDoor.length && !gebruiktIn.length) return null;
  const rij = (lijst: Regel[]) => lijst.length ? (
    <ul className="space-y-1">
      {lijst.map((r) => (
        <li key={r.id} className="flex items-start justify-between gap-2">
          <Link href={regelPad(werkgebiedId, r.id)} className="focus-ring rounded text-sm text-lint hover:underline">{r.naam || r.uitvoer}</Link>
          <StatusLabel klein toon={REGEL_STATUS_TOON[r.status]}>{REGEL_STATUS_LABEL[r.status]}</StatusLabel>
        </li>
      ))}
    </ul>
  ) : <span className="text-sm text-muted">Geen</span>;
  return (
    <Kaart titel="Afleidingsregels" data-begrip-regels>
      <Regels>
        <RegelVeld naam="Afgeleid door">{rij(afgeleidDoor)}</RegelVeld>
        <RegelVeld naam="Gebruikt in">{rij(gebruiktIn)}</RegelVeld>
      </Regels>
    </Kaart>
  );
}
