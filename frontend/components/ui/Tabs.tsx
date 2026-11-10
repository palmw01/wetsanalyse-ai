"use client";

import { Fragment, useEffect, useId, useRef, type ReactNode } from "react";
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
export function Tabs({
  tabs,
  active,
  onChange,
  orientation = "horizontal",
  lazy = false,
  label = "Fasen",
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
}) {
  const base = useId();
  const tabRefs = useRef<Record<string, HTMLButtonElement | null>>({});
  const verticaal = orientation === "vertical";

  // Op een smal scherm is de tabkolom een rij die scrolt: de actieve tab hoort in beeld te staan. Eén keer scrollen is niet
  // genoeg: een telbadge of het webfont komt later en maakt een tab ervoor breder, en dat duwt de actieve tab weer uit beeld.
  useEffect(() => {
    if (!verticaal) return;
    const inBeeld = () => tabRefs.current[active]?.scrollIntoView?.({ block: "nearest", inline: "nearest" });
    inBeeld();
    if (typeof ResizeObserver === "undefined") return;
    const waarnemer = new ResizeObserver(inBeeld);
    for (const tab of Object.values(tabRefs.current)) if (tab) waarnemer.observe(tab);
    return () => waarnemer.disconnect();
  }, [active, verticaal]);

  function onKeyDown(e: React.KeyboardEvent, index: number) {
    const [vorige, volgende] = verticaal ? ["ArrowUp", "ArrowDown"] : ["ArrowLeft", "ArrowRight"];
    if (e.key !== volgende && e.key !== vorige) return;
    e.preventDefault();
    const next = e.key === volgende ? (index + 1) % tabs.length : (index - 1 + tabs.length) % tabs.length;
    const nextKey = tabs[next].key;
    onChange(nextKey);
    tabRefs.current[nextKey]?.focus();
  }

  return (
    <div className={verticaal ? "flex min-h-0 flex-1 flex-col sm:flex-row" : undefined}>
      <div
        role="tablist"
        aria-label={label}
        aria-orientation={verticaal ? "vertical" : undefined}
        className={
          verticaal
            ? // Mobiel: horizontaal scrollbare rij bovenin; vanaf sm een kolom links.
              "flex shrink-0 gap-1 overflow-x-auto overflow-y-hidden overscroll-x-contain border-b border-line px-2 py-2 sm:w-56 sm:flex-col sm:overflow-x-visible sm:overflow-y-auto sm:border-b-0 sm:border-r sm:px-2 sm:py-3"
            : // Een rij die op een smal scherm niet past scrolt, in plaats van tabs af te kappen.
              `${TABRIJ} print:hidden`
        }
      >
        {tabs.map((t, i) => {
          const selected = t.key === active;
          const basis =
            "min-h-[44px] text-sm font-medium transition-colors focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-lint";
          return (
            <Fragment key={t.key}>
            {verticaal && t.groep && (
              <span role="presentation" className="hidden px-3 pb-1 pt-3 text-xs font-medium text-faint first:pt-1 sm:block">
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
              tabIndex={selected ? 0 : -1}
              onClick={() => onChange(t.key)}
              onKeyDown={(e) => onKeyDown(e, i)}
              className={
                verticaal
                  ? `${basis} shrink-0 whitespace-nowrap rounded-kaart px-3 py-2 text-left sm:w-full ${
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
                  className="ml-1.5 inline-flex h-4 min-w-[1rem] items-center justify-center rounded-full bg-accent px-1 text-[0.6rem] font-bold leading-none text-paper"
                >
                  {t.badge > 99 ? "99+" : t.badge}
                </span>
              )}
            </button>
            </Fragment>
          );
        })}
      </div>
      {tabs.map((t) => {
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
      })}
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
export function TabRij({ tabs, active, onChange, label }: {
  tabs: readonly TabRijItem[];
  active?: string;
  onChange: (key: string) => void;
  label: string;
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
          <div key={t.key} role="presentation" data-paneel-tab={t.key} data-actief={gekozen || undefined}
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
