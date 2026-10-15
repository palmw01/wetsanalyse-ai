"use client";

import { useEffect, useState } from "react";

import { Button } from "@/components/ui/Button";
import { ButtonRow } from "@/components/ui/ButtonRow";
import { Dialog } from "@/components/ui/Dialog";
import { Melding } from "@/components/ui/Melding";
import { Skeleton } from "@/components/ui/Skeleton";
import { foutTekst, haalAnnotatieWerkvoorraad } from "@/lib/api";
import type { AnnotatieWerkvoorraad } from "@/lib/types";
import { bepalingen, bevestigingInhoud, getal, isWerkvoorraad } from "@/lib/werkgebiedAnnoteren";

/** De bevestiging vóór Lex het werkgebied annoteert (fase B): hoeveel, wat het naar schatting kost,
 *  wat er over is, en wat er níét meegaat. Gedeeld door de tab Elementen en de werkgebiedbalk.
 *
 *  Lex begint nooit zonder dit akkoord. Wat de analist bevestigt is het aantal dat hier staat; is de
 *  werkvoorraad intussen veranderd, dan begint graph-qa niet en zegt hij dat. Op een smal scherm is
 *  het een sheet (`compact`). */
export function AnnoterenBevestiging({ werkgebiedId, werkvoorraad, onSluit, onBevestig }: {
  werkgebiedId: string;
  /** Al geladen (de tab Elementen); anders haalt de dialoog hem zelf op. */
  werkvoorraad?: AnnotatieWerkvoorraad | null;
  onSluit: () => void;
  onBevestig: (aantal: number) => void;
}) {
  const [wv, setWv] = useState<AnnotatieWerkvoorraad | null>(werkvoorraad ?? null);
  const [fout, setFout] = useState<string | null>(null);

  useEffect(() => {
    if (werkvoorraad) return;
    let levend = true;
    haalAnnotatieWerkvoorraad(werkgebiedId)
      .then((w) => {
        if (!levend) return;
        if (isWerkvoorraad(w)) setWv(w);
        else setFout("De werkvoorraad kon niet worden gelezen.");
      })
      .catch((e) => levend && setFout(foutTekst(e, "De werkvoorraad kon niet worden opgehaald.")));
    return () => { levend = false; };
  }, [werkgebiedId, werkvoorraad]);

  const inhoud = wv ? bevestigingInhoud(wv) : null;
  const geblokkeerd = !!wv?.budget.geblokkeerd;

  return (
    <Dialog label="Laat Lex het werkgebied annoteren" variant="compact" onSluit={onSluit}>
      <div className="flex shrink-0 items-center justify-between gap-3 border-b border-line px-5 py-3.5 pt-[max(0.875rem,env(safe-area-inset-top))]">
        <h2 className="font-display text-base font-semibold text-lint">Laat Lex annoteren</h2>
        <button type="button" onClick={onSluit} aria-label="Sluiten"
          className="focus-ring -mr-1 rounded-kaart p-1.5 text-muted transition-colors hover:bg-surface hover:text-ink">
          <svg viewBox="0 0 20 20" className="h-5 w-5" fill="none" stroke="currentColor" strokeWidth="1.6" aria-hidden="true">
            <path d="M5 5l10 10M15 5L5 15" strokeLinecap="round" />
          </svg>
        </button>
      </div>
      <div className="flex min-h-0 flex-col gap-4 overflow-y-auto p-6 text-sm text-ink" data-werkvoorraad={inhoud?.aantal ?? ""}>
        {fout ? (
          <Melding type="fout">{fout}</Melding>
        ) : !inhoud || !wv ? (
          <div className="space-y-2" aria-busy="true">
            <p className="text-muted">De bronnen en hun annotaties worden opgehaald…</p>
            <Skeleton className="h-4 w-48" />
            <Skeleton className="h-4 w-64" />
          </div>
        ) : inhoud.aantal === 0 ? (
          <p>Niets nieuws te annoteren in <span className="font-medium">{wv.naam}</span>: elke bepaling van de
            analysebronnen heeft al een annotatie.</p>
        ) : (
          <>
            <p>
              Lex annoteert <span className="font-semibold">{bepalingen(inhoud.dezeRun)}</span> in{" "}
              <span className="font-medium">{wv.naam}</span>, één voor één. Je volgt het per bepaling in een
              nieuw gesprek, en beoordeelt de voorstellen daarna.
            </p>
            <dl className="grid grid-cols-[auto_1fr] gap-x-4 gap-y-1.5">
              <dt className="text-muted">Naar schatting</dt>
              <dd>
                {inhoud.schatting !== null ? `~${getal(inhoud.schatting)} tokens` : "nog geen schatting"}
                <span className="block text-xs text-muted">{inhoud.schattingUitleg}</span>
              </dd>
              <dt className="text-muted">Je hebt nog</dt>
              <dd>{inhoud.budgetOver !== null ? `${getal(inhoud.budgetOver)} tokens` : "geen limiet ingesteld"}</dd>
            </dl>
            {inhoud.budgetKrap && (
              <Melding type="waarschuwing" compact>
                De schatting is hoger dan wat je nog hebt. Lex stopt tussen twee bepalingen als je budget op is;
                wat dan nog nieuw is, blijft staan voor later.
              </Melding>
            )}
            {inhoud.nietMee.length > 0 && (
              <div>
                <p className="text-muted">Niet mee:</p>
                <ul className="ml-5 list-disc">
                  {inhoud.nietMee.map((r) => <li key={r}>{r}</li>)}
                </ul>
              </div>
            )}
            {inhoud.openPunten.length > 0 && (
              <Melding type="waarschuwing" titel="Niet elke bron is bereikbaar" compact>
                <ul className="ml-4 list-disc">{inhoud.openPunten.map((p) => <li key={p}>{p}</li>)}</ul>
              </Melding>
            )}
            {geblokkeerd && <Melding type="fout" compact>Je tokenbudget voor deze periode is op.</Melding>}
          </>
        )}
        <ButtonRow>
          <Button variant="secondary" onClick={onSluit}>Annuleren</Button>
          {inhoud && inhoud.aantal > 0 && (
            <Button disabled={geblokkeerd} onClick={() => onBevestig(inhoud.aantal)}>
              Start ({bepalingen(inhoud.dezeRun)})
            </Button>
          )}
        </ButtonRow>
      </div>
    </Dialog>
  );
}
