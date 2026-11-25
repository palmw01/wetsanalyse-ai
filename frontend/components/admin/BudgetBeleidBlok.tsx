"use client";

import { useCallback, useEffect, useState } from "react";
import { BewerkKnop, BewerkVoet } from "@/components/ui/Bewerkbaar";
import { Card } from "@/components/ui/Card";
import { Field, Input, Select } from "@/components/ui/Field";
import { Melding } from "@/components/ui/Melding";
import { FormRij } from "@/components/ui/SettingRow";
import { Skeleton } from "@/components/ui/Skeleton";
import { getBudgetBeleid, isApiError, proefBudgetBeleid, zetBudgetBeleid, zetRolBudget, type BudgetBeleidIn } from "@/lib/api";
import {
  ankerVoorDatum, ankerVoorWeekdag, bovenBudgetMelding, resetdatum, resetRitme, rolLabel, tokens, wandklok, WEEKDAGEN,
} from "@/lib/tokenbudget";
import type { BudgetBeleid, BudgetProef } from "@/lib/types";

/** Waar de keuze van het resetmoment op begint. Een geseed beleid heeft het moment van de eerste start als
 *  anker, en dat koos niemand: dan stellen we het begin van de werkweek voor. */
function beginKeuze(b: BudgetBeleid) {
  if (b.updated_by === "seed") return { weekdag: 0, tijd: "00:00", datum: wandklok(new Date(), b.tijdzone).datum };
  return wandklok(b.anker, b.tijdzone);
}

/** Het tokenbudget: hoeveel per rol, en wanneer het weer vol is.
 *
 *  Staat boven de gebruikerslijst omdat een budget een eigenschap is van *wie* er werkt — niet van
 *  het model. Het volgt alleen uit de rol: een budget per gebruiker bestaat niet.
 */
