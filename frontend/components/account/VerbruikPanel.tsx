"use client";

import { useCallback, useEffect, useState } from "react";
import { Melding } from "@/components/ui/Melding";
import { Meter } from "@/components/ui/Meter";
import { SettingGroup } from "@/components/ui/SettingRow";
import { getVerbruik, isApiError } from "@/lib/api";
import { resetdatum, tokens } from "@/lib/tokenbudget";
import type { Verbruiksstand } from "@/lib/types";

/** "Mijn verbruik": waar sta ik, en wanneer is het budget weer vol.
 *
 *  De opzet volgt Claude's Settings → Usage: het percentage met een balk is het hoofdgetal, de
 *  resetdatum staat er pal naast. Het absolute tokenaantal staat eronder als detail — het zegt de
 *  gebruiker minder dan "62%", maar wie het wil narekenen moet het kunnen zien.
 */
export function VerbruikPanel() {
  const [stand, setStand] = useState<Verbruiksstand | null>(null);
  const [fout, setFout] = useState<string | null>(null);

  const laad = useCallback(async () => {
    setFout(null);
    try {
      setStand(await getVerbruik());
    } catch (e) {
      setFout(isApiError(e) ? `${e.detail} (${e.status})` : (e as Error).message);
    }
  }, []);

  useEffect(() => {
    // Data-load bij mount: setState gebeurt async ná de fetch (geen synchrone render-cascade).
    // eslint-disable-next-line react-hooks/set-state-in-effect
    laad();
  }, [laad]);

  return (
    <SettingGroup
      titel="Verbruik"
      omschrijving="Hoeveel tokens je deze periode hebt gebruikt. Elke vraag en elke annotatieronde van Lex telt mee."
    >
      {fout && (
        <Melding type="fout" className="mb-3">
          {fout}
        </Melding>
      )}

      {stand === null ? (
        <p className="text-sm text-muted">Laden…</p>
      ) : !stand.actief ? (
        <>
          <Melding type="uitleg" className="mb-3">
            Er geldt op dit moment geen tokenlimiet. Je verbruik wordt wel bijgehouden.
          </Melding>
          <p className="text-sm text-muted">
            Deze periode gebruikt: <span className="font-medium text-ink">{tokens(stand.gebruikt)}</span> tokens.
          </p>
        </>
      ) : (
        <>
          {stand.geblokkeerd && (
            <Melding type="fout" titel="Je tokenbudget is op" className="mb-3">
              Je kunt geen nieuwe vragen of annotatierondes meer starten. Je budget is weer vol op{" "}
              <span className="font-medium">{resetdatum(stand.reset_op)}</span>. Bestaande gesprekken
              en annotaties blijven gewoon leesbaar; heb je eerder ruimte nodig, vraag een beheerder
              om je budget te verhogen.
            </Melding>
          )}
          {!stand.geblokkeerd && stand.waarschuwing && (
            <Melding type="waarschuwing" titel={`${stand.percentage}% van je tokenbudget gebruikt`} className="mb-3">
              Je hebt nog {tokens(stand.resterend)} tokens tot{" "}
              <span className="font-medium">{resetdatum(stand.reset_op)}</span>.
            </Melding>
          )}

          <div className="flex items-baseline justify-between gap-3">
            <span className="font-display text-2xl font-semibold text-ink">{stand.percentage}%</span>
            <span className="text-sm text-muted">
              Reset op <span className="text-ink">{resetdatum(stand.reset_op)}</span>
            </span>
          </div>
          <Meter
            percentage={stand.percentage}
            label="Tokenverbruik deze periode"
            toon="verbruik"
            className="mt-2"
          />
          <p className="mt-2 text-sm text-muted">
            {tokens(stand.gebruikt)} van {tokens(stand.budget)} tokens gebruikt
            {stand.eigen_budget && " (persoonlijk budget)"}.
          </p>
        </>
      )}

      <p className="mt-4 text-xs text-muted">
        Een token is ongeveer een half woord. Zowel je vraag als het antwoord telt mee, plus de
        wettekst die Lex erbij haalt — een annotatieronde kost daarom meer dan een korte vraag.
      </p>
    </SettingGroup>
  );
}
