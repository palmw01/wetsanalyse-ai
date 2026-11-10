"use client";

import { createContext, useEffect, useMemo, useRef, useState, type ReactNode } from "react";

import { IcoonKnop } from "@/components/ui/Button";
import { leesOpslag, schrijfOpslag } from "@/lib/opslag";
import { OPSLAG_BREEDTE, OPSLAG_INGEKLAPT, begrens, grenzen, leesBreedte, naToets } from "@/lib/zijpaneel";

/** Voor de inhoud van het zijpaneel: er is één *Vergroten*, die van het paneel. De graaf leest `vergroot` in plaats van
 *  een eigen knop, en een inhoud die Escape zelf laag voor laag afpelt (de graaf: lagen → selectie → verkleinen →
 *  sluiten) claimt Escape, zodat het paneel hem niet eerst wegvangt. Buiten het zijpaneel (de sheet, de
 *  annotatiepagina) is er geen context en houdt de graaf zijn eigen knop. */
export const ZijpaneelContext = createContext<{
  vergroot: boolean;
  zetVergroot: (v: boolean) => void;
  claimEscape: (ja: boolean) => void;
} | null>(null);

/** Het paneel naast het gesprek op een breed scherm (het bronvenster, PR 3a; naar het voorbeeld van Claude Code): één
 *  vaste kolom rechts, met een scheiding om de breedte te verslepen, *Inklappen* tot een strook en *Vergroten* over het
 *  gesprek heen. De breedte en de ingeklapte stand bewaart de browser (`lib/opslag.ts`). Onder 800 px is er geen
 *  zijpaneel maar een sheet (`Dialog side`); dit component staat daar niet.
 *
 *  De inhoud blijft gemount als het paneel ingeklapt is: wat je half had gelezen of ingevuld, staat er nog als je
 *  uitklapt. Escape verkleint een vergroot paneel eerst. Geen sneltoetsen: alleen de pijltjes op de scheiding als die
 *  de focus heeft, en Escape. */
