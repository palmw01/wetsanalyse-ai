"use client";

import { useEffect, useId, useRef, useState, useSyncExternalStore } from "react";

import { Button } from "@/components/ui/Button";
import { ChevronOmlaag, Kruis, PijlRechts, Vinkje } from "@/components/ui/Icoon";
import { Regel, Regels } from "@/components/ui/Lijst";
import {
  ONBEKEND, antwoordActie, beginstand, isLaatsteVraag, vorigeStap, type IntakeActie, type Vraagkaart,
} from "@/lib/vraagkaart";

/** De open vraag van Lex bij het samenstellen van een werkgebied (activiteit 1), onderaan de werkplek op
 *  de plek van het invoerveld – zoals Claude een vraag stelt.
 *
 *  - **Bladeren**: ‹ gaat terug naar de vorige vraag (graph-qa vult je eerdere antwoord in), › gaat
 *    verder met het antwoord dat er staat, alleen als deze vraag al beantwoord was.
 *  - **✕** klapt de vraag weg en geeft het invoerveld terug, bijvoorbeeld voor een tussenvraag; "Een
 *    vraag stellen ›" in de thread opent hem weer. Wegklikken beantwoordt niets.
 *  - **Opties** zijn regels met een titel en een omschrijving; een klik selecteert alleen, pas
 *    *Volgende* (of Enter) stuurt in. "Weet ik (nog) niet" sluit de andere keuzes uit, en andersom.
 *  - **"Typ je antwoord…"** is de laatste regel: met tekst erin krijgt hij het vinkje. Bij één keuze
 *    vervangt hij een gekozen optie; bij de regelingen is hij een zoekopdracht. Bij de deelvragen
 *    (`meer_tekst`) is elke eigen deelvraag een regel: Enter of *+ Nog een deelvraag* opent de
 *    volgende, *Volgende* stuurt alles in.
 *  - **Toetsenbord op mobiel**: de hoogte volgt `visualViewport`, zodat de sheet boven het toetsenbord
 *    past; kop en vraag scrollen mee, de knoppen ‹ › en ✕ blijven staan. */
