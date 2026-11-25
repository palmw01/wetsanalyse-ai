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
  ankerVoorDag, ankerVoorDatum, ankerVoorMaanddag, ankerVoorWeekdag, bovenBudgetMelding, periodeLabel, periodeSoort,
  resetdatum, rolLabel, tokens, wandklok, WEEKDAGEN, type PeriodeSoort,
} from "@/lib/tokenbudget";
import type { BudgetBeleid, BudgetProef } from "@/lib/types";

/** De keuze in het bewerkscherm: hoe vaak, en op welk moment. */
interface Keuze {
  soort: PeriodeSoort;
  weekdag: number;
  dag: number;
  tijd: string;
  datum: string;
  dagen: string;
}

/** De keuze zoals het beleid nu staat. Een geseed beleid koos niemand: dan stellen we het begin van de werkweek voor. */
function huidigeKeuze(b: BudgetBeleid): Keuze {
  if (b.updated_by === "seed") return standaardKeuze("week", b);
  const w = wandklok(b.anker, b.tijdzone);
  return { soort: periodeSoort(b), weekdag: w.weekdag, dag: Math.min(w.dag, 28), tijd: w.tijd, datum: w.datum,
    dagen: String(b.periode_dagen) };
}

/** Wat een nieuw gekozen periode voorstelt: per week maandag 00:00, per maand de 1e om 00:00, per dag 00:00. */
function standaardKeuze(soort: PeriodeSoort, b: BudgetBeleid): Keuze {
  return { soort, weekdag: 0, dag: 1, tijd: "00:00", datum: wandklok(new Date(), b.tijdzone).datum,
    dagen: String(b.periode_dagen) };
}

const SOORTEN: { soort: PeriodeSoort; label: string }[] = [
  { soort: "dag", label: "Per dag" },
  { soort: "week", label: "Per week" },
  { soort: "maand", label: "Per maand" },
];

/** Het tokenbudget: hoeveel per rol, en wanneer het weer vol is.
 *
 *  Staat boven de gebruikerslijst omdat een budget een eigenschap is van *wie* er werkt — niet van
 *  het model. Het volgt alleen uit de rol: een budget per gebruiker bestaat niet.
 */
