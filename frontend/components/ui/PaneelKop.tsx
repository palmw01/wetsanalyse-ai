"use client";

import { createContext, useCallback, useContext, useEffect, useLayoutEffect, useRef, useState } from "react";

import { NaarPagina } from "@/components/ui/Icoon";
import { MeerMenu, MenuLink } from "@/components/ui/MeerMenu";
import { PaneelKnop, actieVan, usePaneel } from "@/components/ui/Paneel";
import { knoppenVoor } from "@/lib/paneelBediening";
import { metVanuit } from "@/lib/terugNaarGesprek";

/** Het kruisje rechtsboven in een venster (`Dialog`, de rondleiding, het menu op een telefoon). Een paneel naast het
 *  gesprek heeft het niet: daar is sluiten een handeling van het paneel (`PaneelKnop`, `lib/paneelBediening.ts`). */
export function SluitKnop({ onSluit, label = "Sluiten", className = "" }: {
  onSluit: () => void;
  /** De voorleesnaam, als "Sluiten" niet genoeg zegt ("Instellingen sluiten"). */
  label?: string;
  className?: string;
}) {
  return (
    <button type="button" onClick={onSluit} aria-label={label}
      // `-mr-1` haalt de optische ruimte van het icoon weg, zodat het kruisje uitlijnt met de kantlijn.
      className={`focus-ring -mr-1 inline-flex shrink-0 items-center justify-center rounded-knop p-1.5 text-muted transition-colors hover:bg-surface hover:text-ink coarse:h-11 coarse:w-11 ${className}`}>
      <svg viewBox="0 0 20 20" className="h-5 w-5" fill="none" stroke="currentColor" strokeWidth="1.6" aria-hidden="true">
        <path d="M5 5l10 10M15 5L5 15" strokeLinecap="round" />
      </svg>
    </button>
  );
}

/** Wat de inhoud van een paneel zelf aan de kop toevoegt: zijn stand en zijn handelingen in het menu ⋯. */
export interface KopVulling {
  status?: React.ReactNode;
  hoofdactie?: React.ReactNode;
  menu?: (sluit: () => void) => React.ReactNode;
}

const ZetVulling = createContext<((v: KopVulling | null) => void) | null>(null);
const Vulling = createContext<KopVulling | null>(null);

/** Om de schil van een paneel: de inhoud laadt zijn eigen object (een werkgebied, een begrip) en kent dus zijn stand en
 *  zijn menu; via deze context komen die in de ene kop van de schil, in plaats van in een eigen rij in de inhoud. */
export function PaneelKopVuller({ children }: { children: React.ReactNode }) {
  const [vulling, setVulling] = useState<KopVulling | null>(null);
  return <ZetVulling.Provider value={setVulling}><Vulling.Provider value={vulling}>{children}</Vulling.Provider></ZetVulling.Provider>;
}

/** Zet de stand en het menu van de inhoud in de paneelkop. `sleutel` zegt wanneer de status opnieuw moet (de status en
 *  de revisie); het menu leest altijd de laatste render, dus een handeling werkt nooit op een oude stand. `null`: niets
 *  (een oude versie, een verwijderd object). Buiten een `PaneelKopVuller` (een pagina) doet de haak niets. */
export function usePaneelKopVulling(vulling: KopVulling | null, sleutel: string) {
  const zet = useContext(ZetVulling);
  const laatste = useRef(vulling);
  useLayoutEffect(() => { laatste.current = vulling; });
  const menu = useCallback((sluit: () => void) => laatste.current?.menu?.(sluit), []);
  const heeftMenu = Boolean(vulling?.menu);
  const leeg = vulling === null;
  useEffect(() => {
    const v = laatste.current;
    zet?.(leeg || !v ? null : { status: v.status, hoofdactie: v.hoofdactie, menu: heeftMenu ? menu : undefined });
  }, [zet, sleutel, heeftMenu, leeg, menu]);
  useEffect(() => () => zet?.(null), [zet]);
}

