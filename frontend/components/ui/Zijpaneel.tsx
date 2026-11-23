"use client";

import { useCallback, useEffect, useMemo, useRef, useState, type ReactNode } from "react";

import { PaneelContext, PaneelKnop, actieVan, type PaneelOmgeving } from "@/components/ui/Paneel";
import { Scheiding } from "@/components/ui/Scheiding";
import { leesOpslag, schrijfOpslag } from "@/lib/opslag";
import { OPSLAG_WEERGAVE, knoppenVoor, leesWeergave, plekVanWeergave, volgende, type Gebeurtenis, type Weergave } from "@/lib/paneelBediening";
import { OPSLAG_BREEDTE, begrens, grenzen, leesBreedte, naToets } from "@/lib/zijpaneel";

/** Het paneel naast het gesprek op een breed scherm (het bronvenster, PR 3a; naar het voorbeeld van Claude Code): één
 *  vaste kolom rechts, met een scheiding om de breedte te verslepen. Onder 800 px is er geen zijpaneel maar een sheet
 *  (`Dialog side`); dit component staat daar niet.
 *
 *  **Eén stand** (`Weergave` in `lib/paneelBediening.ts`: normaal, vergroot of ingeklapt), met de overgangen daar, en per
 *  browser bewaard (`lex.paneel.weergave`, telt alleen bij een herstelde inhoud). **Geen eigen bediening**: het zijpaneel
 *  vult de `PaneelContext`, en de kop van wat er open is (`PaneelKop`) tekent de knoppen (besluit gebruiker 23 nov 2026).
 *  Ingeklapt is het een strook met dezelfde knoppen (`PaneelKnop`). Boven de inhoud staat alleen een tabrij, en alleen bij
 *  twee of meer open items (`tabs`).
 *
 *  De inhoud blijft gemount als het paneel ingeklapt is: wat je half had gelezen of ingevuld, staat er nog als je
 *  uitklapt. Escape verkleint een vergroot paneel eerst. Geen sneltoetsen: alleen de pijltjes op de scheiding als die
 *  de focus heeft, en Escape. */