export function BudgetBeleidBlok({ onGewijzigd }: { onGewijzigd?: () => void }) {
  const [beleid, setBeleid] = useState<BudgetBeleid | null>(null);
  const [perRol, setPerRol] = useState<Record<string, string>>({});
  const [keuze, setKeuze] = useState<Keuze | null>(null);
  const [actief, setActief] = useState(true);
  const [proef, setProef] = useState<BudgetProef | null>(null);
  const [fout, setFout] = useState<string | null>(null);
  const [bezig, setBezig] = useState(false);
  const [bewaard, setBewaard] = useState(false);
  const [bewerken, setBewerken] = useState(false);

  const neemOver = useCallback((b: BudgetBeleid) => {
    setBeleid(b);
    setPerRol(Object.fromEntries(b.rollen.map((r) => [r.rol, String(r.tokens)])));
    setActief(b.actief);
    setKeuze(huidigeKeuze(b));
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

  const zet = (deel: Partial<Keuze>) => setKeuze((oud) => (oud ? { ...oud, ...deel } : oud));

  /** Een andere periode kiezen: terug naar de huidige brengt de huidige waarden terug, een nieuwe begint op zijn
   *  standaard. */
  function kiesSoort(soort: PeriodeSoort) {
    if (!beleid) return;
    const huidig = huidigeKeuze(beleid);
    setKeuze(soort === huidig.soort ? huidig : standaardKeuze(soort, beleid));
  }

  /** Wat er naar de api gaat. Het anker alleen als het moment afwijkt van wat er staat: een ander anker verplaatst
   *  ieders venster, en dat hoort geen bijvangst te zijn van een nieuw rolbudget. */
  const verzoek = useCallback((): BudgetBeleidIn | null => {
    if (!beleid || !keuze || !keuze.tijd) return null;
    const { soort, weekdag, dag, tijd, datum } = keuze;
    const tz = beleid.tijdzone;
    const nu = wandklok(beleid.anker, tz);
    const zelfdePeriode = soort === periodeSoort(beleid) && beleid.updated_by !== "seed";
    switch (soort) {
      case "dag": {
        const basis = { periode_dagen: 1, periode_maanden: 0, actief };
        return zelfdePeriode && tijd === nu.tijd ? basis : { ...basis, anker: ankerVoorDag(tijd, tz) };
      }
      case "week": {
        const basis = { periode_dagen: 7, periode_maanden: 0, actief };
        return zelfdePeriode && weekdag === nu.weekdag && tijd === nu.tijd
          ? basis : { ...basis, anker: ankerVoorWeekdag(weekdag, tijd, tz) };
      }
      case "maand": {
        // `periode_dagen` telt niet bij een periode in maanden; 30 is wat een oudere lezer ervan zou verwachten.
        const basis = { periode_dagen: 30, periode_maanden: 1, actief };
        return zelfdePeriode && dag === nu.dag && tijd === nu.tijd
          ? basis : { ...basis, anker: ankerVoorMaanddag(dag, tijd, tz) };
      }
      default: {
        const basis = { periode_dagen: Math.max(1, Number(keuze.dagen) || 1), periode_maanden: 0, actief };
        if (!datum || (datum === nu.datum && tijd === nu.tijd)) return basis;
        return { ...basis, anker: ankerVoorDatum(datum, tijd) };
      }
    }
  }, [beleid, keuze, actief]);

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
    return (
      <Card className="mb-4 p-3" data-budget-beleid>
        <div className="flex items-start justify-between gap-3">
          <div className="min-w-0">
            <h4 className="font-display text-sm font-semibold text-ink">Tokenbudget</h4>
            <p className="mt-0.5 text-sm text-muted">
              {beleid.actief
                ? `${periodeLabel(beleid)}, reset op ${resetdatum(beleid.reset_op, beleid.tijdzone)}.`
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
          </FormRij>
          {keuze && (
            <FormRij>
              <Field label="Periode">
                <Select value={keuze.soort} onChange={(e) => kiesSoort(e.target.value as PeriodeSoort)}>
                  {SOORTEN.map((o) => <option key={o.soort} value={o.soort}>{o.label}</option>)}
                  {periodeSoort(beleid) === "dagen" && <option value="dagen">{periodeLabel(beleid)}</option>}
                </Select>
              </Field>
              {keuze.soort === "week" && (
                <Field label="Reset op">
                  <Select value={keuze.weekdag} onChange={(e) => zet({ weekdag: Number(e.target.value) })}>
                    {WEEKDAGEN.map((d, i) => <option key={d} value={i}>{d.charAt(0).toUpperCase() + d.slice(1)}</option>)}
                  </Select>
                </Field>
              )}
              {keuze.soort === "maand" && (
                <Field label="Reset op dag" hint="1–28: elke maand heeft die dag">
                  <Select value={keuze.dag} onChange={(e) => zet({ dag: Number(e.target.value) })}>
                    {Array.from({ length: 28 }, (_, i) => i + 1).map((d) => <option key={d} value={d}>{`${d}e van de maand`}</option>)}
                  </Select>
                </Field>
              )}
              {keuze.soort === "dagen" && (
                <>
                  <Field label="Om de (dagen)">
                    <Input type="number" min={1} max={365} required value={keuze.dagen} onChange={(e) => zet({ dagen: e.target.value })} />
                  </Field>
                  <Field label="Eerste reset op" hint="vandaag of eerder">
                    <Input type="date" required max={vandaag} value={keuze.datum} onChange={(e) => zet({ datum: e.target.value })} />
                  </Field>
                </>
              )}
              <Field label="Om" hint="Nederlandse tijd">
                <Input type="time" required step={60} value={keuze.tijd} onChange={(e) => zet({ tijd: e.target.value })} />
              </Field>
            </FormRij>
          )}
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
