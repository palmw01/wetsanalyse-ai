"use client";

import { useCallback, useEffect, useState } from "react";
import { BewerkKnop, BewerkVoet } from "@/components/ui/Bewerkbaar";
import { Card } from "@/components/ui/Card";
import { Field, Input } from "@/components/ui/Field";
import { Melding } from "@/components/ui/Melding";
import { Skeleton } from "@/components/ui/Skeleton";
import { getBudgetBeleid, isApiError, zetBudgetBeleid, zetRolBudget } from "@/lib/api";
import { resetdatum, rolLabel, tokens } from "@/lib/tokenbudget";
import type { BudgetBeleid } from "@/lib/types";

/** Het tokenbudget: hoeveel per rol, en om de hoeveel dagen het weer vol is.
 *
 *  Staat boven de gebruikerslijst omdat een budget een eigenschap is van *wie* er werkt — niet van
 *  het model. Het volgt alleen uit de rol: een budget per gebruiker bestaat niet.
 */
export function BudgetBeleidBlok({ onGewijzigd }: { onGewijzigd?: () => void }) {
  const [beleid, setBeleid] = useState<BudgetBeleid | null>(null);
  const [perRol, setPerRol] = useState<Record<string, string>>({});
  const [dagen, setDagen] = useState("");
  const [actief, setActief] = useState(true);
  const [fout, setFout] = useState<string | null>(null);
  const [bezig, setBezig] = useState(false);
  const [bewaard, setBewaard] = useState(false);
  const [bewerken, setBewerken] = useState(false);

  const neemOver = useCallback((b: BudgetBeleid) => {
    setBeleid(b);
    setPerRol(Object.fromEntries(b.rollen.map((r) => [r.rol, String(r.tokens)])));
    setDagen(String(b.periode_dagen));
    setActief(b.actief);
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

  async function opslaan(e: React.FormEvent) {
    e.preventDefault();
    if (bezig || !beleid) return;
    setBezig(true);
    setFout(null);
    setBewaard(false);
    try {
      await zetBudgetBeleid({ periode_dagen: Number(dagen) || 1, actief });
      // Alleen wat veranderde: elke wijziging is een regel in de audit.
      for (const r of beleid.rollen) {
        const nieuw = Number(perRol[r.rol]);
        if (nieuw !== r.tokens) await zetRolBudget(r.rol, nieuw);
      }
      neemOver(await getBudgetBeleid());
      setBewaard(true);
      setBewerken(false);
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
                ? `Per ${beleid.periode_dagen === 1 ? "dag" : `${beleid.periode_dagen} dagen`}, per rol. Reset op ${resetdatum(beleid.reset_op)}.`
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
          <div className="flex flex-col gap-3 sm:flex-row sm:flex-wrap sm:items-end">
            {beleid.rollen.map((r) => (
              <Field key={r.rol} label={`${rolLabel(r.rol)}: tokens per periode`}>
                <Input type="number" min={1} step={1} required value={perRol[r.rol] ?? ""}
                  onChange={(e) => setPerRol((oud) => ({ ...oud, [r.rol]: e.target.value }))} />
              </Field>
            ))}
            <Field label="Reset na (dagen)">
              <Input type="number" min={1} max={365} required value={dagen} onChange={(e) => setDagen(e.target.value)} />
            </Field>
          </div>
          <label className="flex items-start gap-2 text-sm text-ink">
            <input type="checkbox" className="mt-0.5 h-4 w-4 accent-lint" checked={actief} onChange={(e) => setActief(e.target.checked)} />
            <span>
              Begrenzing actief
              <span className="block text-xs text-muted">Uit: verbruik wordt nog steeds gemeten, maar niemand wordt tegengehouden.</span>
            </span>
          </label>
          <BewerkVoet submit bezig={bezig} gewijzigd opslaanTekst="Opslaan" onAnnuleer={() => { setBewerken(false); void laad(); }} />
        </form>
      )}
    </Card>
  );
}
