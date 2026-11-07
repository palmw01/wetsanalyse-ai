"use client";

import { useEffect, useState } from "react";
import { Button } from "@/components/ui/Button";
import { Melding } from "@/components/ui/Melding";
import { SettingGroup, SettingList, SettingRow } from "@/components/ui/SettingRow";
import { SkeletonCard } from "@/components/ui/Skeleton";
import { foutTekst, getAccount, zetRondleiding } from "@/lib/api";
import { START_URL } from "@/lib/rondleiding";

/** De rondleiding door de werkplek: de knop op het startscherm aan of uit, en starten wanneer je wilt. De keuze staat
 *  bij de gebruiker in de api, dus ze gaat mee naar een andere computer. */
export function RondleidingPanel() {
  const [knop, setKnop] = useState<boolean | null>(null);
  const [fout, setFout] = useState<string | null>(null);

  useEffect(() => {
    let weg = false;
    getAccount()
      .then((a) => { if (!weg) setKnop(a.rondleiding_knop); })
      .catch((e) => { if (!weg) setFout(foutTekst(e)); });
    return () => { weg = true; };
  }, []);

  async function wissel(aan: boolean) {
    setFout(null);
    setKnop(aan);
    try {
      setKnop((await zetRondleiding({ knop: aan })).rondleiding_knop);
    } catch (e) {
      setKnop(!aan);
      setFout(foutTekst(e));
    }
  }

  return (
    <SettingGroup titel="Rondleiding" omschrijving="Een korte wandeling langs de werkplek, met een voorbeeld dat niets aan je werk verandert.">
      {fout && <Melding type="fout" className="mb-3">{fout}</Melding>}
      {knop === null && !fout ? <SkeletonCard /> : (
        <SettingList>
          {knop !== null && (
            <SettingRow
              label="Toon de knop op het startscherm"
              htmlFor="rondleiding-knop"
              omschrijving="Laat me de werkplek zien, in een leeg gesprek. Aan het eind van de rondleiding kun je hem ook uitzetten."
            >
              <input
                id="rondleiding-knop"
                type="checkbox"
                className="h-4 w-4 accent-lint"
                checked={knop}
                onChange={(e) => void wissel(e.target.checked)}
              />
            </SettingRow>
          )}
          <SettingRow label="Rondleiding starten" omschrijving="Opent de werkplek en begint de rondleiding.">
            {/* Een echte paginawissel: vanuit het venster blijft het `@modal`-slot bij een routerwissel staan. */}
            <Button size="sm" variant="secondary" onClick={() => window.location.assign(START_URL)}>
              Start de rondleiding
            </Button>
          </SettingRow>
        </SettingList>
      )}
    </SettingGroup>
  );
}
