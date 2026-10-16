"use client";

import { useCallback, useEffect, useRef, useState } from "react";

import { Button } from "@/components/ui/Button";
import { Select } from "@/components/ui/Field";
import { ChevronOmlaag } from "@/components/ui/Icoon";
import { Melding } from "@/components/ui/Melding";
import { foutTekst, haalActieveKaartRun, startKaartRun, stopRun, volgRun } from "@/lib/api";
import {
  ACTIES, BESLUIT_LABEL, VELD_LABEL, besloten, runMelding, schattingTekst, vergelijkKandidaten, voorstelTekst,
  waaromNiet,
} from "@/lib/begripLex";
import { voortgangsregel } from "@/lib/begripVoorstellen";
import type { Begrip, BegripSamenvatting, KaartActie, KaartVoorstellenAntwoord } from "@/lib/types";

const tijd = (iso: string) =>
  new Date(iso).toLocaleString("nl-NL", { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" });

/** *Lex naast de kaart*: vier knoppen boven de begripskaart. Een klik is de bevestiging (de knop noemt de
 *  schatting); de voorstellen verschijnen daarna onder het veld waar ze bij horen, in `BegripKaart`.
 *  Volgen en stoppen gaan als bij elke run van Lex; na herladen haakt de strook weer aan. */
export function BegripLex({ id, begrip, andere, onbewaard, data, onVernieuw }: {
  id: string;
  begrip: Begrip;
  andere: readonly BegripSamenvatting[];
  onbewaard: boolean;
  data: KaartVoorstellenAntwoord | null;
  /** Na een run: de voorstellen opnieuw laden. */
  onVernieuw: () => Promise<void>;
}) {
  const kandidaten = vergelijkKandidaten(begrip, andere);
  const [ander, setAnder] = useState<string>(kandidaten[0]?.id ?? "");
  const [agentRun, setAgentRun] = useState<string | null>(null);
  const [lopend, setLopend] = useState<KaartActie | null>(null);
  const [voortgang, setVoortgang] = useState<string[]>([]);
  const [fout, setFout] = useState<string | null>(null);
  const [melding, setMelding] = useState<string | null>(null);
  const kijker = useRef<AbortController | null>(null);
  const budgetOp = !!data?.budget?.geblokkeerd;

  // Het voorgevulde vergelijkingsbegrip volgt de lijst, tenzij de analist zelf koos.
  if (ander && !kandidaten.some((b) => b.id === ander)) setAnder(kandidaten[0]?.id ?? "");
  if (!ander && kandidaten[0]) setAnder(kandidaten[0].id);

  const volg = useCallback(async (runId: string) => {
    kijker.current?.abort();
    const ctl = new AbortController();
    kijker.current = ctl;
    setAgentRun(runId);
    setVoortgang([]);
    try {
      await volgRun(runId, { onStatus: (m) => setVoortgang((v) => [...v, voortgangsregel(m)]) }, 0, ctl.signal);
    } catch (e) {
      if ((e as Error)?.name === "AbortError") return;
      setFout(foutTekst(e, "Lex kon dit niet afmaken."));
    }
    if (ctl.signal.aborted) return;
    setAgentRun(null);
    setLopend(null);
    await onVernieuw();
  }, [onVernieuw]);

  useEffect(() => {
    void haalActieveKaartRun(begrip.id).then((r) => {
      if (r && r !== "onbekend") void volg(r.run_id);
    });
    return () => kijker.current?.abort();
  }, [begrip.id, volg]);

  async function start(actie: KaartActie) {
    setFout(null);
    setMelding(null);
    setLopend(actie);
    try {
      const { agent_run_id } = await startKaartRun(id, begrip.id, actie, actie === "betekenisverschil" ? ander : undefined);
      if (agent_run_id) await volg(agent_run_id);
      else {
        setLopend(null);
        await onVernieuw();
        setMelding("Voor deze stand van het begrip staan de voorstellen van Lex er al; ze staan bij de velden.");
      }
    } catch (e) {
      setLopend(null);
      setFout(foutTekst(e, "Lex kon niet beginnen."));
    }
  }

  const eerder = besloten(data?.voorstellen ?? []);
  return (
    <section className="space-y-3 rounded-button border border-line bg-paper p-3" aria-labelledby={`lex-${begrip.id}`} data-begrip-lex>
      <div className="flex flex-col gap-1 sm:flex-row sm:items-baseline sm:justify-between">
        <h3 id={`lex-${begrip.id}`} className="font-display text-sm font-semibold text-lint">Lex naast de kaart</h3>
        <p className="text-xs text-muted">Lex stelt voor, per veld; jij neemt over, past aan of wijst af.</p>
      </div>

      <ul className="grid gap-2 sm:grid-cols-2" aria-label="Acties van Lex">
        {ACTIES.map((a) => {
          const niet = waaromNiet(a.actie, begrip, { onbewaard, ander, budgetOp });
          const schatting = schattingTekst(a.actie, data);
          const melding = runMelding(data?.runs?.[a.actie]);
          return (
            <li key={a.actie} className="space-y-1.5 rounded-kaart border border-line p-2">
              {a.actie === "betekenisverschil" && (
                <Select value={ander} onChange={(e) => setAnder(e.target.value)} aria-label="Vergelijk met"
                  disabled={!kandidaten.length || !!agentRun}>
                  {!kandidaten.length && <option value="">Geen ander begrip in dit werkgebied</option>}
                  {kandidaten.map((b) => <option key={b.id} value={b.id}>Met “{b.inhoud.naam}”</option>)}
                </Select>
              )}
              <Button size="sm" variant="secondary" className="w-full" disabled={!!niet || !!agentRun}
                aria-describedby={`lex-${begrip.id}-${a.actie}`} onClick={() => void start(a.actie)}>
                {lopend === a.actie && agentRun ? "Lex is bezig…" : a.label}
              </Button>
              <p id={`lex-${begrip.id}-${a.actie}`} className="text-xs text-muted">
                {niet ?? a.uitleg}
                {!niet && a.model && (schatting ? ` Kost ${schatting}.` : " Kost tokens.")}
              </p>
              {melding && (
                <p className={`text-xs ${melding.soort === "fout" ? "text-aandacht-rood-tekst" : "text-ink"}`}>{melding.tekst}</p>
              )}
            </li>
          );
        })}
      </ul>

      {agentRun && (
        <div aria-live="polite" className="flex flex-col gap-2 text-xs text-muted sm:flex-row sm:items-start sm:justify-between">
          <div className="space-y-0.5">
            <p className="font-medium text-ink">Lex is bezig…</p>
            {voortgang.map((v, i) => <p key={i}>· {v}</p>)}
          </div>
          <Button size="sm" variant="ghost" className="w-full sm:w-auto" onClick={() => void stopRun(agentRun)}>Stoppen</Button>
        </div>
      )}
      {fout && <Melding type="fout" compact>{fout}</Melding>}
      {melding && <Melding type="uitleg" compact>{melding}</Melding>}
      {data?.budget?.actief && (
        <p className="text-xs text-muted">Je hebt nog {data.budget.resterend.toLocaleString("nl-NL")} tokens.</p>
      )}

      {eerder.length > 0 && (
        <details className="group text-sm">
          <summary className="focus-ring flex cursor-pointer list-none items-center gap-1.5 rounded text-xs font-medium text-muted">
            <ChevronOmlaag className="-rotate-90 transition-transform group-open:rotate-0" />
            Eerdere voorstellen van Lex <span className="font-normal text-faint">({eerder.length})</span>
          </summary>
          <ol className="mt-2 space-y-1.5" aria-label="Eerdere voorstellen van Lex">
            {eerder.map((v) => (
              <li key={v.id} className="border-b border-line pb-1.5 text-xs">
                <span className="text-ink">{VELD_LABEL[v.veld]}: “{voorstelTekst(v).slice(0, 160)}”</span>
                <span className="text-muted"> · {BESLUIT_LABEL[v.status]}
                  {v.besloten_door ? ` door ${v.besloten_door}` : ""}{v.besloten_op ? ` · ${tijd(v.besloten_op)}` : ""}
                  {v.reden ? ` · ${v.reden}` : ""}</span>
              </li>
            ))}
          </ol>
        </details>
      )}
    </section>
  );
}