export function Zijpaneel({ sleutel, hersteld = false, vast = false, tabs, inklapSignaal = 0, omgeving, children }: {
  /** Wat er openstaat. Iets anders openen is een expliciete handeling: dan klapt het paneel uit, ook als het ingeklapt was
   *  – anders gebeurt er na een klik op een ingang zichtbaar niets. */
  sleutel: string;
  /** De inhoud kwam terug uit de opslag (herladen), niet uit een klik: dan geldt de bewaarde stand. */
  hersteld?: boolean;
  /** In de rondleiding: altijd normaal, niets bewaard (de stappen wijzen in het paneel). */
  vast?: boolean;
  /** De tabrij boven de inhoud; de werkplek geeft hem pas bij twee of meer open items. */
  tabs?: ReactNode;
  /** Verhoogt bij Escape in de inhoud (verbergen, niet sluiten). Een teller, omdat de inhoud dit paneel niet kent. */
  inklapSignaal?: number;
  /** Wat de werkplek toevoegt: sluiten en het gesprek. */
  omgeving: Pick<PaneelOmgeving, "sluiten" | "gesprekId">;
  children: ReactNode;
}) {
  const ref = useRef<HTMLDivElement>(null);
  const [breedte, setBreedte] = useState<number>();
  const [stand, setStand] = useState<Weergave>("normaal");
  // De breedte van de werkplek en van het paneel zelf, gemeten: tijdens het renderen lezen we geen refs.
  const [maat, setMaat] = useState({ container: 1280, paneel: 544 });

  // Elke overgang via `volgende`, en bewaard: na herladen of terug van een pagina staat het paneel zoals je het verliet.
  const ga = useCallback((g: Gebeurtenis) => {
    if (vast) return;
    setStand((s) => {
      const nieuw = volgende(s, g);
      schrijfOpslag(OPSLAG_WEERGAVE, nieuw === "normaal" ? undefined : nieuw);
      return nieuw;
    });
  }, [vast]);

  // Pas na het mounten: de server kent geen opslag.
  useEffect(() => {
    if (vast) return;
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setBreedte(leesOpslag(OPSLAG_BREEDTE, leesBreedte));
    if (hersteld) setStand(leesOpslag(OPSLAG_WEERGAVE, leesWeergave) ?? "normaal");
    // Alleen bij het mounten: daarna beslist de kijker zelf.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [vast]);

  // Escape in de inhoud: verbergen, niet sluiten.
  const vorigSignaal = useRef(inklapSignaal);
  useEffect(() => {
    if (vorigSignaal.current === inklapSignaal) return;
    vorigSignaal.current = inklapSignaal;
    ga("inklappen");
  }, [inklapSignaal, ga]);

  // Iets anders geopend: uitklappen (de eerste keer telt het mounten al als opening).
  const vorige = useRef(sleutel);
  useEffect(() => {
    if (vorige.current === sleutel) return;
    vorige.current = sleutel;
    ga("nieuw");
  }, [sleutel, ga]);

  // Escape verkleint eerst, vóór het paneel zelf hem ziet (dat sluit anders): de capture-fase op `document`. Behalve
  // als de inhoud Escape zelf afpelt (`claimEscape`): die verkleint op haar eigen beurt.
  const escapeGeclaimd = useRef(false);
  const vergroot = stand === "vergroot";
  useEffect(() => {
    if (!vergroot) return;
    const opToets = (e: KeyboardEvent) => {
      if (e.key !== "Escape" || escapeGeclaimd.current) return;
      e.stopPropagation();
      ga("verkleinen");
    };
    document.addEventListener("keydown", opToets, true);
    return () => document.removeEventListener("keydown", opToets, true);
  }, [vergroot, ga]);

  useEffect(() => {
    const el = ref.current;
    const ouder = el?.parentElement;
    if (!el || !ouder) return;
    const meet = () => setMaat({ container: ouder.clientWidth, paneel: el.offsetWidth });
    meet();
    const waarnemer = new ResizeObserver(meet);
    waarnemer.observe(ouder);
    waarnemer.observe(el);
    return () => waarnemer.disconnect();
  }, []);

  const container = () => ref.current?.parentElement?.clientWidth ?? maat.container;
  const huidig = () => breedte ?? ref.current?.offsetWidth ?? maat.paneel;
  const rechts = () => (ref.current?.parentElement ?? document.body).getBoundingClientRect().right;
  const zet = (b: number | undefined) => {
    setBreedte(b);
    if (!vast) schrijfOpslag(OPSLAG_BREEDTE, b);
  };

  const plek = plekVanWeergave(stand, vast);
  const { sluiten, gesprekId } = omgeving;
  const context = useMemo<PaneelOmgeving>(() => ({
    plek, sluiten, gesprekId,
    zetVergroot: vast ? undefined : (v: boolean) => ga(v ? "vergroten" : "verkleinen"),
    inklappen: vast ? undefined : () => ga("inklappen"),
    uitklappen: vast ? undefined : () => ga("uitklappen"),
    claimEscape: (ja: boolean) => { escapeGeclaimd.current = ja; },
  }), [plek, sluiten, gesprekId, vast, ga]);
  const open = stand !== "ingeklapt";
  const { min, max } = grenzen(maat.container);
  const stijl = vergroot || !open ? undefined : breedte ? { width: `${breedte}px` } : undefined;
  const klasse = vergroot
    ? "absolute inset-0 z-30 flex flex-col bg-paper shadow-kaart"
    : !open ? "flex w-10 shrink-0 flex-col items-center gap-2 border-l border-line bg-paper py-2"
      : `relative flex shrink-0 flex-col ${breedte ? "" : "w-[min(34rem,46%)]"}`;

  return (
    <div ref={ref} data-zijpaneel={vergroot ? "vergroot" : open ? "open" : "ingeklapt"}
      {...(!open ? { "data-paneel-ingeklapt": "" } : {})} style={stijl} className={klasse}>
      {/* Ingeklapt is de kop niet te zien: de strook draagt dezelfde knoppen. */}
      {!open && knoppenVoor(plek, { kanSluiten: !!sluiten }).map((h) => <PaneelKnop key={h} handeling={h} onClick={actieVan(h, { plek, sluiten, uitklappen: () => ga("uitklappen") })} />)}
      {open && !vergroot && (
        // De scheiding (`Scheiding`): slepen, of de pijltjes als hij de focus heeft. Dubbelklik zet de standaard terug.
        <Scheiding label="Breedte van het paneel" waarde={breedte ?? maat.paneel} min={min} max={max} data-paneel-scheiding
          onSleep={(x) => setBreedte(begrens(rechts() - x, container()))}
          onLos={(x) => zet(begrens(rechts() - x, container()))}
          onToets={(toets) => {
            const nieuw = naToets(huidig(), toets, container());
            if (nieuw === null) return false;
            zet(nieuw);
            return true;
          }}
          onStandaard={() => zet(undefined)} className="absolute inset-y-0 -left-1 z-10 w-2" />
      )}
      <div className={open ? "flex min-h-0 flex-1 flex-col" : "hidden"}>
        {tabs && (
          <div data-paneel-tabs className="flex shrink-0 items-center border-b border-l border-line bg-paper px-2 py-1">{tabs}</div>
        )}
        <div className="flex min-h-0 flex-1 flex-col"><PaneelContext.Provider value={context}>{children}</PaneelContext.Provider></div>
      </div>
    </div>
  );
}