export function VraagDock({ kaart, uitgeschakeld, onActie, onSluit }: {
  kaart: Vraagkaart;
  /** Het budget is op: de vraag blijft leesbaar, maar niet te bedienen. */
  uitgeschakeld: boolean;
  onActie: (actie: IntakeActie) => void;
  onSluit: () => void;
}) {
  const begin = beginstand(kaart);
  const [gekozen, setGekozen] = useState<string[]>(begin.gekozen);
  const [eigen, setEigen] = useState(begin.eigen);
  const [teksten, setTeksten] = useState<string[]>(begin.teksten);
  // Welke eigen regel de focus krijgt nadat er een bij kwam.
  const [nieuweRegel, setNieuweRegel] = useState<number | null>(null);
  const [cursor, setCursor] = useState(0);
  const lijstId = useId();
  const lijst = useRef<HTMLUListElement>(null);
  const veld = useRef<HTMLTextAreaElement>(null);
  const hoogte = useZichtbareHoogte();

  // De vraag verschijnt als antwoord op je vraag: de focus hoort erin. Op een touchscreen niet in het
  // tekstveld, want dat opent ongevraagd het toetsenbord.
  useEffect(() => {
    if (uitgeschakeld || kaart.soort === "samenvatting") return;
    if (kaart.opties.length) lijst.current?.focus({ preventScroll: true });
    else if (!window.matchMedia?.("(pointer: coarse)").matches) veld.current?.focus({ preventScroll: true });
    // Alleen bij verschijnen; later niet de focus weggrijpen.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  function kies(waarde: string) {
    if (uitgeschakeld) return;
    setGekozen((g) => {
      if (!kaart.meerkeuze) return g[0] === waarde ? [] : [waarde];
      if (g.includes(waarde)) return g.filter((w) => w !== waarde);
      return waarde === ONBEKEND ? [ONBEKEND] : [...g.filter((w) => w !== ONBEKEND), waarde];
    });
    if (!kaart.meerkeuze) setEigen("");
  }

  const basis = { intake_id: kaart.intake_id, stap: kaart.stap };
  const actie = antwoordActie(kaart, gekozen, eigen, teksten);
  const regelErbij = (na: number) => {
    setTeksten((t) => [...t.slice(0, na + 1), "", ...t.slice(na + 1)]);
    setNieuweRegel(na + 1);
  };
  const stuur = (a: IntakeActie | undefined) => { if (!uitgeschakeld && a) onActie(a); };
  const vorige = vorigeStap(kaart);
  const zoekt = kaart.stap === "regelingen" && !!eigen.trim() && !gekozen.length;
  const knop = kaart.soort === "samenvatting" ? "Werkgebied aanmaken" : zoekt ? "Zoek" : isLaatsteVraag(kaart) ? "Verzend" : "Volgende";

  return (
    <section
      aria-label="Vraag van Lex"
      data-vraagdock={kaart.stap}
      className="relative w-full overflow-hidden rounded-[24px] border border-line bg-white shadow-kaart"
    >
      <div className="overflow-y-auto overscroll-contain px-5 pb-4"
        style={{ maxHeight: hoogte ? `min(70dvh, ${Math.max(hoogte - 24, 240)}px)` : "70dvh" }}>
        {/* Bladeren en sluiten blijven staan terwijl de vraag meescrollt. */}
        <div className="sticky top-0 z-10 -mx-5 flex items-center gap-1 bg-white/95 px-3 pt-3 pb-1 backdrop-blur">
          <button type="button" aria-label="Vorige vraag" disabled={!vorige || uitgeschakeld}
            onClick={() => vorige && stuur({ ...basis, actie: "wijzig", naar: vorige })}
            className="focus-ring inline-flex h-9 w-9 items-center justify-center rounded-full text-ink hover:bg-surface disabled:opacity-30 coarse:h-11 coarse:w-11">
            <ChevronOmlaag className="rotate-90 text-lg" />
          </button>
          <span className="text-sm tabular-nums text-muted">
            {kaart.soort === "samenvatting" ? "Samenvatting" : `${kaart.nr} van ${kaart.totaal}`}
          </span>
          <button type="button" aria-label="Volgende vraag" disabled={!kaart.beantwoord || !actie || uitgeschakeld}
            onClick={() => stuur(actie)}
            className="focus-ring inline-flex h-9 w-9 items-center justify-center rounded-full text-ink hover:bg-surface disabled:opacity-30 coarse:h-11 coarse:w-11">
            <ChevronOmlaag className="-rotate-90 text-lg" />
          </button>
          <button type="button" aria-label="Vraag wegklikken" onClick={onSluit}
            className="focus-ring ml-auto inline-flex h-10 w-10 items-center justify-center rounded-full border border-line bg-white text-ink shadow-zacht hover:bg-surface coarse:h-11 coarse:w-11">
            <Kruis className="text-base" />
          </button>
        </div>

        <h2 className="mt-1 font-display text-lg font-semibold leading-snug text-ink sm:text-xl">{kaart.vraag}</h2>
        {kaart.toelichting && <p className="mt-1 text-sm text-muted">{kaart.toelichting}</p>}

        {kaart.soort === "samenvatting" && kaart.samenvatting ? (
          <Regels className="mt-3 text-[15px]">
            <Regel naam="Naam">{kaart.samenvatting.naam}</Regel>
            {(["aanleiding", "context", "doel"] as const).map((v) => (
              <Regel key={v} naam={DOSSIER_NAAM[v]}>
                {kaart.samenvatting?.[v] || <span className="text-muted">geen</span>}
              </Regel>
            ))}
            <Regel naam="Analysevraag">{kaart.samenvatting.analysevraag || <span className="text-muted">geen</span>}</Regel>
            <Regel naam="Praktijkvoorbeeld">
              {kaart.samenvatting.praktijkvoorbeeld || <span className="text-muted">geen</span>}
            </Regel>
            <Regel naam="Deelvragen">
              {kaart.samenvatting.deelvragen.length
                ? <ol className="list-decimal space-y-0.5 pl-5">{kaart.samenvatting.deelvragen.map((d) => <li key={d}>{d}</li>)}</ol>
                : <span className="text-muted">geen</span>}
            </Regel>
            <Regel naam="Afbakening">
              {kaart.samenvatting.afbakening
                ? <span className="whitespace-pre-line">{kaart.samenvatting.afbakening}</span>
                : <span className="text-muted">geen</span>}
            </Regel>
            <Regel naam="Bronnen">
              {kaart.samenvatting.bronnen.length
                ? <ul className="space-y-0.5">{kaart.samenvatting.bronnen.map((b) => <li key={b}>{b}</li>)}</ul>
                : <span className="text-muted">nog geen – die voeg je later toe</span>}
            </Regel>
          </Regels>
        ) : (
          <ul
            ref={lijst}
            id={lijstId}
            role="listbox"
            aria-label={kaart.vraag}
            aria-multiselectable={kaart.meerkeuze || undefined}
            aria-activedescendant={kaart.opties.length ? `${lijstId}-${cursor}` : undefined}
            aria-disabled={uitgeschakeld || undefined}
            tabIndex={uitgeschakeld || !kaart.opties.length ? -1 : 0}
            onKeyDown={(e) => {
              if (uitgeschakeld || e.target !== lijst.current || !kaart.opties.length) return;
              if (e.key === "ArrowDown") { e.preventDefault(); setCursor((i) => Math.min(i + 1, kaart.opties.length - 1)); }
              else if (e.key === "ArrowUp") { e.preventDefault(); setCursor((i) => Math.max(i - 1, 0)); }
              else if (e.key === " ") { e.preventDefault(); kies(kaart.opties[cursor].waarde); }
              else if (e.key === "Enter") {
                e.preventDefault();
                stuur(actie ?? antwoordActie(kaart, [kaart.opties[cursor].waarde], ""));
              }
            }}
            className="group mt-2 outline-none"
          >
            {kaart.opties.map((o, i) => {
              const aan = gekozen.includes(o.waarde);
              return (
                <li key={o.waarde} id={`${lijstId}-${i}`} role="option" aria-selected={aan}
                  onMouseEnter={() => setCursor(i)} onClick={() => kies(o.waarde)}
                  className={`-mx-2 flex cursor-pointer items-center gap-3 rounded-lg border-b border-line px-2 py-3.5 hover:bg-surface/60 ${
                    i === cursor ? "group-focus-visible:bg-surface group-focus-visible:ring-1 group-focus-visible:ring-lint/40" : ""} ${
                    uitgeschakeld ? "cursor-not-allowed opacity-50" : ""}`}>
                  <span className="min-w-0 flex-1">
                    <span className={`block text-[15px] font-medium ${o.waarde === ONBEKEND ? "text-muted" : "text-ink"}`}>{o.label}</span>
                    {o.omschrijving && <span className="mt-0.5 block text-sm text-muted">{o.omschrijving}</span>}
                  </span>
                  {aan && <Vinkje className="text-lg text-lint" />}
                </li>
              );
            })}
            {kaart.vrije_tekst && kaart.meer_tekst && (
              <li className="py-2" role="presentation">
                <ul className="space-y-1" aria-label="Je eigen deelvragen">
                  {teksten.map((t, i) => (
                    <li key={i} className="flex items-center gap-3 py-1.5">
                      <label className="min-w-0 flex-1">
                        <span className="sr-only">{`Eigen deelvraag ${i + 1}`}</span>
                        <textarea
                          rows={1}
                          value={t}
                          disabled={uitgeschakeld}
                          maxLength={1000}
                          autoFocus={nieuweRegel === i}
                          placeholder={i === 0 ? "Typ een eigen deelvraag…" : "Nog een deelvraag…"}
                          onChange={(e) => setTeksten((ts) => ts.map((x, j) => (j === i ? e.target.value : x)))}
                          onKeyDown={(e) => {
                            if (e.key !== "Enter" || e.shiftKey || e.nativeEvent.isComposing) return;
                            e.preventDefault();
                            // Ctrl/⌘+Enter stuurt in; Enter in een gevulde regel opent de volgende.
                            if (e.ctrlKey || e.metaKey) stuur(actie);
                            else if (t.trim()) regelErbij(i);
                          }}
                          className="block w-full resize-none border-0 bg-transparent p-0 text-[15px] text-ink placeholder:text-faint focus:outline-none focus:ring-0 disabled:opacity-50"
                        />
                      </label>
                      {t.trim() && <Vinkje className="text-lg text-lint" />}
                    </li>
                  ))}
                </ul>
                <button type="button" disabled={uitgeschakeld} onClick={() => regelErbij(teksten.length - 1)}
                  className="focus-ring mt-1 rounded text-sm font-medium text-lint hover:underline disabled:opacity-50">
                  + Nog een deelvraag
                </button>
              </li>
            )}
            {kaart.vrije_tekst && !kaart.meer_tekst && (
              <li className="flex items-center gap-3 py-3" role="presentation">
                <label className="min-w-0 flex-1">
                  <span className="sr-only">Typ je antwoord</span>
                  <textarea
                    ref={veld}
                    rows={LANG.has(kaart.stap) ? 3 : 1}
                    value={eigen}
                    disabled={uitgeschakeld}
                    maxLength={kaart.stap === "naam" ? 200 : LANG.has(kaart.stap) ? 4000 : 2000}
                    placeholder={kaart.stap === "regelingen" ? "Zoek een regeling op naam of onderwerp…" : "Typ je antwoord…"}
                    onChange={(e) => {
                      setEigen(e.target.value);
                      // Bij één keuze is je eigen antwoord dé keuze.
                      if (!kaart.meerkeuze && e.target.value.trim()) setGekozen([]);
                    }}
                    onKeyDown={(e) => {
                      if (e.key === "Enter" && !e.shiftKey && !e.nativeEvent.isComposing) { e.preventDefault(); stuur(actie); }
                    }}
                    className="block w-full resize-none border-0 bg-transparent p-0 text-[15px] text-ink placeholder:text-faint focus:outline-none focus:ring-0 disabled:opacity-50"
                  />
                </label>
                {eigen.trim() && <Vinkje className="text-lg text-lint" />}
              </li>
            )}
          </ul>
        )}

        <div className="mt-3 flex flex-col-reverse gap-2 sm:flex-row sm:items-center">
          <button type="button" disabled={uitgeschakeld} onClick={() => stuur({ ...basis, actie: "afbreken" })}
            className="focus-ring self-center rounded text-xs text-muted underline-offset-2 hover:underline disabled:opacity-50 sm:mr-auto sm:self-auto">
            Stop met samenstellen
          </button>
          <div className="flex gap-2 sm:justify-end">
            {kaart.overslaanbaar && (
              <Button pil variant="secondary" disabled={uitgeschakeld} className="flex-1 sm:flex-none"
                onClick={() => stuur({ ...basis, actie: "overslaan" })}>
                Sla over
              </Button>
            )}
            <Button pil disabled={uitgeschakeld || (kaart.soort !== "samenvatting" && !actie)} className="flex-1 sm:flex-none"
              onClick={() => stuur(kaart.soort === "samenvatting" ? { ...basis, actie: "aanmaken" } : actie)}>
              {knop}{knop !== "Verzend" && <PijlRechts />}
            </Button>
          </div>
        </div>
      </div>
    </section>
  );
}

// Vrije tekst die meer dan een regel vraagt (Shift+Enter voor een nieuwe regel).
const LANG = new Set<string>(["context", "praktijkvoorbeeld"]);

const DOSSIER_NAAM = { aanleiding: "Aanleiding", context: "Context", doel: "Doel" } as const;

/** De zichtbare hoogte boven het toetsenbord (`visualViewport`), of `null` zonder die API. */
function useZichtbareHoogte(): number | null {
  return useSyncExternalStore(
    (opNieuw) => {
      const vv = window.visualViewport;
      vv?.addEventListener("resize", opNieuw);
      return () => vv?.removeEventListener("resize", opNieuw);
    },
    () => window.visualViewport?.height ?? null,
    () => null,
  );
}
