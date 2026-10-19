"use client";

import { useEffect, useId, useRef, useState } from "react";

import {
  ONBEKEND, STAPPEN, STAP_NAAM, antwoordActie, beginstand, type IntakeActie, type Vraagkaart,
} from "@/lib/vraagkaart";

/** Een vraag van Lex bij het samenstellen van een werkgebied (activiteit 1), in de thread.
 *
 *  Volgt de vraagkaart van Claude, net als `KeuzeKaart`: de voorstellen als lijst, een eigen antwoord
 *  eronder, en pas *Volgende* stuurt het antwoord in. Een klik op een voorstel selecteert alleen; zo kost
 *  een misklik geen beurt. Bij de regelingen en onderdelen staat altijd "Weet ik (nog) niet": dat sluit
 *  de andere keuzes uit, en andersom.
 *
 *  Alleen het laatste kaartje in de thread is te bedienen (`actief`); een eerder kaartje toont wat er
 *  gevraagd werd. De samenvatting toont wat er aangemaakt wordt, met *Aanmaken*, *Aanpassen* en
 *  *Afbreken*. */
export function VraagKaart({ kaart, actief, uitgeschakeld, onActie }: {
  kaart: Vraagkaart;
  actief: boolean;
  /** Er loopt een beurt of het budget is op. */
  uitgeschakeld: boolean;
  onActie: (actie: IntakeActie) => void;
}) {
  const begin = beginstand(kaart);
  const [gekozen, setGekozen] = useState<string[]>(begin.gekozen);
  const [eigen, setEigen] = useState(begin.eigen);
  const [cursor, setCursor] = useState(0);
  const lijstId = useId();
  const lijst = useRef<HTMLUListElement>(null);
  const veld = useRef<HTMLTextAreaElement>(null);
  const uit = uitgeschakeld || !actief;

  // Het kaartje verschijnt als antwoord op je vraag: de focus hoort erin, net als bij `KeuzeKaart`.
  useEffect(() => {
    if (uit || kaart.soort === "samenvatting") return;
    if (kaart.opties.length) lijst.current?.focus({ preventScroll: true });
    else veld.current?.focus({ preventScroll: true });
    // Alleen bij verschijnen; later niet de focus weggrijpen.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  function kies(waarde: string) {
    if (uit) return;
    setGekozen((g) => {
      if (!kaart.meerkeuze) return g[0] === waarde ? [] : [waarde];
      if (g.includes(waarde)) return g.filter((w) => w !== waarde);
      // "Weet ik (nog) niet" sluit de rest uit, en andersom.
      return waarde === ONBEKEND ? [ONBEKEND] : [...g.filter((w) => w !== ONBEKEND), waarde];
    });
    if (!kaart.meerkeuze) setEigen("");
  }
  const actie = antwoordActie(kaart, gekozen, eigen);
  const stuur = (a: IntakeActie | undefined) => { if (!uit && a) onActie(a); };
  const basis = { intake_id: kaart.intake_id, stap: kaart.stap };

  const kop = kaart.soort === "samenvatting" ? "Werkgebied · samenvatting" : `Werkgebied · vraag ${kaart.nr} van ${kaart.totaal}`;

  return (
    <div data-vraagkaart={kaart.stap} data-actief={actief || undefined}
      className={`mt-2 rounded-kaart border bg-surface shadow-zacht ${actief ? "border-lint/30" : "border-line opacity-80"}`}>
      <div className={`px-4 py-2.5 ${actief || kaart.soort === "samenvatting" ? "border-b border-line" : ""}`}>
        <p className="text-[11px] font-medium uppercase tracking-wide text-muted">{kop}</p>
        <p className="mt-0.5 text-sm font-medium text-ink">{kaart.vraag}</p>
        {kaart.toelichting && actief && <p className="mt-0.5 text-xs text-muted">{kaart.toelichting}</p>}
      </div>

      {kaart.soort === "samenvatting" && kaart.samenvatting ? (
        <Samenvatting kaart={kaart} uit={uit} onActie={stuur} />
      ) : actief ? (
        <>
          {kaart.opties.length > 0 && (
            <ul
              ref={lijst}
              id={lijstId}
              role="listbox"
              aria-label={kaart.vraag}
              aria-multiselectable={kaart.meerkeuze || undefined}
              aria-activedescendant={`${lijstId}-${cursor}`}
              aria-disabled={uit || undefined}
              tabIndex={uit ? -1 : 0}
              onKeyDown={(e) => {
                if (uit) return;
                if (e.key === "ArrowDown") { e.preventDefault(); setCursor((i) => Math.min(i + 1, kaart.opties.length - 1)); }
                else if (e.key === "ArrowUp") { e.preventDefault(); setCursor((i) => Math.max(i - 1, 0)); }
                else if (e.key === " ") { e.preventDefault(); kies(kaart.opties[cursor].waarde); }
                else if (e.key === "Enter") {
                  e.preventDefault();
                  stuur(actie ?? antwoordActie(kaart, [kaart.opties[cursor].waarde], ""));
                }
              }}
              className="max-h-72 overflow-y-auto p-1 outline-none focus-visible:ring-2 focus-visible:ring-lint/40"
            >
              {kaart.opties.map((o, i) => {
                const aan = gekozen.includes(o.waarde);
                return (
                  <li key={o.waarde} id={`${lijstId}-${i}`} role="option" aria-selected={aan}
                    onMouseEnter={() => setCursor(i)} onClick={() => kies(o.waarde)}
                    className={`flex cursor-pointer items-start gap-3 rounded-lg px-3 py-2 text-left ${
                      i === cursor ? "bg-lint/[0.06]" : ""} ${uit ? "cursor-not-allowed opacity-50" : ""}`}>
                    <input type={kaart.meerkeuze ? "checkbox" : "radio"} tabIndex={-1} checked={aan} disabled={uit}
                      aria-label={o.label} onClick={(e) => e.stopPropagation()} onChange={() => kies(o.waarde)}
                      className="mt-0.5 h-4 w-4 shrink-0 accent-lint" />
                    <span className={`min-w-0 flex-1 text-sm ${o.waarde === ONBEKEND ? "text-muted" : "text-ink"}`}>{o.label}</span>
                  </li>
                );
              })}
            </ul>
          )}
          {kaart.vrije_tekst && (
            <div className="border-t border-line px-3 py-2">
              <label className="block">
                <span className="sr-only">Eigen antwoord</span>
                <textarea
                  ref={veld}
                  rows={kaart.stap === "naam" ? 1 : 2}
                  value={eigen}
                  disabled={uit}
                  maxLength={kaart.stap === "naam" ? 200 : 2000}
                  placeholder={PLAATSHOUDER[kaart.stap] ?? "Of typ je eigen antwoord"}
                  onChange={(e) => {
                    setEigen(e.target.value);
                    // Een eigen antwoord vervangt bij één keuze het voorstel.
                    if (!kaart.meerkeuze && e.target.value.trim()) setGekozen([]);
                  }}
                  onKeyDown={(e) => {
                    if (e.key === "Enter" && !e.shiftKey && !e.nativeEvent.isComposing) { e.preventDefault(); stuur(actie); }
                  }}
                  className="focus-ring w-full resize-none rounded-lg border border-line bg-white px-3 py-2 text-sm text-ink placeholder:text-faint disabled:opacity-50"
                />
              </label>
            </div>
          )}
          <div className="flex flex-col gap-2 border-t border-line px-3 py-2 sm:flex-row sm:items-center">
            <button type="button" disabled={uit} onClick={() => stuur({ ...basis, actie: "afbreken" })}
              className="focus-ring rounded text-xs text-muted underline-offset-2 hover:underline disabled:opacity-50 sm:mr-auto">
              Stop met samenstellen
            </button>
            {kaart.overslaanbaar && (
              <button type="button" disabled={uit} onClick={() => stuur({ ...basis, actie: "overslaan" })}
                className="focus-ring rounded-full border border-line px-3 py-1 text-xs font-medium text-lint hover:bg-lint/5 disabled:opacity-50">
                Overslaan
              </button>
            )}
            <button type="button" disabled={uit || !actie} onClick={() => stuur(actie)}
              className="focus-ring rounded-full bg-lint px-3 py-1 text-xs font-medium text-white hover:bg-lint/90 disabled:opacity-40">
              {kaart.stap === "regelingen" && eigen.trim() && !gekozen.length ? "Zoeken" : "Volgende"}
            </button>
          </div>
        </>
      ) : null}
    </div>
  );
}

const PLAATSHOUDER: Partial<Record<Vraagkaart["stap"], string>> = {
  naam: "Bijvoorbeeld: Box 3-heffing",
  analysevraag: "Of formuleer je eigen analysevraag",
  regelingen: "Of zoek een regeling op naam of onderwerp",
  onderdelen: "Of noem artikelen, bijvoorbeeld 'artikel 5.2 en 5.3'",
  buiten: "Bijvoorbeeld: geen overgangsrecht",
};

function Samenvatting({ kaart, uit, onActie }: {
  kaart: Vraagkaart;
  uit: boolean;
  onActie: (a: IntakeActie) => void;
}) {
  const s = kaart.samenvatting!;
  const [aanpassen, setAanpassen] = useState(false);
  const basis = { intake_id: kaart.intake_id, stap: kaart.stap };
  return (
    <div>
      <dl className="space-y-2 px-4 py-3 text-sm">
        <Regel naam="Naam">{s.naam}</Regel>
        <Regel naam="Analysevraag">{s.analysevraag || <span className="text-muted">geen</span>}</Regel>
        <Regel naam="Afbakening">
          {s.afbakening ? <span className="whitespace-pre-line">{s.afbakening}</span> : <span className="text-muted">geen</span>}
        </Regel>
        <Regel naam="Bronnen">
          {s.bronnen.length
            ? <ul className="list-disc pl-4">{s.bronnen.map((b) => <li key={b}>{b}</li>)}</ul>
            : <span className="text-muted">nog geen – die voeg je later toe</span>}
        </Regel>
      </dl>
      {!uit && aanpassen && (
        <div className="flex flex-wrap gap-2 border-t border-line px-3 py-2">
          {STAPPEN.map((stap) => (
            <button key={stap} type="button" onClick={() => onActie({ ...basis, actie: "wijzig", naar: stap })}
              className="focus-ring rounded-full border border-line px-3 py-1 text-xs font-medium text-lint hover:bg-lint/5">
              {STAP_NAAM[stap].replace(/^de /, "").replace(/^\w/, (c) => c.toUpperCase())}
            </button>
          ))}
        </div>
      )}
      {!uit && (
        <div className="flex flex-col gap-2 border-t border-line px-3 py-2 sm:flex-row sm:items-center">
          <button type="button" onClick={() => onActie({ ...basis, actie: "afbreken" })}
            className="focus-ring rounded text-xs text-muted underline-offset-2 hover:underline sm:mr-auto">
            Stop met samenstellen
          </button>
          <button type="button" aria-expanded={aanpassen} onClick={() => setAanpassen((a) => !a)}
            className="focus-ring rounded-full border border-line px-3 py-1 text-xs font-medium text-lint hover:bg-lint/5">
            Aanpassen
          </button>
          <button type="button" onClick={() => onActie({ ...basis, actie: "aanmaken" })}
            className="focus-ring rounded-full bg-lint px-3 py-1 text-xs font-medium text-white hover:bg-lint/90">
            Werkgebied aanmaken
          </button>
        </div>
      )}
    </div>
  );
}

function Regel({ naam, children }: { naam: string; children: React.ReactNode }) {
  return (
    <div className="grid gap-0.5 sm:grid-cols-[8rem_1fr] sm:gap-3">
      <dt className="text-xs font-medium text-muted">{naam}</dt>
      <dd className="min-w-0 break-words text-ink">{children}</dd>
    </div>
  );
}
