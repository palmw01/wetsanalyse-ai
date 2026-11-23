"use client";

import { createContext, useCallback, useContext, useEffect, useLayoutEffect, useRef, useState } from "react";

import { IcoonKnop } from "@/components/ui/Button";
import { NaarPagina } from "@/components/ui/Icoon";
import { MeerMenu, MenuLink } from "@/components/ui/MeerMenu";
import { ZijpaneelContext } from "@/components/ui/Zijpaneel";
import { metVanuit } from "@/lib/terugNaarGesprek";

/** Het kruisje rechtsboven in elk paneel en venster: één icoon, één lijndikte, één plek. */
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
 *  1. soort en titel (afgekapt), en rechtsboven het kopgereedschap: ⋯, dan in het zijpaneel *Vergroten* of *Verkleinen*
 *     en *Inklappen* (`ZijpaneelContext.bediening`), en ✕ – altijd in die volgorde en op die plek. **De kop is de enige
 *     bediening van het paneel** (besluit gebruiker 23 nov 2026): er is geen balk erboven, en geen knop naar een pagina
 *     die op *Vergroten* lijkt. Vergroten is de volle weergave binnen de werkplek; de pagina zelf (een link om te delen)
 *     staat als *Openen als pagina* bovenaan in ⋯, met het gesprek erbij (`?vanuit=`, `lib/terugNaarGesprek.ts`);
 *  2. alleen als er iets is: de status links en één hoofdactie rechts (de annotatie: *Annotatie afronden*).
 *
 *  Kopiëren en exporteren, verwijderen en de zeldzame bewerkingen van een soort staan in het menu ⋯ (eerst wat de
 *  schil geeft, dan wat de inhoud via `usePaneelKopVulling` toevoegt; *Verwijderen* onderaan): in een paneel van 360 px
 *  passen ze niet naast de status. Twee slots onder de kop: `onder` (één regel: de reeks of de versie) en `balk` (de
 *  weergaven van de inhoud: Tekst | Graaf), zodat geen paneel een eigen kop of sluitknop nodig heeft. `app/paneelKop.test.ts` bewaakt het. */
/** De tabs van het paneel naast het gesprek, op een telefoon (het bronvenster, PR 3b): daar is het paneel een sheet,
 *  dus de tabs staan boven de kop van wat er open is. Alleen de werkplek geeft ze, en pas bij twee of meer. */
export const PaneelTabsContext = createContext<React.ReactNode>(null);

/** Het gesprek waarin het paneel openstaat (de werkplek geeft het). *Openen als pagina* neemt het mee als
 *  `?vanuit=`, zodat de pagina een weg terug naar het gesprek heeft (`lib/terugNaarGesprek.ts`). */
export const PaneelGesprekContext = createContext<string | null>(null);

export function PaneelKop({ soort, titel, pagina, status, hoofdactie, vraag, menu, onSluit, onder, balk }: {
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
  const heeftMenu = Boolean(pagina || menu || eigenMenu);
  const zp = useContext(ZijpaneelContext);
  const bediening = zp?.bediening;
  const tabs = useContext(PaneelTabsContext);
  const gesprek = useContext(PaneelGesprekContext);
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
          {zp && bediening && <>
            <IcoonKnop size="sm" aria-label={zp.vergroot ? "Verkleinen" : "Vergroten"} aria-pressed={zp.vergroot}
              title={zp.vergroot ? "Verkleinen: terug naast het gesprek" : "Vergroten: de volle weergave"}
              onClick={() => zp.zetVergroot(!zp.vergroot)} data-paneel-vergroten>
              {zp.vergroot ? <Verkleinen /> : <Vergroten />}
            </IcoonKnop>
            <IcoonKnop size="sm" aria-label={`${bediening.label} inklappen`} title={`${bediening.label} inklappen`}
              onClick={bediening.inklappen} data-paneel-inklappen>
              <Inklappen />
            </IcoonKnop>
          </>}
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

const SVG = { width: 16, height: 16, viewBox: "0 0 20 20", fill: "none", stroke: "currentColor", strokeWidth: 1.6,
  strokeLinecap: "round" as const, strokeLinejoin: "round" as const, "aria-hidden": true };
function Vergroten() {
  return <svg {...SVG}><path d="M12 3h5v5M8 17H3v-5M17 3l-6 6M3 17l6-6" /></svg>;
}
function Verkleinen() {
  return <svg {...SVG}><path d="M16 9h-5V4M4 11h5v5M11 9l6-6M9 11l-6 6" /></svg>;
}
function Inklappen() {
  return <svg {...SVG}><path d="M5 5l5 5-5 5M11 5l5 5-5 5" /></svg>;
}
