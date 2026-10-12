"use client";

import { useEffect, useId, useMemo, useRef, useState } from "react";
import { Kruis, Zoek } from "@/components/ui/Icoon";
import { SOORT_LABEL, zoekKnopen } from "@/lib/graaf/bediening";
import type { GraafModel } from "@/lib/graaf/model";
import { eigenKleur } from "@/lib/graaf/stijl";

/** Zoeken in de graaf: een combobox linksboven in het canvas, over het hele model – ook wat een laag
 *  verbergt (dat staat erbij). Enter kiest, Escape sluit eerst de lijst en gaat niet door naar het
 *  paneel. Dit is ook de toetsenbordroute naar elke knoop. */
export function GraafZoek({ model, verborgen, gekozen, onKies }: {
  model: GraafModel; verborgen: ReadonlySet<string>; gekozen: string | null; onKies: (id: string) => void;
}) {
  const [vraag, setVraag] = useState("");
  const [open, setOpen] = useState(false);
  const [actief, setActief] = useState(0);
  const lijstId = useId();
  // Sluiten na blur wacht even (een klik op een optie moet eerst landen); focus of typen ná die
  // blur annuleert het, anders klapt de lijst dicht terwijl je al weer zoekt.
  const sluitTimer = useRef<ReturnType<typeof setTimeout>>(undefined);
  const openLijst = () => { clearTimeout(sluitTimer.current); setOpen(true); };
  useEffect(() => () => clearTimeout(sluitTimer.current), []);
  const resultaten = useMemo(() => zoekKnopen(model, vraag), [model, vraag]);

  function kies(id: string) {
    onKies(id);
    setOpen(false);
    setVraag("");
  }

  const toonLijst = open && !!vraag.trim();
  return <div className="pointer-events-auto relative w-[min(17rem,calc(100%-1.5rem))]">
    <div className="flex items-center gap-2 rounded-kaart border border-line bg-paper/95 px-2.5 shadow-kaart focus-within:border-lint/50">
      <Zoek className="text-muted" />
      <input role="combobox" aria-expanded={toonLijst} aria-controls={lijstId} aria-autocomplete="list" aria-label="Zoek in de graaf"
        aria-activedescendant={toonLijst && resultaten[actief] ? `${lijstId}-${actief}` : undefined}
        placeholder="Zoek artikel, lid, markering…" value={vraag}
        onChange={(e) => { setVraag(e.target.value); setActief(0); openLijst(); }}
        onFocus={openLijst} onClick={openLijst}
        onBlur={() => { sluitTimer.current = setTimeout(() => setOpen(false), 120); }}
        onKeyDown={(e) => {
          if (e.key === "ArrowDown") { e.preventDefault(); openLijst(); setActief((i) => Math.min(i + 1, resultaten.length - 1)); }
          else if (e.key === "ArrowUp") { e.preventDefault(); setActief((i) => Math.max(i - 1, 0)); }
          else if (e.key === "Enter" && resultaten[actief]) { e.preventDefault(); kies(resultaten[actief]); }
          else if (e.key === "Escape" && (open || vraag)) { e.stopPropagation(); setOpen(false); setVraag(""); }
        }}
        className="min-h-9 w-full bg-transparent py-1.5 text-xs text-ink outline-none placeholder:text-faint coarse:min-h-11" />
      {vraag && <button type="button" aria-label="Zoekvraag wissen" onClick={() => setVraag("")} className="focus-ring rounded p-1 text-muted hover:text-ink"><Kruis /></button>}
    </div>
    {toonLijst && <ul id={lijstId} role="listbox" aria-label="Gevonden in de graaf" className="absolute left-0 right-0 top-full z-20 mt-1 max-h-72 overflow-y-auto rounded-kaart border border-line bg-paper p-1 shadow-kaart">
      {resultaten.map((id, i) => {
        const a = model.getNodeAttributes(id);
        return <li key={id} id={`${lijstId}-${i}`} role="option" aria-selected={i === actief} data-knoop-id={id}
          aria-current={gekozen === id || undefined}
          onMouseDown={(e) => e.preventDefault()} onClick={() => kies(id)} onMouseEnter={() => setActief(i)}
          className={`flex cursor-pointer items-start gap-2 rounded-lg px-2 py-1.5 text-xs coarse:min-h-11 ${i === actief ? "bg-lint/10 text-lint" : "text-ink"}`}>
          <span className="mt-1 h-2.5 w-2.5 shrink-0 rounded-full border border-black/10" style={{ backgroundColor: eigenKleur(a) }} />
          <span className="min-w-0">
            <span className="block truncate">{a.naam}</span>
            <span className="text-[10px] text-faint">{SOORT_LABEL[a.soort]}{a.rand ? " · buiten wat geladen is" : ""}{verborgen.has(id) ? " · laag staat uit" : ""}</span>
          </span>
        </li>;
      })}
      {!resultaten.length && <li role="presentation" className="p-2 text-xs text-muted">Niets gevonden.</li>}
    </ul>}
  </div>;
}
