"use client";

import { useEffect, useLayoutEffect, useRef, useState } from "react";

import { plaatsBubbel, type Afmeting, type Stap, type Vak } from "@/lib/rondleiding";

/** Hoe ver de spotlight om het element heen valt. */
const SPOT_MARGE = 6;
const BUBBEL_BREEDTE = 340;
/** Waar we vanuit gaan zolang de bubbel nog niet gemeten is (eerste frame van een stap). */
const BUBBEL_HOOGTE_SCHATTING = 220;

function vakVan(el: Element): Vak {
  const r = el.getBoundingClientRect();
  return { top: r.top, left: r.left, breedte: r.width, hoogte: r.height };
}

interface Props {
  stap: Stap;
  /** 1-gebaseerd, voor "Stap 4 van 13". */
  nummer: number;
  totaal: number;
  /** Het element waar de bubbel aan hangt; `null` = gecentreerd tonen. */
  doel: Element | null;
  /** Bevestiging van een geslaagde handeling in een interactieve stap. */
  gedaan?: string;
  onVorige?: () => void;
  onVolgende: () => void;
  onSluit: () => void;
}

/** Eén stap van de rondleiding: een bubbel bij het element, met de rest van het scherm gedimd.
 *
 *  Bewust géén `aria-modal` en géén backdrop die klikken opvangt. De rondleiding wijst de échte
 *  werkplek aan – die moet leesbaar blijven voor een schermlezer, en in de interactieve stap moet je
 *  er zelfs op kunnen klikken. Wat de overlay wél doet is dimmen; het aangewezen element houdt zijn
 *  volle kleur, want bij dit product ís die kleur de uitleg (de JAS-klassen). */