export function Zijpaneel({ label, sleutel, hersteld = false, vast = false, balk, inklapSignaal = 0, children }: {
  /** Waar het paneel over gaat, voor de strook en de knoppen ("Bepaling", "Begrip"). */
  label: string;
  /** Wat er openstaat. Iets anders openen is een expliciete handeling: dan klapt het paneel uit, ook als het ingeklapt was
   *  – anders gebeurt er na een klik op een ingang zichtbaar niets. */
  sleutel: string;
  /** De inhoud kwam terug uit de opslag (herladen), niet uit een klik: dan geldt de bewaarde ingeklapte stand. */
  hersteld?: boolean;
  /** In de rondleiding: altijd uitgeklapt, niets bewaard (de stappen wijzen in het paneel). */
  vast?: boolean;
  /** Links in de balk boven de inhoud: de tabs van het paneel. */
  balk?: ReactNode;
  /** Verhoogt als het paneel moet inklappen (Escape in de inhoud verbergt het paneel, het sluit geen tab). */
  inklapSignaal?: number;
  children: ReactNode;
}) {
  const ref = useRef<HTMLDivElement>(null);
  const [breedte, setBreedte] = useState<number>();
  const [ingeklapt, setIngeklapt] = useState(false);
  const [vergroot, setVergroot] = useState(false);
  const [sleept, setSleept] = useState(false);
  // De breedte van de werkplek en van het paneel zelf, gemeten: tijdens het renderen lezen we geen refs.
  const [maat, setMaat] = useState({ container: 1280, paneel: 544 });

  // Pas na het mounten: de server kent geen opslag.
  useEffect(() => {
    if (vast) return;
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setBreedte(leesOpslag(OPSLAG_BREEDTE, leesBreedte));
    if (hersteld) setIngeklapt(leesOpslag(OPSLAG_INGEKLAPT, (r) => (r === true ? true : undefined)) ?? false);
    // Alleen bij het mounten: daarna beslist de kijker zelf.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [vast]);

  // Escape in de inhoud: verbergen, niet sluiten. Een teller, omdat de inhoud dit paneel niet kent.
  const vorigSignaal = useRef(inklapSignaal);
  useEffect(() => {
    if (vorigSignaal.current === inklapSignaal) return;
    vorigSignaal.current = inklapSignaal;
    if (vast) return;
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setIngeklapt(true);
    setVergroot(false);
  }, [inklapSignaal, vast]);

  // Iets anders geopend: uitklappen (de eerste keer telt het mounten al als opening).
  const vorige = useRef(sleutel);
  useEffect(() => {
    if (vorige.current === sleutel) return;
    vorige.current = sleutel;
    setIngeklapt(false);
  }, [sleutel]);

  // Escape verkleint eerst, vóór het paneel zelf hem ziet (dat sluit anders): de capture-fase op `document`. Behalve
  // als de inhoud Escape zelf afpelt (`claimEscape`): die verkleint op haar eigen beurt.
  const escapeGeclaimd = useRef(false);
  useEffect(() => {
    if (!vergroot) return;
    const opToets = (e: KeyboardEvent) => {
      if (e.key !== "Escape" || escapeGeclaimd.current) return;
      e.stopPropagation();
      setVergroot(false);
    };
    document.addEventListener("keydown", opToets, true);
    return () => document.removeEventListener("keydown", opToets, true);
  }, [vergroot]);

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
  const zet = (b: number | undefined) => {
    setBreedte(b);
    if (!vast) schrijfOpslag(OPSLAG_BREEDTE, b);
  };
  const klap = (dicht: boolean) => {
    setIngeklapt(dicht);
    if (dicht) setVergroot(false);
    if (!vast) schrijfOpslag(OPSLAG_INGEKLAPT, dicht || undefined);
  };

  function begin(e: React.PointerEvent<HTMLDivElement>) {
    if (e.button !== 0) return;
    e.preventDefault();
    const doel = e.currentTarget;
    doel.setPointerCapture(e.pointerId);
    setSleept(true);
    const rechts = (ref.current?.parentElement ?? document.body).getBoundingClientRect().right;
    const beweeg = (ev: PointerEvent) => setBreedte(begrens(rechts - ev.clientX, container()));
    const los = (ev: PointerEvent) => {
      doel.removeEventListener("pointermove", beweeg);
      doel.removeEventListener("pointerup", los);
      doel.removeEventListener("pointercancel", los);
      setSleept(false);
      zet(begrens(rechts - ev.clientX, container()));
    };
    doel.addEventListener("pointermove", beweeg);
    doel.addEventListener("pointerup", los);
    doel.addEventListener("pointercancel", los);
  }

  const context = useMemo(() => ({
    vergroot, zetVergroot: setVergroot, claimEscape: (ja: boolean) => { escapeGeclaimd.current = ja; },
  }), [vergroot]);
  const open = vast || !ingeklapt;
  const { min, max } = grenzen(maat.container);
  const stijl = vergroot || !open ? undefined : breedte ? { width: `${breedte}px` } : undefined;
  const klasse = vergroot
    ? "absolute inset-0 z-30 flex flex-col bg-paper shadow-kaart"
    : !open ? "flex w-10 shrink-0 flex-col items-center gap-2 border-l border-line bg-paper py-2"
      : `relative flex shrink-0 flex-col ${breedte ? "" : "w-[min(34rem,46%)]"}`;

  return (
    <div ref={ref} data-zijpaneel={vergroot ? "vergroot" : open ? "open" : "ingeklapt"}
      {...(!open ? { "data-paneel-ingeklapt": "" } : {})} style={stijl} className={klasse}>
      {!open && (
        <IcoonKnop size="sm" aria-label={`${label} uitklappen`} title={`${label} uitklappen`} onClick={() => klap(false)}
          data-paneel-uitklappen>
          <PijlLinks />
        </IcoonKnop>
      )}
      {open && !vergroot && (
        // De scheiding: slepen, of de pijltjes als hij de focus heeft (WCAG 2.1.1). Dubbelklik zet de standaard terug.
        <div role="separator" aria-orientation="vertical" aria-label="Breedte van het paneel" tabIndex={0}
          aria-valuemin={min} aria-valuemax={max} aria-valuenow={Math.round(breedte ?? maat.paneel)} data-paneel-scheiding
          onPointerDown={begin} onDoubleClick={() => zet(undefined)}
          onKeyDown={(e) => {
            const nieuw = naToets(huidig(), e.key, container());
            if (nieuw === null) return;
            e.preventDefault();
            zet(nieuw);
          }}
          className={`focus-ring absolute inset-y-0 -left-1 z-10 w-2 cursor-col-resize touch-none rounded-sm hover:bg-lint/20 ${sleept ? "bg-lint/30" : ""}`} />
      )}
      <div className={open ? "flex min-h-0 flex-1 flex-col" : "hidden"}>
        {!vast && (
          <div data-zijpaneel-balk className="flex h-10 shrink-0 items-center justify-end gap-1.5 border-b border-l border-line bg-paper px-2">
            {balk}
            {!vergroot && (
              <IcoonKnop aria-label={`${label} inklappen`} title={`${label} inklappen`} onClick={() => klap(true)} data-paneel-inklappen>
                <PijlRechts />
              </IcoonKnop>
            )}
            <IcoonKnop aria-label={vergroot ? "Verkleinen" : "Vergroten"} title={vergroot ? "Terug naast het gesprek" : "Paneel vergroten"}
              aria-pressed={vergroot} onClick={() => setVergroot(!vergroot)} data-paneel-vergroten>
              {vergroot ? <Verkleinen /> : <Vergroten />}
            </IcoonKnop>
          </div>
        )}
        <div className="flex min-h-0 flex-1 flex-col"><ZijpaneelContext.Provider value={context}>{children}</ZijpaneelContext.Provider></div>
      </div>
    </div>
  );
}

const SVG = { width: 14, height: 14, viewBox: "0 0 20 20", fill: "none", stroke: "currentColor", strokeWidth: 1.6,
  strokeLinecap: "round" as const, strokeLinejoin: "round" as const, "aria-hidden": true };

function PijlRechts() {
  return <svg {...SVG}><path d="M5 5l5 5-5 5M11 5l5 5-5 5" /></svg>;
}
function PijlLinks() {
  return <svg {...SVG}><path d="M15 5l-5 5 5 5M9 5l-5 5 5 5" /></svg>;
}
function Vergroten() {
  return <svg {...SVG}><path d="M12 3h5v5M8 17H3v-5M17 3l-6 6M3 17l6-6" /></svg>;
}
function Verkleinen() {
  return <svg {...SVG}><path d="M16 9h-5V4M4 11h5v5M11 9l6-6M9 11l-6 6" /></svg>;
}
