"use client";

import { useCallback, useEffect, useState } from "react";
import { Select } from "@/components/ui/Field";
import { BlokKop } from "@/components/ui/Lijst";
import { Melding } from "@/components/ui/Melding";
import { SettingGroup, SettingList, SettingRow } from "@/components/ui/SettingRow";
import { SkeletonCard } from "@/components/ui/Skeleton";
import { isApiError, listModelrollen, zetModelrol } from "@/lib/api";
import { datumTijd } from "@/lib/datum";
import { groepeerModelrollen, keuzesVoorRol, STANDAARD_WAARDE } from "@/lib/modelrollen";
import type { ModelrollenOverzicht } from "@/lib/types";

/** Welk modelprofiel Lex per rol gebruikt (api `/v1/admin/modelrollen`, graph-qa `agent/modelkeuze.py`).
 *
 *  Zonder keuze volgt een rol het standaardprofiel, en dan verandert er niets. Lex neemt van een profiel alleen de
 *  modelnaam over; een profiel dat hij niet kan gebruiken (ander endpoint, geen Claude-model) staat uitgeschakeld in de
 *  lijst, met de reden. Een keuze draagt een naam in de audit, dus de api wil een beheerder mét 2FA. `versie` laadt
 *  opnieuw als de profielen hierboven veranderen. */
export function ModelrollenBlok({ versie = 0 }: { versie?: number }) {
  const [stand, setStand] = useState<ModelrollenOverzicht | null>(null);
  const [fout, setFout] = useState<string | null>(null);
  const [bezig, setBezig] = useState<string | null>(null);

  const laad = useCallback(async () => {
    setFout(null);
    try {
      setStand(await listModelrollen());
    } catch (e) {
      setFout(isApiError(e) ? e.detail : (e as Error).message);
    }
  }, []);

  useEffect(() => {
    // Data-load bij mount en na een wijziging van de profielen: setState gebeurt async ná de fetch.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    laad();
  }, [laad, versie]);

  async function kies(rol: string, waarde: string) {
    setBezig(rol);
    setFout(null);
    try {
      await zetModelrol(rol, waarde === STANDAARD_WAARDE ? null : waarde);
      await laad();
    } catch (e) {
      setFout(isApiError(e) ? e.detail : (e as Error).message);
    } finally {
      setBezig(null);
    }
  }

  return (
    <SettingGroup titel="Model per rol"
      omschrijving="Welk profiel Lex voor elk soort werk gebruikt. Zonder keuze volgt een rol het standaardprofiel. Lex neemt van een profiel alleen de modelnaam over.">
      {fout && <Melding type="fout" className="mb-3">{fout}</Melding>}
      {stand === null ? (
        fout ? null : <SkeletonCard regels={3} />
      ) : (
        <div className="space-y-5">
          {stand.standaard_niet_bruikbaar && (
            <Melding type="waarschuwing" compact>
              Lex kan het standaardprofiel niet gebruiken: {stand.standaard_niet_bruikbaar} Rollen zonder keuze houden het
              model van de omgeving.
            </Melding>
          )}
          {groepeerModelrollen(stand.rollen).map(([groep, rollen]) => (
            <div key={groep} data-modelrol-groep={groep}>
              <BlokKop titel={groep} niveau={4} />
              <SettingList>
                {rollen.map((r) => {
                  const id = `modelrol-${r.naam}`;
                  return (
                    <div key={r.naam} data-modelrol={r.naam}>
                      <SettingRow label={r.label} htmlFor={id} veld
                        omschrijving={
                          <>
                            {r.beschrijving}
                            {r.model && <> Nu: <span className="font-mono text-xs">{r.model}</span>.</>}
                            {r.door && <> Gekozen door {r.door}{r.bijgewerkt ? `, ${datumTijd(r.bijgewerkt)}` : ""}.</>}
                          </>
                        }>
                        <Select id={id} value={r.profiel ?? STANDAARD_WAARDE} disabled={bezig === r.naam}
                          aria-busy={bezig === r.naam} onChange={(e) => kies(r.naam, e.target.value)}>
                          {keuzesVoorRol(stand, r).map((k) => (
                            <option key={k.waarde} value={k.waarde} disabled={k.uit}>{k.label}</option>
                          ))}
                        </Select>
                      </SettingRow>
                      {r.niet_bruikbaar && (
                        <Melding type="waarschuwing" compact className="mb-3">
                          Het gekozen profiel {r.profiel} is niet bruikbaar: {r.niet_bruikbaar} Deze rol volgt nu de standaard.
                        </Melding>
                      )}
                      {r.profiel && !r.niet_bruikbaar && r.waarschuwing && (
                        <Melding type="waarschuwing" compact className="mb-3">
                          {r.waarschuwing}
                        </Melding>
                      )}
                    </div>
                  );
                })}
              </SettingList>
            </div>
          ))}
        </div>
      )}
    </SettingGroup>
  );
}
