"use client";

import Link from "next/link";
import { createContext, useCallback, useContext, useEffect, useLayoutEffect, useRef, useState } from "react";

import { icoonKnopKlasse } from "@/components/ui/Button";
import { NaarPagina } from "@/components/ui/Icoon";
import { MeerMenu } from "@/components/ui/MeerMenu";

/** Het kruisje rechtsboven in elk paneel en venster: één icoon, één lijndikte, één plek. */
export function SluitKnop({ onSluit, className = "" }: { onSluit: () => void; className?: string }) {
  return (
    <button type="button" onClick={onSluit} aria-label="Sluiten"
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
 *  1. soort en titel (afgekapt), en rechtsboven het kopgereedschap: ↗ *Open volledige pagina*, ⋯ en ✕ – altijd in die
 *     volgorde en op die plek, zodat sluiten en de pagina nooit wandelen;
 *  2. alleen als er iets is: de status links en één hoofdactie rechts (de annotatie: *Annotatie afronden*).
 *
 *  Kopiëren en exporteren, verwijderen en de zeldzame bewerkingen van een soort staan in het menu ⋯ (eerst wat de
 *  schil geeft, dan wat de inhoud via `usePaneelKopVulling` toevoegt; *Verwijderen* onderaan): in een paneel van 360 px
 *  passen ze niet naast de status. Twee slots onder de kop: `onder` (één regel: de reeks of de versie) en `balk` (tabs
 *  en *Vergroten*), zodat geen paneel een eigen kop of sluitknop nodig heeft. `app/paneelKop.test.ts` bewaakt het. */
/** De tabs van het paneel naast het gesprek, op een telefoon (het bronvenster, PR 3b): daar is het paneel een sheet en
 *  staat er geen zijpaneel met een balk, dus de tabs staan boven de kop van wat er open is. Alleen de werkplek geeft ze. */
export const PaneelTabsContext = createContext<React.ReactNode>(null);

export function PaneelKop({ soort, titel, pagina, status, hoofdactie, vraag, menu, onSluit, onder, balk }: {
  /** De soort, klein boven de titel; weg als de titel de soortnaam al is (`artefactKop` in `lib/artefact.ts`). */
  soort?: string;
  titel: string;
  /** Waar *Open volledige pagina* heen gaat; zonder geen knop (de rondleiding, een overzicht). */
  pagina?: string;
  /** De stand, links op de tweede rij: een `StatusLabel`, eventueel met een meta ("revisie 3"). */
  status?: React.ReactNode;
  /** Hoogstens één handeling, rechts op de tweede rij (`knopKlasse("secondary", "xs")`). */
  hoofdactie?: React.ReactNode;
  /** *Vraag Lex* over wat het paneel toont (`VraagLexKnop`, ontdubbelen PR 5): op de tweede rij, vóór de hoofdactie. */
  vraag?: React.ReactNode;
  /** De regels van het menu ⋯ (`MenuKnop`, `ExportRegels`, `MenuVerwijder`). */
  menu?: (sluit: () => void) => React.ReactNode;
  onSluit?: () => void;
  /** Eén regel onder de kop: waar je bent in een reeks of in de versies. */
  onder?: React.ReactNode;
  /** Tabs en weergaveknoppen (de annotatie: Tekst | Graaf, *Vergroten*). */
  balk?: React.ReactNode;
}) {
  const vulling = useContext(Vulling);
  const stand = status ?? vulling?.status;
  const actie = hoofdactie ?? vulling?.hoofdactie;
  const eigenMenu = vulling?.menu;
  const heeftMenu = Boolean(menu || eigenMenu);
  const tabs = useContext(PaneelTabsContext);
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
          {pagina && (
            <Link href={pagina} aria-label="Open volledige pagina" title="Open volledige pagina" data-naar-pagina
              className={icoonKnopKlasse("sm")}>
              <NaarPagina />
            </Link>
          )}
          {heeftMenu && (
            <MeerMenu label={`Meer: ${titel}`} maat="sm" breedte="w-64">
              {(sluit) => <>{menu?.(sluit)}{eigenMenu?.(sluit)}</>}
            </MeerMenu>
          )}
          {onSluit && <SluitKnop onSluit={onSluit} />}
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