export function TourBubbel({
  stap, nummer, totaal, doel, gedaan, onVorige, onVolgende, onSluit,
}: Props) {
  const [vak, setVak] = useState<Vak | null>(null);
  // De eigen afmeting van de bubbel. Zonder die te meten valt niet te bepalen of hij ergens
  // *past* – en dat is precies wat er misging: "de kant met de meeste ruimte" kan nog altijd te
  // weinig ruimte zijn, waarna de bubbel half onder de schermrand hing.
  const [bubbel, setBubbel] = useState<Afmeting>({
    breedte: BUBBEL_BREEDTE, hoogte: BUBBEL_HOOGTE_SCHATTING,
  });
  const [viewport, setViewport] = useState<Afmeting>({ breedte: 1024, hoogte: 768 });
  const bubbelRef = useRef<HTMLDivElement>(null);
  const kopRef = useRef<HTMLParagraphElement>(null);

  // Meebewegen met de pagina. Het artefact en de reviewlijst hebben hun eigen scrollers, dus
  // luisteren op `window` is niet genoeg: een scroll in een binnenpaneel bubbelt alleen in de
  // capture-fase omhoog. Vandaar `capture: true`.
  //
  // In dezelfde slag meten we de bubbel en de viewport: die drie horen bij elkaar, want samen
  // bepalen ze de plaatsing. Ook zonder doel loopt dit effect – de bubbel kan dan nog steeds van
  // maat veranderen, en de viewport hoort na een draai van het toestel te kloppen.
  useLayoutEffect(() => {
    let frame = 0;
    const meet = () => {
      cancelAnimationFrame(frame);
      frame = requestAnimationFrame(() => {
        setVak(doel ? vakVan(doel) : null);
        setViewport({ breedte: window.innerWidth, hoogte: window.innerHeight });
        const r = bubbelRef.current?.getBoundingClientRect();
        if (r && r.height > 0) setBubbel({ breedte: r.width, hoogte: r.height });
      });
    };
    meet();
    window.addEventListener("resize", meet);
    window.addEventListener("scroll", meet, { capture: true, passive: true });
    return () => {
      cancelAnimationFrame(frame);
      window.removeEventListener("resize", meet);
      window.removeEventListener("scroll", meet, { capture: true });
    };
    // `stap.id` hoort erbij: een andere tekst is een andere bubbelhoogte.
  }, [doel, stap.id]);

  // De focus hoort bij elke stap in de bubbel te landen, anders staat hij nog op de knop van de
  // vorige stap en leest een schermlezer de nieuwe tekst nooit voor.
  useEffect(() => {
    kopRef.current?.focus();
  }, [stap.id]);

  // Zonder doel telt een eerder gemeten vak niet meer: dan hoort de bubbel gecentreerd te staan in
  // plaats van bij het element van de vórige stap. Afgeleid in plaats van weggeschreven, zodat het
  // effect hierboven geen state hoeft te wissen.
  const actiefVak = doel ? vak : null;

  const plaatsing = plaatsBubbel(actiefVak, bubbel, viewport);

  // In `midden`-modus wijst de bubbel niets aan – dus hoort er ook geen spotlight omheen. Dat is
  // precies het geval bij het gespreksvenster en de sidebar: die vullen bijna het hele scherm, en
  // een uitsparing eromheen licht het halve beeld op in plaats van iets aan te wijzen.
  const spotVak = plaatsing.modus === "midden" ? null : actiefVak;

  const stijl: React.CSSProperties =
    plaatsing.modus === "midden"
      ? {
          top: "50%",
          left: "50%",
          transform: "translate(-50%, -50%)",
          width: BUBBEL_BREEDTE,
          maxWidth: "calc(100vw - 1.5rem)",
        }
      : {
          top: plaatsing.top,
          left: plaatsing.left,
          width: BUBBEL_BREEDTE,
          maxWidth: "calc(100vw - 1.5rem)",
        };

  return (
    <>
      {/* De dimlaag. `pointer-events-none` is essentieel: in stap "Jij beslist" klikt de gebruiker
          op een knop die híéronder ligt. */}
      <div className="pointer-events-none fixed inset-0 z-[60]" aria-hidden>
        {spotVak ? (
          <div
            className="absolute rounded-kaart transition-all duration-150 motion-reduce:transition-none"
            style={{
              top: spotVak.top - SPOT_MARGE,
              left: spotVak.left - SPOT_MARGE,
              width: spotVak.breedte + SPOT_MARGE * 2,
              height: spotVak.hoogte + SPOT_MARGE * 2,
              boxShadow: "0 0 0 9999px rgba(26, 26, 26, 0.55)",
              outline: "2px solid rgb(var(--lint))",
              outlineOffset: "2px",
            }}
          />
        ) : (
          <div className="absolute inset-0 bg-ink/55" />
        )}
      </div>

      <div
        ref={bubbelRef}
        role="dialog"
        aria-label={`Rondleiding, stap ${nummer} van ${totaal}: ${stap.titel}`}
        className="fixed z-[61] rounded-kaart border border-line bg-paper p-4 shadow-kaart animate-rise motion-reduce:animate-none"
        style={stijl}
      >
        <div className="mb-2 flex items-start gap-2">
          <p
            ref={kopRef}
            tabIndex={-1}
            className="focus-ring min-w-0 flex-1 rounded font-display text-sm font-semibold text-lint outline-none"
          >
            {stap.titel}
          </p>
          <button
            type="button"
            onClick={onSluit}
            aria-label="Rondleiding afsluiten"
            className="focus-ring -mr-1 -mt-1 shrink-0 rounded-kaart p-1.5 text-muted transition-colors hover:bg-surface hover:text-ink"
          >
            <svg viewBox="0 0 20 20" className="h-4 w-4" fill="none" stroke="currentColor" strokeWidth="1.6" aria-hidden>
              <path d="M5 5l10 10M15 5L5 15" strokeLinecap="round" />
            </svg>
          </button>
        </div>

        <p className="text-[0.8125rem] leading-6 text-ink">{stap.tekst}</p>
        {stap.waarom && (
          <p className="mt-2 border-l-2 border-lint/30 pl-2.5 text-[0.75rem] leading-5 text-muted">
            <span className="font-semibold text-ink">Waarom: </span>
            {stap.waarom}
          </p>
        )}
        {gedaan && (
          <p className="mt-2 rounded-kaart bg-aandacht-groen-bg px-2.5 py-1.5 text-[0.75rem] text-aandacht-groen-tekst">
            {gedaan}
          </p>
        )}

        {/* Voortgang: een teller voor wie leest, streepjes voor wie scant. */}
        <div className="mt-3.5 flex items-center gap-1" aria-hidden>
          {Array.from({ length: totaal }, (_, i) => (
            <span
              key={i}
              className={`h-1 flex-1 rounded-full ${i < nummer ? "bg-lint" : "bg-line"}`}
            />
          ))}
        </div>

        <div className="mt-2.5 flex items-center gap-2">
          <span className="text-[0.7rem] text-faint">
            Stap {nummer} van {totaal}
          </span>
          <button
            type="button"
            onClick={onSluit}
            className="focus-ring ml-auto min-h-[24px] rounded px-1 text-[0.75rem] text-muted underline underline-offset-2 transition-colors hover:text-ink coarse:min-h-[44px]"
          >
            Overslaan
          </button>
          <button
            type="button"
            onClick={onVorige}
            disabled={!onVorige}
            className="focus-ring min-h-[28px] rounded-button border border-line px-2.5 text-[0.75rem] text-ink transition-colors hover:bg-surface disabled:opacity-40 coarse:min-h-[44px]"
          >
            Vorige
          </button>
          <button
            type="button"
            onClick={onVolgende}
            className="focus-ring min-h-[28px] rounded-button bg-accent px-3 text-[0.75rem] font-medium text-paper transition-opacity hover:opacity-90 coarse:min-h-[44px]"
          >
            {nummer === totaal ? "Afronden" : "Volgende"}
          </button>
        </div>
      </div>
    </>
  );
}
