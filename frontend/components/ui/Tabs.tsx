"use client";

import { Fragment, useEffect, useId, useRef, useState, type ReactNode } from "react";
import { TABRIJ } from "./Pagina";

export interface TabDef {
  /** Stabiele sleutel; ook gebruikt voor de aria-id's. */
  key: string;
  label: string;
  content: ReactNode;
  /** Aantal openstaande items; > 0 toont een telbadge achter het label. De tab blijft toegankelijk
   *  benoemd via `label` – de badge zelf is `aria-hidden` en dus geen ruis voor schermlezers. */
  badge?: number;
  /** In de tabkolom: de kop van de groep die bij deze tab begint (*Beheer*). */
  groep?: string;
}

// Toegankelijke tablist in Rijkshuisstijl: lintblauw onderlijn-indicator op de actieve tab.
// Beide panelen blijven gemount; het inactieve krijgt `hidden` (display:none) i.p.v. te unmounten,
// zodat de print-/PDF-stylesheet ze allebei kan tonen. Pijltjestoetsen verplaatsen de focus.
//
// De tabkolom (`vertical`, het instellingenvenster) is op een telefoon een lijst naar het voorbeeld van de instellingen
// van iOS en Claude: eerst de lijst, een gekozen tab vervangt hem, en *‹ <label>* gaat terug. Vanaf `sm:` staan lijst en
// paneel naast elkaar en bestaat die terugknop niet.
export function Tabs({
  tabs,
  active,
  onChange,
  orientation = "horizontal",
  lazy = false,
  label = "Fasen",
  verborgen,
  zoek,
}: {
  tabs: TabDef[];
  active: string;
  onChange: (key: string) => void;
  /** `vertical` = tabkolom links (instellingen); `horizontal` = onderlijn-indicator (rapport). */
  orientation?: "horizontal" | "vertical";
  /** Alleen het actieve paneel renderen. Zet dit aan als panelen bij mount data ophalen – anders
   *  vuurt élk paneel zijn fetch zodra de tabs verschijnen. Uit (default) blijft alles gemount,
   *  wat de print-/PDF-stylesheet nodig heeft. */
  lazy?: boolean;
  label?: string;
  /** Tabs die niet in de kolom staan (een zoekterm vond ze niet). Hun paneel blijft bereikbaar als ze actief zijn. */
  verborgen?: ReadonlySet<string>;
  /** Alleen bij `vertical`: boven de tabkolom, bijvoorbeeld een zoekveld. */
  zoek?: ReactNode;
}) {
  const base = useId();
  const tabRefs = useRef<Record<string, HTMLButtonElement | null>>({});
  const verticaal = orientation === "vertical";
  // Op een telefoon: staat de lijst open (en niet het paneel)? Vanaf `sm:` doet dit niets.
  const [opLijst, setOpLijst] = useState(false);
  const inKolom = tabs.filter((t) => !verborgen?.has(t.key));

  function kies(key: string) {
    setOpLijst(false);
    onChange(key);
  }

  function onKeyDown(e: React.KeyboardEvent, index: number) {
    const [vorige, volgende] = verticaal ? ["ArrowUp", "ArrowDown"] : ["ArrowLeft", "ArrowRight"];
    if (e.key !== volgende && e.key !== vorige) return;
    e.preventDefault();
    const next = e.key === volgende ? (index + 1) % inKolom.length : (index - 1 + inKolom.length) % inKolom.length;
    const nextKey = inKolom[next].key;
    onChange(nextKey);
    tabRefs.current[nextKey]?.focus();
  }

  const lijstKlasse = verticaal
    ? // Mobiel een lijst over de volle breedte (de `nav` verbergt hem als het paneel open is); vanaf sm een kolom links.
      "flex flex-col gap-0.5 px-2 py-2 sm:py-3"
    : // Een rij die op een smal scherm niet past scrolt, in plaats van tabs af te kappen.
      `${TABRIJ} print:hidden`;

  const tablist = (
    <div role="tablist" aria-label={label} aria-orientation={verticaal ? "vertical" : undefined} className={lijstKlasse}>
      {inKolom.map((t, i) => {
        const selected = t.key === active;
        const basis =
          "min-h-[44px] text-sm font-medium transition-colors focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-lint";
        return (
          <Fragment key={t.key}>
            {verticaal && t.groep && (
              <span role="presentation" className="block px-3 pb-1 pt-3 text-xs font-medium text-faint first:pt-1">
                {t.groep}
              </span>
            )}
            <button
              ref={(el) => {
                tabRefs.current[t.key] = el;
              }}
              role="tab"
              id={`${base}-tab-${t.key}`}
              aria-selected={selected}
              aria-controls={`${base}-panel-${t.key}`}
              tabIndex={selected || (!inKolom.some((x) => x.key === active) && i === 0) ? 0 : -1}
              onClick={() => kies(t.key)}
              onKeyDown={(e) => onKeyDown(e, i)}
              className={
                verticaal
                  ? `${basis} w-full shrink-0 whitespace-nowrap rounded-kaart px-3 py-2 text-left ${
                      selected ? "bg-surface text-lint" : "text-muted hover:bg-surface hover:text-lint"
                    }`
                  : `${basis} shrink-0 whitespace-nowrap border-b-2 px-4 py-2 ${
                      selected ? "border-lint text-lint" : "border-transparent text-muted hover:text-lint"
                    }`
              }
            >
              {t.label}
              {t.badge !== undefined && t.badge > 0 && (
                <span
                  aria-hidden
                  className="ml-1.5 inline-flex h-4 min-w-[1rem] items-center justify-center rounded-full bg-accent px-1 text-3xs font-bold leading-none text-paper"
                >
                  {t.badge > 99 ? "99+" : t.badge}
                </span>
              )}
            </button>
          </Fragment>
        );
      })}
      {verticaal && inKolom.length === 0 && (
        <p className="px-3 py-2 text-sm text-muted" role="presentation">Niets gevonden.</p>
      )}
    </div>
  );

  const panelen = tabs.map((t) => {
    const selected = t.key === active;
    if (lazy && !selected) return null;
    return (
      <div
        key={t.key}
        role="tabpanel"
        id={`${base}-panel-${t.key}`}
        aria-labelledby={`${base}-tab-${t.key}`}
        data-tabpanel
        hidden={!selected}
        // `min-w-0` en `anywhere`: een lang adres of een lange modelnaam breekt af in plaats van de kolom breder te maken.
        className={verticaal ? "min-h-0 min-w-0 flex-1 overflow-y-auto px-5 py-5 [overflow-wrap:anywhere]" : "pt-6"}
      >
        {t.content}
      </div>
    );
  });

  if (!verticaal) return <div>{tablist}{panelen}</div>;

  const actieveTab = tabs.find((t) => t.key === active);
  return (
    <div className="flex min-h-0 flex-1 flex-col sm:flex-row">
      <nav
        className={`flex min-h-0 shrink-0 flex-col overflow-y-auto overscroll-contain sm:w-56 sm:border-r sm:border-line ${opLijst ? "max-sm:flex-1" : "max-sm:hidden"}`}>
        {zoek && <div className="px-3 pt-3">{zoek}</div>}
        {tablist}
      </nav>
      <div className={`flex min-h-0 min-w-0 flex-1 flex-col ${opLijst ? "max-sm:hidden" : ""}`}>
        {/* Alleen op een telefoon: terug naar de lijst, met waar je bent. */}
        <div className="flex shrink-0 items-center gap-2 border-b border-line px-3 py-2 sm:hidden">
          <button type="button" onClick={() => setOpLijst(true)} data-naar-lijst
            className="focus-ring inline-flex min-h-[44px] items-center gap-1 rounded-knop px-2 text-sm font-medium text-lint hover:bg-surface">
            <span aria-hidden>‹</span> Alle {label.toLowerCase()}
          </button>
          {actieveTab && <span className="truncate text-sm text-muted" aria-hidden>{actieveTab.label}</span>}
        </div>
        {panelen}
      </div>
    </div>
  );
}

