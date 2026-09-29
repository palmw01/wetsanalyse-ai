"use client";

import { useId, useMemo, useState } from "react";
import { Kruis, Zoek } from "@/components/ui/Icoon";
import { SOORT_LABEL, zoekKnopen, type GraafData, type GraafKnoop } from "@/lib/samenhang";

/** Zoeken in de graaf: een combobox linksboven in het canvas. Zoekt over álle knopen, ook
 *  verborgen; een lege focus toont wat in beeld staat, zodat de lijst ook de toetsenbordroute is.
 *  Escape sluit eerst de lijst en gaat niet door naar het paneel. */
export function GraafZoek({ graaf, zichtbaar, gekozen, onKies }: {
  graaf: GraafData; zichtbaar: GraafKnoop[]; gekozen: string; onKies: (id: string) => void;
}) {
  const [vraag, setVraag] = useState("");
  const [open, setOpen] = useState(false);
  const [actief, setActief] = useState(0);
  const lijstId = useId();
  const resultaten = useMemo(() => vraag.trim() ? zoekKnopen(graaf, vraag) : zichtbaar.slice(0, 40), [graaf, vraag, zichtbaar]);
  const zichtbareIds = useMemo(() => new Set(zichtbaar.map((n) => n.id)), [zichtbaar]);

  function kies(n: GraafKnoop) {
    onKies(n.id);
    setOpen(false);
    setVraag("");
  }

  return <div className="pointer-events-auto relative w-[min(17rem,calc(100%-1.5rem))]">
    <div className="flex items-center gap-2 rounded-kaart border border-line bg-paper/95 px-2.5 shadow-kaart focus-within:border-lint/50">
      <Zoek className="text-muted" />
      <input role="combobox" aria-expanded={open} aria-controls={lijstId} aria-autocomplete="list" aria-label="Knoop zoeken"
        aria-activedescendant={open && resultaten[actief] ? `${lijstId}-${actief}` : undefined}
        placeholder="Zoek knoop…" value={vraag}
        onChange={(e) => { setVraag(e.target.value); setActief(0); setOpen(true); }}
        onFocus={() => setOpen(true)} onClick={() => setOpen(true)}
        onBlur={() => setTimeout(() => setOpen(false), 120)}
        onKeyDown={(e) => {
          if (e.key === "ArrowDown") { e.preventDefault(); setOpen(true); setActief((i) => Math.min(i + 1, resultaten.length - 1)); }
          else if (e.key === "ArrowUp") { e.preventDefault(); setActief((i) => Math.max(i - 1, 0)); }
          else if (e.key === "Enter" && resultaten[actief]) { e.preventDefault(); kies(resultaten[actief]); }
          else if (e.key === "Escape" && (open || vraag)) { e.stopPropagation(); setOpen(false); setVraag(""); }
        }}
        className="min-h-9 w-full bg-transparent py-1.5 text-xs text-ink outline-none placeholder:text-faint coarse:min-h-11" />
      {vraag && <button type="button" aria-label="Zoekvraag wissen" onClick={() => setVraag("")} className="focus-ring rounded p-1 text-muted hover:text-ink"><Kruis /></button>}
    </div>
    {open && <ul id={lijstId} role="listbox" aria-label="Knopen" className="absolute left-0 right-0 top-full z-20 mt-1 max-h-72 overflow-y-auto rounded-kaart border border-line bg-paper p-1 shadow-kaart">
      {!vraag.trim() && <li role="presentation" className="px-2 pb-1 pt-1.5 text-[10px] font-semibold uppercase tracking-wider text-faint">In beeld</li>}
      {resultaten.map((n, i) => <li key={n.id} id={`${lijstId}-${i}`} role="option" aria-selected={i === actief} data-knoop-id={n.id}
        aria-current={gekozen === n.id || undefined}
        onMouseDown={(e) => e.preventDefault()} onClick={() => kies(n)} onMouseEnter={() => setActief(i)}
        className={`flex cursor-pointer items-start gap-2 rounded-lg px-2 py-1.5 text-xs ${i === actief ? "bg-lint/10 text-lint" : "text-ink"}`}>
        <span className="mt-1 h-2.5 w-2.5 shrink-0 rounded-full border border-black/10" style={{ backgroundColor: n.kleur }} />
        <span className="min-w-0">
          <span className="block truncate">{n.label}</span>
          <span className="text-[10px] text-faint">{SOORT_LABEL[n.soort]}{n.rand ? " · buiten dit artikel" : ""}{!zichtbareIds.has(n.id) ? " · nu verborgen" : ""}</span>
        </span>
      </li>)}
      {!resultaten.length && <li role="presentation" className="p-2 text-xs text-muted">Geen knopen gevonden.</li>}
    </ul>}
  </div>;
}