export function BudgetBeleidBlok({ onGewijzigd }: { onGewijzigd?: () => void }) {
  const [beleid, setBeleid] = useState<BudgetBeleid | null>(null);
  const [perRol, setPerRol] = useState<Record<string, string>>({});
  const [dagen, setDagen] = useState("");
  const [weekdag, setWeekdag] = useState(0);
  const [tijd, setTijd] = useState("00:00");
  const [datum, setDatum] = useState("");
  const [actief, setActief] = useState(true);
  const [proef, setProef] = useState<BudgetProef | null>(null);
  const [fout, setFout] = useState<string | null>(null);
  const [bezig, setBezig] = useState(false);
  const [bewaard, setBewaard] = useState(false);
  const [bewerken, setBewerken] = useState(false);

  const neemOver = useCallback((b: BudgetBeleid) => {
    setBeleid(b);
    setPerRol(Object.fromEntries(b.rollen.map((r) => [r.rol, String(r.tokens)])));
    setDagen(String(b.periode_dagen));
    setActief(b.actief);
    const keuze = beginKeuze(b);
    setWeekdag(keuze.weekdag);
    setTijd(keuze.tijd);
    setDatum(keuze.datum);
  }, []);

  const laad = useCallback(async () => {
    setFout(null);
    try {
      neemOver(await getBudgetBeleid());
    } catch (e) {
      setFout(isApiError(e) ? `${e.detail} (${e.status})` : (e as Error).message);
    }
  }, [neemOver]);

  useEffect(() => {
    // Data-load bij mount: setState gebeurt async ná de fetch.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    laad();
  }, [laad]);

  const periode = Math.max(1, Number(dagen) || 1);
  const perWeek = periode === 7;

  /** Wat er naar de api gaat. Het anker alleen als de keuze afwijkt van wat er staat: een ander anker
   *  verplaatst ieders venster, en dat hoort geen bijvangst te zijn van een nieuw rolbudget. */
  const verzoek = useCallback((): BudgetBeleidIn | null => {
    if (!beleid || !tijd) return null;
    const huidig = wandklok(beleid.anker, beleid.tijdzone);
    const basis = { periode_dagen: periode, actief };
    if (perWeek) {
      if (weekdag === huidig.weekdag && tijd === huidig.tijd) return basis;
      return { ...basis, anker: ankerVoorWeekdag(weekdag, tijd, beleid.tijdzone) };
    }
    if (!datum || (datum === huidig.datum && tijd === huidig.tijd)) return basis;
    return { ...basis, anker: ankerVoorDatum(datum, tijd) };
  }, [beleid, periode, perWeek, actief, weekdag, tijd, datum]);

  // Laat zien wat de keuze doet voordat hij wordt opgeslagen: het venster, en wie daarin boven zijn budget komt.
  useEffect(() => {
    if (!bewerken) return;
    const body = verzoek();
    if (!body) return;
    let weg = false;
    const t = setTimeout(() => {
      proefBudgetBeleid(body).then((p) => { if (!weg) setProef(p); }).catch(() => { if (!weg) setProef(null); });
    }, 250);
    return () => { weg = true; clearTimeout(t); };
  }, [bewerken, verzoek]);

  async function opslaan(e: React.FormEvent) {
    e.preventDefault();
    const body = verzoek();
    if (bezig || !beleid || !body) return;
    setBezig(true);
    setFout(null);
    setBewaard(false);
    try {
      await zetBudgetBeleid(body);
      // Alleen wat veranderde: elke wijziging is een regel in de audit.
      for (const r of beleid.rollen) {
        const nieuw = Number(perRol[r.rol]);
        if (nieuw !== r.tokens) await zetRolBudget(r.rol, nieuw);
      }
      neemOver(await getBudgetBeleid());
      setBewaard(true);
      setBewerken(false);
      setProef(null);
      onGewijzigd?.();
    } catch (e) {
      setFout(isApiError(e) ? `${e.detail} (${e.status})` : (e as Error).message);
    } finally {
      setBezig(false);
    }
  }

  if (beleid && !bewerken) {
    const ritme = resetRitme(beleid.periode_dagen, beleid.anker, beleid.tijdzone);
    return (
      <Card className="mb-4 p-3" data-budget-beleid>
        <div className="flex items-start justify-between gap-3">
          <div className="min-w-0">
            <h4 className="font-display text-sm font-semibold text-ink">Tokenbudget</h4>
            <p className="mt-0.5 text-sm text-muted">
              {beleid.actief
                ? `Per ${beleid.periode_dagen === 1 ? "dag" : `${beleid.periode_dagen} dagen`}, per rol${ritme ? `, ${ritme}` : ""}. Reset op ${resetdatum(beleid.reset_op, beleid.tijdzone)}.`
                : "De begrenzing staat uit; verbruik wordt wel gemeten."}
            </p>
            <ul className="mt-1 text-sm text-ink">
              {beleid.rollen.map((r) => (
                <li key={r.rol} data-rol-budget={r.rol}>{rolLabel(r.rol)}: {tokens(r.tokens)} tokens</li>
              ))}
            </ul>
            {bewaard && <p className="mt-1 text-xs text-succes" role="status">Opgeslagen.</p>}
          </div>
          <BewerkKnop wat="Tokenbudget" onClick={() => { setBewaard(false); setBewerken(true); }} />
        </div>
      </Card>
    );
  }

  const vandaag = beleid ? wandklok(new Date(), beleid.tijdzone).datum : undefined;

  return (
    <Card className="mb-4 p-3" data-budget-beleid>
      <h4 className="font-display text-sm font-semibold text-ink">Tokenbudget</h4>
      <p className="mt-0.5 text-sm text-muted">
        Iedereen krijgt het budget van zijn rol. Elke vraag en elke annotatieronde van Lex telt mee, inclusief de
        wettekst die Lex erbij haalt.
      </p>

      {fout && <Melding type="fout" className="mt-3">{fout}</Melding>}

      {!beleid ? !fout && <Skeleton className="mt-3 h-10 w-full" /> : (
        <form onSubmit={opslaan} className="mt-3 space-y-3">
          <FormRij>
            {beleid.rollen.map((r) => (
              <Field key={r.rol} label={`${rolLabel(r.rol)}: tokens per periode`}>
                <Input type="number" min={1} step={1} required value={perRol[r.rol] ?? ""}
                  onChange={(e) => setPerRol((oud) => ({ ...oud, [r.rol]: e.target.value }))} />
              </Field>
            ))}
            <Field label="Reset na (dagen)">
              <Input type="number" min={1} max={365} required value={dagen} onChange={(e) => setDagen(e.target.value)} />
            </Field>
          </FormRij>
          <FormRij>
            {perWeek ? (
              <Field label="Reset op">
                <Select value={weekdag} onChange={(e) => setWeekdag(Number(e.target.value))}>
                  {WEEKDAGEN.map((d, i) => <option key={d} value={i}>{d.charAt(0).toUpperCase() + d.slice(1)}</option>)}
                </Select>
              </Field>
            ) : (
              <Field label="Eerste reset op" hint="vandaag of eerder">
                <Input type="date" required max={vandaag} value={datum} onChange={(e) => setDatum(e.target.value)} />
              </Field>
            )}
            <Field label="Om" hint="Nederlandse tijd">
              <Input type="time" required step={60} value={tijd} onChange={(e) => setTijd(e.target.value)} />
            </Field>
          </FormRij>
          {proef && (
            <p className="text-sm text-muted" data-budget-proef>
              Het venster loopt dan van {resetdatum(proef.venster_start, beleid.tijdzone)} tot{" "}
              {resetdatum(proef.reset_op, beleid.tijdzone)}.
            </p>
          )}
          {proef && proef.boven_budget.length > 0 && (
            <Melding type="waarschuwing" compact data-budget-boven="">
              {bovenBudgetMelding(proef.boven_budget)} Na opslaan geef je iemand zijn budget terug met{" "}
              <em>Verbruik resetten</em> in het menu bij die gebruiker.
            </Melding>
          )}
          <label className="flex items-start gap-2 text-sm text-ink">
            <input type="checkbox" className="mt-0.5 h-4 w-4 accent-lint" checked={actief} onChange={(e) => setActief(e.target.checked)} />
            <span>
              Begrenzing actief
              <span className="block text-xs text-muted">Uit: verbruik wordt nog steeds gemeten, maar niemand wordt tegengehouden.</span>
            </span>
          </label>
          <BewerkVoet submit bezig={bezig} gewijzigd opslaanTekst="Opslaan"
            onAnnuleer={() => { setBewerken(false); setProef(null); void laad(); }} />
        </form>
      )}
    </Card>
  );
}