export interface TabRijItem {
  key: string;
  label: string;
  /** De tooltip: het volle label, en waar de tab geopend werd. */
  title?: string;
  icoon?: ReactNode;
  /** Een ✕ achter de tab; zonder is de tab niet los te sluiten. */
  onSluit?: () => void;
}

/** Alleen de tabrij, voor een paneel waarvan de inhoud elders staat (de tabs van het zijpaneel, het bronvenster PR 3b):
 *  dezelfde tablist als `Tabs` (`TABRIJ`, scrollt horizontaal, pijltjestoetsen verplaatsen de focus), compact van hoogte
 *  en met een ✕ per tab. Een tab sluiten is een eigen knop naast de tab, niet erin: een knop in een knop kan niet. */
export function TabRij({ tabs, active, onChange, label, soort = "paneel" }: {
  tabs: readonly TabRijItem[];
  active?: string;
  onChange: (key: string) => void;
  label: string;
  /** `paneel`: de tabs van het zijpaneel (`data-paneel-tab`); `weergave`: Tekst | Graaf in een venster
   *  (`data-weergave-tab`, `WeergaveBalk`). Dezelfde rij, een ander anker. */
  soort?: "paneel" | "weergave";
}) {
  const refs = useRef<Record<string, HTMLButtonElement | null>>({});
  useEffect(() => {
    if (active) refs.current[active]?.scrollIntoView?.({ block: "nearest", inline: "nearest" });
  }, [active]);
  function onKeyDown(e: React.KeyboardEvent, index: number) {
    if (e.key !== "ArrowRight" && e.key !== "ArrowLeft") return;
    e.preventDefault();
    const next = (index + (e.key === "ArrowRight" ? 1 : -1) + tabs.length) % tabs.length;
    onChange(tabs[next].key);
    refs.current[tabs[next].key]?.focus();
  }
  return (
    <div role="tablist" aria-label={label} className={`${TABRIJ} min-w-0 flex-1 shadow-none`}>
      {tabs.map((t, i) => {
        const gekozen = t.key === active;
        return (
          <div key={t.key} role="presentation" data-paneel-tab={soort === "paneel" ? t.key : undefined}
            data-weergave-tab={soort === "weergave" ? t.key : undefined} data-actief={gekozen || undefined}
            className={`flex max-w-[14rem] shrink-0 items-center rounded-knop-xs border ${gekozen ? "border-lint/40 bg-surface text-lint" : "border-transparent text-muted hover:bg-surface hover:text-lint"}`}>
            <button ref={(el) => { refs.current[t.key] = el; }} type="button" role="tab" aria-selected={gekozen}
              tabIndex={gekozen || (!active && i === 0) ? 0 : -1} title={t.title ?? t.label}
              onClick={() => onChange(t.key)} onKeyDown={(e) => onKeyDown(e, i)}
              className="focus-ring flex min-h-7 min-w-0 items-center gap-1.5 rounded-knop-xs px-2 text-xs font-medium coarse:min-h-11">
              {t.icoon && <span aria-hidden className="shrink-0">{t.icoon}</span>}
              <span className="truncate">{t.label}</span>
            </button>
            {t.onSluit && (
              <button type="button" aria-label={`Sluit tab ${t.label}`} title={`Sluit tab ${t.label}`} onClick={t.onSluit} data-tab-sluiten
                className="focus-ring mr-0.5 inline-flex h-5 w-5 shrink-0 items-center justify-center rounded-knop-xs text-faint hover:bg-paper hover:text-lint coarse:h-11 coarse:w-11">
                <svg width="10" height="10" viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" aria-hidden><path d="M5 5l10 10M15 5L5 15" /></svg>
              </button>
            )}
          </div>
        );
      })}
    </div>
  );
}
