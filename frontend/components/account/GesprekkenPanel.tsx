"use client";

import { useCallback, useEffect, useState } from "react";
import { Button } from "@/components/ui/Button";
import { Melding } from "@/components/ui/Melding";
import { SettingGroup, SettingList, SettingRow } from "@/components/ui/SettingRow";
import { SkeletonCard } from "@/components/ui/Skeleton";
import { VerwijderKnop } from "@/components/ui/VerwijderKnop";
import {
  archiveerGesprekkenGroep, foutTekst, gesprekkenTelling, verwijderGesprekkenGroep, type GesprekGroep,
} from "@/lib/api";
import { meldGesprekkenGewijzigd } from "@/lib/gesprekkenGewijzigd";
import { aantalGesprekken, bevestigVerwijderen, uitkomstZin } from "@/lib/gesprekkenOpruimen";
import { metSpoor } from "@/lib/uiSpoor";

/** Gesprekken in één keer opruimen: de recente (actief en los) of het archief (alles wat gearchiveerd is, ook uit een
 *  werkgebied). Alleen je eigen gesprekken; annotaties, begrippen en werkgebieden blijven staan. Verwijderen wist ook
 *  het geheugen van Lex en stopt een lopende beurt; archiveren is terug te halen en vraagt dus geen bevestiging. */
export function GesprekkenPanel() {
  const [telling, setTelling] = useState<Record<GesprekGroep, number> | null>(null);
  const [fout, setFout] = useState<string | null>(null);
  const [gedaan, setGedaan] = useState<string | null>(null);

  const laad = useCallback(async () => {
    try {
      setTelling(await gesprekkenTelling());
    } catch (e) {
      setFout(foutTekst(e, "Het aantal gesprekken is niet geladen."));
    }
  }, []);

  useEffect(() => {
    let weg = false;
    gesprekkenTelling()
      .then((t) => { if (!weg) setTelling(t); })
      .catch((e) => { if (!weg) setFout(foutTekst(e, "Het aantal gesprekken is niet geladen.")); });
    return () => { weg = true; };
  }, []);

  async function verwijder(groep: GesprekGroep) {
    setFout(null);
    setGedaan(null);
    try {
      const uit = await metSpoor("gesprekken_verwijderen", () => verwijderGesprekkenGroep(groep));
      meldGesprekkenGewijzigd({ soort: "verwijderd", ids: uit.ids });
      setGedaan(uitkomstZin("verwijderd", uit.aantal));
    } catch (e) {
      setFout(foutTekst(e, "De gesprekken zijn niet verwijderd."));
    }
    await laad();
  }

  async function archiveer() {
    setFout(null);
    setGedaan(null);
    try {
      const uit = await metSpoor("gesprekken_archiveren", () => archiveerGesprekkenGroep("recent"));
      meldGesprekkenGewijzigd({ soort: "gearchiveerd", ids: uit.ids });
      setGedaan(uitkomstZin("gearchiveerd", uit.aantal));
    } catch (e) {
      setFout(foutTekst(e, "De gesprekken zijn niet gearchiveerd."));
    }
    await laad();
  }

  return (
    <SettingGroup
      titel="Gesprekken opruimen"
      omschrijving="Verwijderen haalt de gesprekken en het geheugen van Lex erover weg; dat is niet terug te halen. Loopt er nog een beurt, dan stopt die. Annotaties, begrippen en werkgebieden blijven bestaan."
    >
      {fout && <Melding type="fout" className="mb-3">{fout}</Melding>}
      {gedaan && <Melding type="bevestiging" className="mb-3">{gedaan}</Melding>}
      {telling === null && !fout ? <SkeletonCard /> : telling && (
        <SettingList>
          <SettingRow
            label="Recente gesprekken"
            omschrijving={`${aantalGesprekken(telling.recent)} die niet in een werkgebied staan. Wil je ze alleen uit beeld hebben, archiveer ze dan.`}
          >
            <div className="flex flex-wrap gap-2" data-groep-opruimen="recent">
              <Button size="sm" variant="secondary" disabled={telling.recent === 0} onClick={() => void archiveer()}>
                Archiveren
              </Button>
              <VerwijderKnop
                soort="gesprekken"
                maat="sm"
                disabled={telling.recent === 0}
                bevestigTekst={bevestigVerwijderen(telling.recent)}
                onBevestig={() => verwijder("recent")}
              />
            </div>
          </SettingRow>
          <SettingRow
            label="Archief"
            omschrijving={`${aantalGesprekken(telling.archief)} in het archief, ook uit een werkgebied.`}
          >
            <div className="flex flex-wrap gap-2" data-groep-opruimen="archief">
              <VerwijderKnop
                soort="gesprekken"
                maat="sm"
                disabled={telling.archief === 0}
                bevestigTekst={bevestigVerwijderen(telling.archief)}
                onBevestig={() => verwijder("archief")}
              />
            </div>
          </SettingRow>
        </SettingList>
      )}
    </SettingGroup>
  );
}
