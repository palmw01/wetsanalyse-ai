"use client";

import { useState, type ReactNode } from "react";
import { actiefOnderdeel, reeksSamenvatting, type Reeks, type ReeksOnderdeel } from "@/lib/reeks";

/** Meerdere onderdelen van één artikel, geannoteerd in één run: per onderdeel een blok.
 *
 *  Het onderdeel waar Lex nu aan werkt staat open, met zijn eigen "zo is dit tot stand gekomen".
 *  Een onderdeel dat klaar is klapt in tot één regel met *Open ›* naar zijn annotatie; uitklappen
 *  laat het spoor weer zien. Zo blijft een reeks van twaalf leden leesbaar zonder dat er iets
 *  verdwijnt. *Stop* stopt het lopende onderdeel op de eerstvolgende grens en slaat de rest over;
 *  wat al klaar was blijft staan. */
export function ReeksBlok({
  reeks, loopt, onOpen, onStop, spoor,
}: {
  reeks: Reeks;
  /** Deze reeks is de lopende run in dit venster. */
  loopt: boolean;
  onOpen: (onderdeel: ReeksOnderdeel, index: number) => void;
  onStop?: () => void;
  /** Het stappenverloop van één onderdeel (denkproces + toolspoor), zoals bij een gewone beurt. */
  spoor: (onderdeel: ReeksOnderdeel, actief: boolean) => ReactNode;
}) {
  const bezig = actiefOnderdeel(reeks);
  return (
    <div className="rounded-kaart border border-line bg-surface shadow-zacht" aria-live="polite">
      <div className="flex items-center gap-3 border-b border-line px-4 py-2.5">
        <span className="min-w-0 flex-1">
          <span className="block truncate text-sm font-medium text-ink">
            Annotatie{reeks.ouder.label ? ` ${reeks.ouder.label}` : ""}
          </span>
          <span className="block text-xs text-muted">{reeksSamenvatting(reeks)}</span>
        </span>
        {loopt && !reeks.afgerond && onStop && (
          <button type="button" onClick={onStop}
            className="focus-ring rounded-full border border-line px-3 py-1 text-xs font-medium text-muted hover:text-ink">
            Stop
          </button>
        )}
      </div>
      <ol className="divide-y divide-line">
        {reeks.onderdelen.map((o, i) => (
          <OnderdeelRegel key={o.bron_iri} onderdeel={o} actief={o.bron_iri === bezig}
            onOpen={() => onOpen(o, i)} spoor={spoor} />
        ))}
      </ol>
    </div>
  );
}

function OnderdeelRegel({
  onderdeel: o, actief, onOpen, spoor,
}: {
  onderdeel: ReeksOnderdeel;
  actief: boolean;
  onOpen: () => void;
  spoor: (onderdeel: ReeksOnderdeel, actief: boolean) => ReactNode;
}) {
  const [keuze, setKeuze] = useState<boolean | null>(null);
  const open = keuze ?? actief;
  const heeftSpoor = !!(o.denk || o.tool_executions.length);
  return (
    <li className="px-4 py-2.5">
      <div className="flex items-center gap-3">
        <StatusIcoon status={o.status} />
        <button type="button" disabled={!heeftSpoor} onClick={() => setKeuze(!open)} aria-expanded={heeftSpoor ? open : undefined}
          className="min-w-0 flex-1 text-left disabled:cursor-default">
          <span className="block truncate text-sm text-ink">{o.label}</span>
          <span className="block text-xs text-muted">{detail(o)}</span>
        </button>
        {o.annotatie_doel && (
          <button type="button" onClick={onOpen}
            className="focus-ring shrink-0 rounded-full border border-line px-2.5 py-0.5 text-[11px] font-medium text-lint hover:bg-lint/5">
            Open ›
          </button>
        )}
      </div>
      {open && heeftSpoor && <div className="mt-2 pl-7">{spoor(o, actief)}</div>}
    </li>
  );
}

function detail(o: ReeksOnderdeel): string {
  switch (o.status) {
    case "wacht": return "wacht";
    case "bezig": return "bezig…";
    case "klaar": return o.voorstellen ? `${o.voorstellen} voorstel${o.voorstellen === 1 ? "" : "len"}` : "klaar – geen nieuwe voorstellen";
    case "hergebruik": return "al geannoteerd – bestaande annotatie hergebruikt";
    case "fout": return o.fout || "mislukt";
    case "gestopt": return "gestopt";
    case "overgeslagen": return "niet aan bod gekomen";
  }
}

function StatusIcoon({ status }: { status: ReeksOnderdeel["status"] }) {
  const basis = "flex h-4 w-4 shrink-0 items-center justify-center rounded-full text-[10px]";
  if (status === "bezig") return <span className={`${basis} border-2 border-lint/30 border-t-lint animate-spin`} aria-label="bezig" />;
  if (status === "klaar" || status === "hergebruik") return <span className={`${basis} bg-lint text-white`} aria-label="klaar">✓</span>;
  if (status === "fout") return <span className={`${basis} bg-red-600 text-white`} aria-label="mislukt">!</span>;
  return <span className={`${basis} border border-line text-faint`} aria-label={status}>·</span>;
}
