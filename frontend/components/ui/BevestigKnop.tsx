"use client";

import { useEffect, useRef, useState } from "react";

/** Wat er staat terwijl de handeling loopt. Een woord en geen icoon: de knop is elders in de app
 *  soms een klein icoontje van 14px, en daar past geen draaiende ring in zonder de rij te laten
 *  verspringen. */
const BEZIG_TEKST = "Bezig…";

/** Een knop die pas bij de tweede klik uitvoert.
 *
 *  Eén idioom voor "weet je het zeker" in de hele app. Het artefact deed dit al zo (× → "Wissen?");
 *  daarbuiten stond een native `window.confirm`, en dat is een systeemvenster in systeemtaal midden
 *  in een applicatie met een eigen vormtaal – bovendien niet te stylen, niet te testen en in sommige
 *  contexten geblokkeerd.
 *
 *  Scherp gezet ontwapent hij vanzelf: na een paar seconden, bij verlies van focus, of met Escape.
 *  Een knop die scherp blijft staan is een val – precies bij de handelingen waar dat het duurst is.
 *  Maar hij mag ook niet aflopen terwijl je de vraag leest: op vier seconden was de "tweede" klik
 *  in de praktijk vaak weer de eerste, en dan lijkt een klik verdwenen. Vandaar acht seconden, en
 *  de klok loopt niet zolang de aanwijzer op de knop staat.
 *
 *  **De handeling zelf duurt ook tijd, en dat hoort te zien te zijn.** `onBevestig` mag een promise
 *  teruggeven; zolang die loopt staat de knop op `Bezig…` en is hij uitgeschakeld. Zonder dat was er
 *  tussen de klik en het resultaat niets te zien – niet te onderscheiden van een klik die niet is
 *  aangekomen – en kon dezelfde handeling er twee keer uit.
 */
export function BevestigKnop({
  children,
  bevestigTekst,
  onBevestig,
  ariaLabel,
  titel,
  className = "",
  bevestigClassName = "",
  disabled,
  wachtMs = 8000,
}: {
  /** Wat er in rust staat: tekst of een icoon. */
  children: React.ReactNode;
  /** Wat er staat zodra hij scherp staat, bv. "Verwijderen?". */
  bevestigTekst: string;
  onBevestig: () => void | Promise<void>;
  ariaLabel?: string;
  titel?: string;
  className?: string;
  /** Extra klassen voor de scherpe stand, zodat die er anders uitziet dan de rust-stand. */
  bevestigClassName?: string;
  disabled?: boolean;
  /** Hoe lang hij scherp blijft staan zodra de aanwijzer eraf is. */
  wachtMs?: number;
}) {
  const [scherp, setScherp] = useState(false);
  const [bezig, setBezig] = useState(false);
  const [hover, setHover] = useState(false);
  const knopRef = useRef<HTMLButtonElement>(null);
  // Na het afronden van de handeling kan de knop al weg zijn (de rij die je verwijderde). `setState`
  // op een verdwenen component is geen fout meer in React 19, maar de vlag houdt de bedoeling
  // expliciet: alleen de nog levende knop keert terug naar zijn ruststand.
  const levendRef = useRef(true);
  useEffect(() => () => { levendRef.current = false; }, []);

  useEffect(() => {
    if (!scherp || hover) return;
    const id = window.setTimeout(() => setScherp(false), wachtMs);
    const opEsc = (e: KeyboardEvent) => {
      if (e.key === "Escape") setScherp(false);
    };
    window.addEventListener("keydown", opEsc);
    return () => {
      window.clearTimeout(id);
      window.removeEventListener("keydown", opEsc);
    };
  }, [scherp, hover, wachtMs]);

  return (
    <button
      ref={knopRef}
      type="button"
      disabled={disabled || bezig}
      aria-busy={bezig || undefined}
      aria-label={bezig ? "Bezig" : scherp ? bevestigTekst : ariaLabel}
      title={bezig ? "Bezig" : scherp ? bevestigTekst : titel}
      onMouseEnter={() => setHover(true)}
      onMouseLeave={() => setHover(false)}
      onBlur={() => setScherp(false)}
      onClick={async (e) => {
        e.stopPropagation();
        if (bezig) return;
        if (!scherp) {
          setScherp(true);
          return;
        }
        setScherp(false);
        setBezig(true);
        try {
          await onBevestig();
        } finally {
          if (levendRef.current) setBezig(false);
        }
      }}
      className={scherp ? `${className} ${bevestigClassName}` : className}
    >
      {bezig ? BEZIG_TEKST : scherp ? bevestigTekst : children}
    </button>
  );
}