/** De kop van elk paneel naast het gesprek (spoor I4; één schil voor elk artefact sinds 4 nov 2026; één vaste indeling
 *  sinds 8 nov 2026). Hoogstens twee rijen, nooit wrappend:
 *
 *  1. soort en titel (afgekapt), en rechtsboven het kopgereedschap: ⋯ en dan de knoppen van de plek (`usePaneel()` en
 *     `knoppenVoor` in `lib/paneelBediening.ts`: *Vergroten* of *Verkleinen*, *Paneel inklappen*, *Sluiten*), altijd in
 *     die volgorde. **De kop is de enige bediening van het paneel** (besluit gebruiker 23 nov 2026): een paneel zegt wat
 *     het is, de plek bepaalt de knoppen. Op een pagina staat alleen ⋯. De pagina zelf (een link om te delen) staat als
 *     *Openen als pagina* bovenaan in ⋯, met het gesprek erbij (`?vanuit=`, `lib/terugNaarGesprek.ts`);
 *  2. alleen als er iets is: de status links en één hoofdactie rechts (de annotatie: *Annotatie afronden*).
 *
 *  Kopiëren en exporteren, verwijderen en de zeldzame bewerkingen van een soort staan in het menu ⋯ (eerst wat de
 *  schil geeft, dan wat de inhoud via `usePaneelKopVulling` toevoegt; *Verwijderen* onderaan): in een paneel van 360 px
 *  passen ze niet naast de status. Twee slots onder de kop: `onder` (één regel: de reeks of de versie) en `balk` (de
 *  weergaven van de inhoud: Tekst | Graaf), zodat geen paneel een eigen kop of sluitknop nodig heeft. `app/paneelKop.test.ts` bewaakt het. */
export function PaneelKop({ soort, titel, pagina, status, hoofdactie, vraag, menu, onder, balk }: {
  /** De soort, klein boven de titel; weg als de titel de soortnaam al is (`artefactKop` in `lib/artefact.ts`). */
  soort?: string;
  titel: string;
  /** Waar *Openen als pagina* (in ⋯) heen gaat; zonder geen regel (de rondleiding, een overzicht). */
  pagina?: string;
  /** De stand, links op de tweede rij: een `StatusLabel`, eventueel met een meta ("revisie 3"). */
  status?: React.ReactNode;
  /** Hoogstens één handeling, rechts op de tweede rij (`knopKlasse("secondary", "xs")`). */
  hoofdactie?: React.ReactNode;
  /** *Vraag Lex* over wat het paneel toont (`VraagLexKnop`, ontdubbelen PR 5): op de tweede rij, vóór de hoofdactie. */
  vraag?: React.ReactNode;
  /** De regels van het menu ⋯ (`MenuKnop`, `ExportRegels`, `MenuVerwijder`). */
  menu?: (sluit: () => void) => React.ReactNode;
  /** Eén regel onder de kop: waar je bent in een reeks of in de versies. */
  onder?: React.ReactNode;
  /** De weergaven van de inhoud (de annotatie: Tekst | Graaf). */
  balk?: React.ReactNode;
}) {
  const vulling = useContext(Vulling);
  const stand = status ?? vulling?.status;
  const actie = hoofdactie ?? vulling?.hoofdactie;
  const eigenMenu = vulling?.menu;
  const heeftMenu = Boolean(pagina || menu || eigenMenu);
  const paneel = usePaneel();
  const { tabs, gesprekId: gesprek } = paneel;
  return (
    <div data-paneel-kop className="shrink-0">
    {tabs && <div data-paneel-tabs className="flex border-b border-line px-3 py-1.5">{tabs}</div>}
    <div data-tour="artefact-acties" className="flex flex-col gap-2 border-b border-line px-5 py-3.5 pt-[max(0.875rem,env(safe-area-inset-top))]">
      <div data-kop-rij="titel" className="flex items-start gap-3">
        <div className="min-w-0 flex-1">
          {soort && <p className="truncate text-xs text-muted">{soort}</p>}
          <h2 className="truncate font-display text-base font-semibold text-lint">{titel}</h2>
        </div>
        <div data-kop-gereedschap className="flex shrink-0 items-center gap-1.5">
          {heeftMenu && (
            <MeerMenu label={`Meer: ${titel}`} maat="sm" breedte="w-64">
              {(sluit) => <>
                {pagina && (
                  <MenuLink href={metVanuit(pagina, gesprek)} icoon={<NaarPagina />} data-naar-pagina
                    title={gesprek ? "Je verlaat het gesprek; Terug naar het gesprek brengt je hier terug" : undefined}>
                    Openen als pagina
                  </MenuLink>
                )}
                {menu?.(sluit)}{eigenMenu?.(sluit)}
              </>}
            </MeerMenu>
          )}
          {knoppenVoor(paneel.plek, { kanSluiten: !!paneel.sluiten }).map((h) => (
            <PaneelKnop key={h} handeling={h} onClick={actieVan(h, paneel)} />
          ))}
        </div>
      </div>
      {(stand || actie || vraag) && (
        <div data-kop-rij="stand" className="flex min-h-[24px] items-center justify-between gap-3">
          <div className="flex min-w-0 items-center gap-2">{stand}</div>
          {(actie || vraag) && <div className="flex shrink-0 items-center gap-2">{vraag}{actie}</div>}
        </div>
      )}
    </div>
    {onder}
    {balk}
    </div>
  );
}
