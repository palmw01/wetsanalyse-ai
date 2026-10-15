"use client";

import { Button } from "@/components/ui/Button";
import { ButtonRow } from "@/components/ui/ButtonRow";
import { Dialog } from "@/components/ui/Dialog";
import { Melding } from "@/components/ui/Melding";
import { meedenkInhoud, meedenkOmvang } from "@/lib/begripVoorstellen";
import type { VerdiepingWerkvoorraad } from "@/lib/types";
import { getal } from "@/lib/werkgebiedAnnoteren";

/** De bevestiging vóór Lex meedenkt over de begripsvoorstellen (fase C): hoeveel, wat het naar
 *  schatting kost, wat er over is, en wat Lex wel en niet doet.
 *
 *  Lex begint nooit zonder dit akkoord. Wat de analist bevestigt is het aantal dat hier staat; is de
 *  werkvoorraad intussen veranderd, dan begint graph-qa niet en zegt hij dat. Op een smal scherm is
 *  het een sheet (`compact`). */
export function MeedenkBevestiging({ werkvoorraad: wv, onSluit, onBevestig }: {
  werkvoorraad: VerdiepingWerkvoorraad;
  onSluit: () => void;
  onBevestig: (aantal: number) => void;
}) {
  const inhoud = meedenkInhoud(wv);
  const geblokkeerd = !!wv.budget?.geblokkeerd;
  return (
    <Dialog label="Laat Lex meedenken over de begrippen" variant="compact" onSluit={onSluit}>
      <div className="flex shrink-0 items-center justify-between gap-3 border-b border-line px-5 py-3.5 pt-[max(0.875rem,env(safe-area-inset-top))]">
        <h2 className="font-display text-base font-semibold text-lint">Laat Lex meedenken</h2>
        <button type="button" onClick={onSluit} aria-label="Sluiten"
          className="focus-ring -mr-1 rounded-kaart p-1.5 text-muted transition-colors hover:bg-surface hover:text-ink">
          <svg viewBox="0 0 20 20" className="h-5 w-5" fill="none" stroke="currentColor" strokeWidth="1.6" aria-hidden="true">
            <path d="M5 5l10 10M15 5L5 15" strokeLinecap="round" />
          </svg>
        </button>
      </div>
      <div className="flex min-h-0 flex-col gap-4 overflow-y-auto p-6 text-sm text-ink" data-meedenk={inhoud.aantal}>
        <p>
          Lex denkt mee over <span className="font-semibold">{meedenkOmvang(inhoud)}</span>. Je volgt het in een
          gesprek; daarna staan de voorstellen hier, met het advies en de kaarten erbij.
        </p>
        <ul className="ml-5 list-disc space-y-1 text-muted">
          <li>Bij een twijfelpunt geeft Lex advies; de vraag blijft staan tot jij beslist.</li>
          <li>Een definitie komt bij voorkeur letterlijk uit de bron. Formuleert Lex haar zelf, dan staat ze geel, met de
            passages waarop ze rust.</li>
          {inhoud.alKlaar > 0 && <li>{inhoud.alKlaar === 1 ? "1 batch is" : `${inhoud.alKlaar} batches zijn`} al klaar;
            Lex gaat verder waar hij bleef.</li>}
        </ul>
        <dl className="grid grid-cols-[auto_1fr] gap-x-4 gap-y-1.5">
          <dt className="text-muted">Naar schatting</dt>
          <dd>
            {inhoud.schatting !== null ? `~${getal(inhoud.schatting)} tokens` : "nog geen schatting"}
            {inhoud.schattingUitleg && <span className="block text-xs text-muted">{inhoud.schattingUitleg}</span>}
          </dd>
          <dt className="text-muted">Je hebt nog</dt>
          <dd>{inhoud.budgetOver !== null ? `${getal(inhoud.budgetOver)} tokens` : "geen limiet ingesteld"}</dd>
        </dl>
        {inhoud.budgetKrap && (
          <Melding type="waarschuwing" compact>
            De schatting is hoger dan wat je nog hebt. Lex stopt tussen twee batches als je budget op is; wat klaar is,
            blijft bewaard.
          </Melding>
        )}
        {geblokkeerd && <Melding type="fout" compact>Je tokenbudget voor deze periode is op.</Melding>}
        <ButtonRow>
          <Button variant="secondary" onClick={onSluit}>Annuleren</Button>
          <Button disabled={geblokkeerd || inhoud.aantal === 0} onClick={() => onBevestig(inhoud.aantal)}>
            Start ({inhoud.aantal})
          </Button>
        </ButtonRow>
      </div>
    </Dialog>
  );
}
