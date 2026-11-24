"use client";

import { useEffect, useRef, useState, type ReactNode } from "react";

import { Scheiding } from "@/components/ui/Scheiding";
import { leesOpslag, schrijfOpslag } from "@/lib/opslag";
import { AANDEEL_MAX, AANDEEL_MIN, AANDEEL_STANDAARD, OPSLAG_AANDEEL, aandeelNaToets, aandeelUitPositie, leesAandeel } from "@/lib/tekstEnLijst";

/** Een wettekst met de lijst die erover gaat, elk met een eigen scroll (de annotatie: de tekst met de markeringen, en de
 *  kaartjes). Smal onder elkaar, breed genoeg naast elkaar: links de tekst over de volle hoogte, rechts de lijst, met een
 *  versleepbare scheiding ertussen (`Scheiding`; de verdeling bewaart de browser). Wat "breed genoeg" is, beslist een
 *  containerquery op dit blok zelf (`lib/tekstEnLijst.ts`, de CSS in `app/globals.css`), niet de schermbreedte of de
 *  stand van het paneel. Zo krijgt een vergroot paneel, een breed gesleept paneel en een pagina twee kolommen, en een
 *  smal paneel niet.
 *
 *  De koppeling tussen tekst en lijst (een markering kiezen licht het kaartje uit, en andersom) blijft werken: elk
 *  scrollt in zijn eigen kolom naar wat gekozen is (`WettekstBlok`, `ReviewQueue`). */
export function TekstEnLijst({ tekst, lijst, standaard = AANDEEL_STANDAARD, opslag = OPSLAG_AANDEEL,
  label = "Verdeling tussen tekst en lijst" }: {
  /** Links (breed) of bovenin (smal). */
  tekst: ReactNode;
  /** Rechts (breed) of eronder (smal). */
  lijst: ReactNode;
  /** Het deel voor links, standaard (procent, binnen `AANDEEL_MIN`–`AANDEEL_MAX`). Het diagram van 2c krijgt meer dan een
   *  wettekst: een tekening wordt bij een smalle kolom onleesbaar klein. */
  standaard?: number;
  /** Waar de browser de eigen verdeling bewaart: een plek met een andere standaard heeft haar eigen voorkeur. */
  opslag?: string;
  /** Hoe de scheiding heet voor een schermlezer. */
  label?: string;
}) {
  const ref = useRef<HTMLDivElement>(null);
  const [aandeel, setAandeel] = useState(standaard);
  // Pas na het mounten: de server kent geen opslag.
  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setAandeel(leesOpslag(opslag, leesAandeel) ?? standaard);
  }, [opslag, standaard]);
  const zet = (a: number) => {
    setAandeel(a);
    schrijfOpslag(opslag, a === standaard ? undefined : a);
  };
  const uitPositie = (x: number) => {
    const r = ref.current?.getBoundingClientRect();
    return r ? aandeelUitPositie(x, r.left, r.width) : aandeel;
  };

  return (
    <div className="tekst-en-lijst-schil">
      <div ref={ref} className="tekst-en-lijst" data-tekst-en-lijst style={{ "--tekst-aandeel": `${aandeel}%` } as React.CSSProperties}>
        <div data-tekst-kolom>{tekst}</div>
        {/* Alleen naast elkaar te zien (de CSS); onder elkaar is er niets te verdelen. */}
        <Scheiding label={label} waarde={aandeel} min={AANDEEL_MIN} max={AANDEEL_MAX}
          data-tekst-scheiding onSleep={(x) => setAandeel(uitPositie(x))} onLos={(x) => zet(uitPositie(x))}
          onToets={(toets) => {
            const nieuw = aandeelNaToets(aandeel, toets);
            if (nieuw === null) return false;
            zet(nieuw);
            return true;
          }}
          onStandaard={() => zet(standaard)} />
        <div data-lijst-kolom>{lijst}</div>
      </div>
    </div>
  );
}
