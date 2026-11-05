"use client";

import { useCallback, useEffect, useState } from "react";
import { BewerkKnop, BewerkVoet } from "@/components/ui/Bewerkbaar";
import { Card } from "@/components/ui/Card";
import { Field, Input } from "@/components/ui/Field";
import { Melding } from "@/components/ui/Melding";
import { Skeleton } from "@/components/ui/Skeleton";
import { getBudgetBeleid, isApiError, zetBudgetBeleid } from "@/lib/api";
import { resetdatum, tokens } from "@/lib/tokenbudget";
import type { BudgetBeleid } from "@/lib/types";

/** Het systeembrede tokenbudget: hoeveel per gebruiker, en om de hoeveel dagen het weer vol is.
 *
 *  Staat boven de gebruikerslijst omdat een budget een eigenschap is van *wie* er werkt — niet van
 *  het model. Een individuele gebruiker kan hieronder een afwijkend budget krijgen.
 */
export function BudgetBeleidBlok({ onGewijzigd }: { onGewijzigd?: () => void }) {
  const [beleid, setBeleid] = useState<BudgetBeleid | null>(null);
  const [aantal, setAantal] = useState("");
  const [dagen, setDagen] = useState("");
  const [actief, setActief] = useState(true);
  const [fout, setFout] = useState<string | null>(null);
  const [bezig, setBezig] = useState(false);
  const [bewaard, setBewaard] = useState(false);
  const [bewerken, setBewerken] = useState(false);

  const laad = useCallback(async () => {
    setFout(null);
    try {
      const b = await getBudgetBeleid();
      setBeleid(b);
      setAantal(String(b.tokens));
      setDagen(String(b.periode_dagen));
      setActief(b.actief);
    } catch (e) {
      setFout(isApiError(e) ? `${e.detail} (${e.status})` : (e as Error).message);
    }
  }, []);

  useEffect(() => {
    // Data-load bij mount: setState gebeurt async ná de fetch.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    laad();
  }, [laad]);

  async function opslaan(e: React.FormEvent) {
    e.preventDefault();
    if (bezig) return;
    setBezig(true);
    setFout(null);
    setBewaard(false);
    try {
      const b = await zetBudgetBeleid({
        tokens: Number(aantal) || 0,
        periode_dagen: Number(dagen) || 1,
        actief,
      });
      setBeleid(b);
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
                ? `${tokens(beleid.tokens)} tokens per ${beleid.periode_dagen === 1 ? "dag" : `${beleid.periode_dagen} dagen`} voor wie geen eigen budget heeft.`
                : "De begrenzing staat uit; verbruik wordt wel gemeten."}
              {beleid.actief && ` Reset op ${resetdatum(beleid.reset_op)}.`}
            </p>
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
        Geldt voor iedereen zonder eigen budget. Elke vraag en elke annotatieronde van Lex telt mee, inclusief de
        wettekst die Lex erbij haalt.
      </p>

      {fout && <Melding type="fout" className="mt-3">{fout}</Melding>}

      {!beleid ? !fout && <Skeleton className="mt-3 h-10 w-full" /> : (
        <form onSubmit={opslaan} className="mt-3 space-y-3">
          <div className="flex flex-col gap-3 sm:flex-row sm:items-end">
            <Field label="Tokens per periode" hint="bijvoorbeeld 500000">
              <Input type="number" min={0} step={1000} required value={aantal} onChange={(e) => setAantal(e.target.value)} />
            </Field>
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
