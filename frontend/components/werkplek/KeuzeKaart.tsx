"use client";

import { useEffect, useId, useRef, useState } from "react";
import type { AgentKandidaat, AgentKeuze, KandidaatStand } from "@/lib/types";

/** De keuze uit de onderdelen van één bepaling (leden, of subbepalingen als 9.1), in de thread.
 *
 *  Volgt de vraagkaart van Claude: één lijst, met het toetsenbord te bedienen. Enter of een klik
 *  op een regel annoteert dat ene onderdeel; spatie of het vinkje selecteert er meer, en dan
 *  annoteert "Annoteer geselecteerde" ze als één reeks – elk met een eigen laag. Per onderdeel staat
 *  hoe ver het werk is, zodat je niet aanvinkt wat al af is.
 *
 *  Bij `keuze.soort === "bepaling"` (een dubbelzinnig artikelnummer) is er precies één te kiezen:
 *  geen vinkjes. */
export function KeuzeKaart({
  kandidaten, keuze, uitgeschakeld, onKies,
}: {
  kandidaten: AgentKandidaat[];
  keuze: AgentKeuze;
  /** Er loopt al een beurt of het budget is op: de keuze blijft leesbaar, maar niet te bedienen. */
  uitgeschakeld: boolean;
  /** Eén onderdeel → een gewone beurt; meer → een reeks. */
  onKies: (gekozen: AgentKandidaat[]) => void;
}) {
  const meer = keuze.soort === "onderdeel";
  const [actief, setActief] = useState(0);
  const [selectie, setSelectie] = useState<Set<number>>(
    () => new Set(meer ? kandidaten.flatMap((k, i) => (k.gekozen ? [i] : [])) : []),
  );
  const lijstId = useId();
  const lijst = useRef<HTMLUListElement>(null);

  // De kaart verschijnt als antwoord op je vraag: de focus hoort erin, net als bij Claude.
  useEffect(() => {
    if (!uitgeschakeld) lijst.current?.focus({ preventScroll: true });
    // Alleen bij verschijnen; later niet de focus weggrijpen.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  function wissel(i: number) {
    setSelectie((s) => {
      const n = new Set(s);
      if (n.has(i)) n.delete(i); else n.add(i);
      return n;
    });
  }
  const geselecteerd = kandidaten.filter((_, i) => selectie.has(i));
  const verstuur = (ks: AgentKandidaat[]) => { if (!uitgeschakeld && ks.length) onKies(ks); };
  const soortNaam = kandidaten.every((k) => k.soort === "Lid") ? "leden" : "onderdelen";

  return (
    <div className="mt-2 rounded-kaart border border-line bg-surface shadow-zacht">
      {keuze.ouder && (
        <p className="border-b border-line px-4 py-2.5 text-sm font-medium text-ink">
          {keuze.ouder}
          <span className="ml-2 text-xs font-normal text-muted">
            {kandidaten.length} {meer ? soortNaam : "mogelijkheden"}
          </span>
        </p>
      )}
      <ul
        ref={lijst}
        id={lijstId}
        role="listbox"
        aria-label={meer ? `Kies ${soortNaam} om te annoteren` : "Kies de bepaling"}
        aria-multiselectable={meer || undefined}
        aria-activedescendant={`${lijstId}-${actief}`}
        aria-disabled={uitgeschakeld || undefined}
        tabIndex={uitgeschakeld ? -1 : 0}
        onKeyDown={(e) => {
          if (uitgeschakeld) return;
          if (e.key === "ArrowDown") { e.preventDefault(); setActief((i) => Math.min(i + 1, kandidaten.length - 1)); }
          else if (e.key === "ArrowUp") { e.preventDefault(); setActief((i) => Math.max(i - 1, 0)); }
          else if (e.key === "Home") { e.preventDefault(); setActief(0); }
          else if (e.key === "End") { e.preventDefault(); setActief(kandidaten.length - 1); }
          else if (e.key === " " && meer) { e.preventDefault(); wissel(actief); }
          else if (e.key === "Enter") {
            e.preventDefault();
            verstuur(geselecteerd.length ? geselecteerd : [kandidaten[actief]]);
          }
        }}
        className="max-h-80 overflow-y-auto p-1 outline-none focus-visible:ring-2 focus-visible:ring-lint/40"
      >
        {kandidaten.map((k, i) => (
          <li
            key={k.bron_iri ?? `${k.bwbId}|${k.artikel}|${k.lid ?? ""}`}
            id={`${lijstId}-${i}`}
            role="option"
            aria-selected={meer ? selectie.has(i) : i === actief}
            onMouseEnter={() => setActief(i)}
            onClick={() => verstuur([k])}
            className={`flex cursor-pointer items-start gap-3 rounded-lg px-3 py-2 text-left ${
              i === actief ? "bg-lint/[0.06]" : ""} ${uitgeschakeld ? "cursor-not-allowed opacity-50" : ""}`}
          >
            {meer && (
              <input
                type="checkbox"
                tabIndex={-1}
                checked={selectie.has(i)}
                disabled={uitgeschakeld}
                aria-label={`Selecteer ${k.label || k.artikel}`}
                onClick={(e) => e.stopPropagation()}
                onChange={() => wissel(i)}
                className="mt-0.5 h-4 w-4 shrink-0 accent-lint"
              />
            )}
            <span className="min-w-0 flex-1">
              <span className="flex items-center gap-2">
                <span className="text-sm font-medium text-ink">{k.label || `Artikel ${k.artikel}${k.lid ? `, lid ${k.lid}` : ""}`}</span>
                {k.stand && <StandBadge stand={k.stand} />}
              </span>
              {k.fragment && <span className="mt-0.5 block line-clamp-2 text-xs text-muted">{k.fragment}</span>}
            </span>
          </li>
        ))}
      </ul>
      <div className="flex flex-wrap items-center gap-2 border-t border-line px-3 py-2">
        {meer && keuze.alles && (
          <button type="button" disabled={uitgeschakeld} onClick={() => setSelectie(new Set(kandidaten.map((_, i) => i)))}
            className="focus-ring rounded-full border border-line px-3 py-1 text-xs font-medium text-lint hover:bg-lint/5 disabled:opacity-50">
            Alle {soortNaam}
          </button>
        )}
        {meer && (
          <button type="button" disabled={uitgeschakeld || !geselecteerd.length} onClick={() => verstuur(geselecteerd)}
            className="focus-ring rounded-full bg-lint px-3 py-1 text-xs font-medium text-white hover:bg-lint/90 disabled:opacity-40">
            Annoteer geselecteerde ({geselecteerd.length})
          </button>
        )}
        {meer && geselecteerd.length > 0 && <Samenvatting gekozen={geselecteerd} />}
        <span className="ml-auto text-[11px] text-faint">
          ↑↓ kiezen · Enter {meer ? (geselecteerd.length ? "annoteert selectie" : "annoteert dit onderdeel") : "annoteert"}{meer ? " · spatie selecteert" : ""}
        </span>
      </div>
    </div>
  );
}

const STAND_TEKST: Record<KandidaatStand["status"], (s: KandidaatStand) => string> = {
  nieuw: () => "nieuw",
  te_beoordelen: (s) => `${s.te_beoordelen} te beoordelen`,
  beoordeeld: () => "beoordeeld",
  afgerond: () => "afgerond",
};

function StandBadge({ stand }: { stand: KandidaatStand }) {
  const kleur = stand.status === "afgerond" ? "border-line text-faint"
    : stand.status === "te_beoordelen" ? "border-accent-soft/60 text-ink"
      : stand.status === "beoordeeld" ? "border-lint/30 text-lint" : "border-line text-muted";
  return <span className={`rounded-full border px-2 py-px text-[10px] ${kleur}`}>{STAND_TEKST[stand.status](stand)}</span>;
}

/** "3 gekozen · 2 nieuw · 1 al geannoteerd" – vóór het versturen, want elk onderdeel kost budget. */
function Samenvatting({ gekozen }: { gekozen: AgentKandidaat[] }) {
  const nieuw = gekozen.filter((k) => !k.stand || k.stand.status === "nieuw").length;
  const al = gekozen.length - nieuw;
  return (
    <span className="text-[11px] text-muted">
      {gekozen.length} gekozen{nieuw && al ? ` · ${nieuw} nieuw · ${al} al geannoteerd` : al ? " · al geannoteerd" : ""}
    </span>
  );
}
