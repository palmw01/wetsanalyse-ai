"use client";

import { useEffect, useState } from "react";
import { begroeting } from "@/lib/begroeting";
import { Skyline } from "./Skyline";

/** De regel rechts in de header. Eén plek, zodat de tekst te vervangen is zonder de opmaak te raken. */
export const TAGLINE = "Samen voor een rechtvaardige en werkende samenleving";

/**
 * Header boven het gesprek.
 *
 * - **Volledig** in de lege werkplek: een begroeting bij het uur, de vraag waarmee Lex helpt en wat
 *   hij doet. Die zin is de korte kadering uit het IDENTITEIT-blok
 *   (`tools/graph-qa/agent/prompts.py`): hulpmiddel, de jurist beoordeelt – verander je de een,
 *   verander dan de ander mee.
 * - **Compact** zodra er een gesprek loopt: alleen de strook met het silhouet en de tagline, zodat
 *   het gesprek de ruimte houdt. Op een smal scherm vervalt de strook dan helemaal: daar staat de
 *   mobiele topbar al, en elke regel hoogte telt.
 *
 * De begroeting komt pas na het mounten: de server kent de lokale tijd van de gebruiker niet, en
 * een groet die tussen server en browser verschilt geeft een hydratatiefout. Tot dan is de kop leeg
 * maar even hoog, en de groet vervaagt erin – geen tussenwoord dat daarna omspringt.
 */
export function WerkplekHeader({ compact }: { compact: boolean }) {
  const [groet, setGroet] = useState<string | null>(null);
  useEffect(() => {
    const zet = () => setGroet(begroeting(new Date()));
    zet();
    // Wie de werkplek de hele dag open heeft, krijgt 's middags geen "Goedemorgen" meer.
    const t = window.setInterval(zet, 5 * 60_000);
    return () => window.clearInterval(t);
  }, []);

  return (
    <header
      data-testid="werkplek-header"
      data-compact={compact ? "ja" : "nee"}
      className={`relative shrink-0 overflow-hidden ${compact ? "max-md:hidden " : ""}border-b border-lint/10 bg-gradient-to-r from-info/[0.04] via-info/[0.07] to-info/[0.12]`}
    >
      {/* Het silhouet vloeit van links in (masker), en staat in de compacte strook zachter achter de tagline. */}
      <Skyline className={`pointer-events-none absolute inset-y-0 right-0 h-full w-[min(34rem,72%)] text-lint [mask-image:linear-gradient(to_right,transparent,black_35%)] ${compact ? "opacity-60" : ""}`} />
      {compact ? (
        <div className="relative flex h-12 items-center justify-end px-6">
          <Tagline />
        </div>
      ) : (
        <>
          {/* Smal scherm: de compacte strook, met de begroeting als kop. */}
          <div className="relative flex h-12 items-center justify-between gap-3 px-4 md:hidden">
            <Groet groet={groet} className="text-lg" />
          </div>
          <div className="relative mx-auto hidden max-w-5xl items-start justify-between gap-6 px-8 py-7 md:flex">
            <div className="min-w-0">
              <Groet groet={groet} className="text-3xl" />
              <p className="mt-1 text-lg text-lint">Waar kan ik je vandaag mee helpen?</p>
              <p className="mt-2 max-w-xl text-sm text-muted">
                Ik zoek bepalingen op, citeer letterlijk en stel JAS-markeringen voor. Wat ik voorstel,
                beoordeel jij.
              </p>
            </div>
            <Tagline />
          </div>
        </>
      )}
    </header>
  );
}

function Groet({ groet, className }: { groet: string | null; className: string }) {
  return (
    <h1 className={`font-display font-semibold text-lint transition-opacity duration-300 motion-reduce:transition-none ${groet ? "opacity-100" : "opacity-0"} ${className}`}>
      {groet ?? "\u00a0"}
    </h1>
  );
}

function Tagline() {
  return (
    <p className="relative max-w-[15rem] text-right text-sm italic leading-snug text-link max-md:hidden">{TAGLINE}</p>
  );
}
