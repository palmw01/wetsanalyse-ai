"use client";

import { usePathname } from "next/navigation";
import { useCallback, useEffect, useRef, useState } from "react";

import { Dialog } from "@/components/ui/Dialog";
import { TourBubbel } from "@/components/rondleiding/TourBubbel";
import {
  domineert, hervatIndex, RONDLEIDING_VERSIE, schrijfStand, zichtbareStappen, type Stap,
} from "@/lib/rondleiding";

/** Waar de rondleiding thuishoort. Buiten dit pad wijst hij niets aan, dus dan pauzeert hij. */
const THUIS = "/workbench";

/** Hoe lang de rondleiding wacht tot de gebruiker in stap "De annotatie openen" zelf klikt. */
const WACHT_OP_KLIK_MS = 6000;

/** Wat de rondleiding aan de werkplek meldt als de gebruiker een handeling uitvoerde die een
 *  interactieve stap verwachtte. Losse export zodat de werkplek hem kan aanroepen zonder de motor
 *  te kennen. */
export const INTERACTIE_BEVESTIGING: Record<string, string> = {
  akkoord: "Beoordeeld. De volgende die aandacht vraagt staat al klaar.",
};

export type TourFase = "welkom" | "stappen" | "slot";

interface Props {
  isBeheerder: boolean;
  /** Staat het annotatie-artefact open? De rondleiding wacht daarop bij de reviewstappen. */
  artefactOpen: boolean;
  /** Het voorbeeldartefact openen (stap 7 doet dat als de gebruiker niet zelf klikt). */
  onOpenArtefact: () => void;
  /** De rondleiding is voorbij: demo opruimen en de gewone werkplek terugzetten. */
  onKlaar: () => void;
  /** Loopt op bij elke beslissing in de voorbeeldannotatie. De interactieve stap wacht daarop en
   *  bevestigt de handeling in plaats van hem stil te laten gebeuren. */
  beslissingen: number;
}

/** De motor van de rondleiding: welke stap staat er, waar hangt hij aan, en wat onderbreekt hem. */
export function Rondleiding({ isBeheerder, artefactOpen, onOpenArtefact, onKlaar, beslissingen }: Props) {
  const stappen = zichtbareStappen(isBeheerder);
  const [fase, setFase] = useState<TourFase>("welkom");
  const [index, setIndex] = useState(0);
  const [doel, setDoel] = useState<Element | null>(null);
  const [gedaan, setGedaan] = useState<string | undefined>();
  const pad = usePathname();
  const beginPad = useRef(pad);

  const stap: Stap | undefined = stappen[index];

  // Bevestig een handeling die déze stap uitnodigde. De teller bij het betreden van de stap is het
  // ijkpunt: een beslissing die de gebruiker eerder al nam, hoort hier niet als "gedaan" te gelden.
  const beslissingenBijStart = useRef(beslissingen);
  useEffect(() => {
    beslissingenBijStart.current = beslissingen;
    // Alleen bij een stapwissel opnieuw ijken; `beslissingen` bewust buiten de dependencies.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [stap?.id]);
  useEffect(() => {
    if (!stap?.interactie) return;
    if (beslissingen > beslissingenBijStart.current) {
      setGedaan(INTERACTIE_BEVESTIGING[stap.interactie]);
    }
  }, [beslissingen, stap?.interactie]);

  /** Afsluiten: onthouden dát hij gezien is, en de werkplek teruggeven. */
  const sluit = useCallback(
    (afgerond: boolean) => {
      schrijfStand({ versie: RONDLEIDING_VERSIE, gezien: true, gestoptBij: undefined });
      setFase(afgerond ? "slot" : "welkom");
      if (!afgerond) onKlaar();
    },
    [onKlaar],
  );

  /** Onderbreken: de rondleiding verdwijnt, maar onthoudt waar hij was.
   *
   *  Dit is nadrukkelijk iets anders dan overslaan. Wie naar zijn instellingen loopt, heeft de
   *  rondleiding niet afgewezen — die zou hem alleen niet meer terugkrijgen als we hier `gezien`
   *  zouden zetten. */
  const onderbreek = useCallback(() => {
    schrijfStand({ versie: RONDLEIDING_VERSIE, gezien: false, gestoptBij: stap?.id });
    onKlaar();
  }, [onKlaar, stap?.id]);

  // Wegnavigeren of een dialoog over de werkplek heen (instellingen, voorwaarden) onderbreekt.
  // De rondleiding wijst elementen aan die daar niet staan; doorgaan zou een bubbel in het niets
  // opleveren.
  useEffect(() => {
    if (pad !== beginPad.current || !pad.startsWith(THUIS)) onderbreek();
  }, [pad, onderbreek]);

  // Het aan te wijzen element opzoeken. Dat gebeurt na elke stapwissel én zodra het artefact
  // opengaat: de reviewstappen bestaan pas als dat paneel er is.
  useEffect(() => {
    if (fase !== "stappen" || !stap) return;
    let pogingen = 0;
    let timer: ReturnType<typeof setTimeout>;
    const zoek = () => {
      const smal = window.matchMedia("(max-width: 1023px)").matches;
      const sleutel = smal && stap.ankerSmal ? stap.ankerSmal : stap.anker;
      const el =
        document.querySelector(`[data-tour="${sleutel}"]`) ??
        document.querySelector(`[data-tour="${stap.anker}"]`);
      if (el) {
        setDoel(el);
        // Een element dat het scherm domineert wordt niet aangewezen maar gecentreerd getoond
        // (zie `plaatsBubbel`), en dan is scrollen zinloos: `block: "center"` kan iets dat groter
        // is dan de viewport nergens centreren, en op een scroll-container als de thread verschuift
        // het de pagina eromheen in plaats van de inhoud.
        const r = el.getBoundingClientRect();
        const vak = { top: r.top, left: r.left, breedte: r.width, hoogte: r.height };
        if (!domineert(vak, { breedte: window.innerWidth, hoogte: window.innerHeight })) {
          el.scrollIntoView({
            block: "center",
            behavior: window.matchMedia("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth",
          });
        }
        return;
      }
      // Nog even geduld: het artefact schuift in, de lijst rendert. Lukt het daarna niet, dan valt
      // de stap terug op een gecentreerde kaart — een rondleiding hoort niet te breken omdat één
      // element ontbreekt.
      if (pogingen++ < 20) timer = setTimeout(zoek, 100);
      else setDoel(null);
    };
    zoek();
    return () => clearTimeout(timer);
  }, [fase, stap, artefactOpen]);

  // Stap 7 laat de gebruiker zélf de annotatie openen. Doet hij dat niet, dan opent de rondleiding
  // hem alsnog — anders loopt hij vast op een handeling die hij misschien niet herkent.
  useEffect(() => {
    if (fase !== "stappen" || !stap || artefactOpen) return;
    const volgendeVraagtArtefact = stappen[index + 1]?.artefactOpen;
    if (!volgendeVraagtArtefact) return;
    const timer = setTimeout(onOpenArtefact, WACHT_OP_KLIK_MS);
    return () => clearTimeout(timer);
  }, [fase, stap, index, stappen, artefactOpen, onOpenArtefact]);

  const naar = useCallback(
    (nieuw: number) => {
      if (nieuw >= stappen.length) {
        setFase("slot");
        schrijfStand({ versie: RONDLEIDING_VERSIE, gezien: true });
        return;
      }
      const doelStap = stappen[Math.max(0, nieuw)];
      // Vooruit naar een reviewstap terwijl het paneel dicht is: eerst openen.
      if (doelStap?.artefactOpen && !artefactOpen) onOpenArtefact();
      setGedaan(undefined);
      setIndex(Math.max(0, nieuw));
      schrijfStand({ versie: RONDLEIDING_VERSIE, gezien: false, gestoptBij: doelStap?.id });
    },
    [stappen, artefactOpen, onOpenArtefact],
  );

  // Toetsenbordbediening. Pijltjes en Enter sturen de rondleiding, Escape sluit hem — behalve
  // terwijl je in een invoerveld staat, want daar betekenen die toetsen iets anders.
  useEffect(() => {
    if (fase !== "stappen") return;
    const opToets = (e: KeyboardEvent) => {
      const doelEl = e.target as HTMLElement | null;
      if (doelEl?.closest("input, textarea, [contenteditable='true']")) return;
      if (e.key === "Escape") {
        e.preventDefault();
        sluit(false);
      } else if (e.key === "ArrowRight" || e.key === "Enter") {
        e.preventDefault();
        naar(index + 1);
      } else if (e.key === "ArrowLeft") {
        e.preventDefault();
        naar(index - 1);
      }
    };
    window.addEventListener("keydown", opToets);
    return () => window.removeEventListener("keydown", opToets);
  }, [fase, index, naar, sluit]);

  if (fase === "welkom") {
    return (
      <Dialog label="Welkom in de werkplek" variant="compact" onSluit={() => sluit(false)}>
        <div className="p-6">
          <p className="font-display text-lg font-semibold text-lint">Welkom in de werkplek</p>
          <p className="mt-3 text-sm leading-6 text-ink">
            Dit is de plek waar je wetsartikelen laat duiden volgens het JAS. In {stappen.length} korte
            stappen laat ik zien hoe je van een vraag naar een beoordeelde annotatie komt — je hoeft
            niets in te vullen, ik gebruik een voorbeeld. Ongeveer twee minuten.
          </p>
          <p className="mt-3 text-[0.8125rem] leading-5 text-muted">
            Let op: dit is een testomgeving. Analyses kunnen verloren gaan.
          </p>
          <div className="mt-5 flex flex-col gap-2 sm:flex-row sm:justify-end">
            <button
              type="button"
              onClick={() => sluit(false)}
              className="focus-ring min-h-[40px] rounded-button border border-line px-4 text-sm text-ink transition-colors hover:bg-surface coarse:min-h-[48px]"
            >
              Later, niet nu
            </button>
            <button
              type="button"
              onClick={() => {
                setFase("stappen");
                setIndex(hervatIndex(stappen, undefined));
              }}
              className="focus-ring min-h-[40px] rounded-button bg-accent px-4 text-sm font-medium text-paper transition-opacity hover:opacity-90 coarse:min-h-[48px]"
            >
              Start de rondleiding
            </button>
          </div>
        </div>
      </Dialog>
    );
  }

  if (fase === "slot") {
    return (
      <Dialog label="Rondleiding afgerond" variant="compact" onSluit={onKlaar}>
        <div className="p-6">
          <p className="font-display text-lg font-semibold text-lint">Dat is de werkstroom</p>
          <p className="mt-3 text-sm leading-6 text-ink">
            Vraag of opdracht typen → Lex haalt de bepaling op en stelt markeringen voor → jij
            beoordeelt → afronden en exporteren.
          </p>
          <p className="mt-3 text-[0.8125rem] leading-5 text-muted">
            Je annotaties staan onder <span className="font-medium text-ink">Annotaties</span> in de
            zijbalk. Deze rondleiding start je opnieuw via je naam linksonder.
            {isBeheerder && (
              <> Daar vind je als beheerder ook <span className="font-medium text-ink">Beheer</span>,
              voor modelprofielen en gebruikers.</>
            )}
          </p>
          <div className="mt-5 flex justify-end">
            <button
              type="button"
              onClick={onKlaar}
              className="focus-ring min-h-[40px] rounded-button bg-accent px-4 text-sm font-medium text-paper transition-opacity hover:opacity-90 coarse:min-h-[48px]"
            >
              Aan de slag
            </button>
          </div>
        </div>
      </Dialog>
    );
  }

  if (!stap) return null;

  return (
    <>
      <TourBubbel
        stap={stap}
        nummer={index + 1}
        totaal={stappen.length}
        doel={doel}
        gedaan={gedaan}
        onVorige={index > 0 ? () => naar(index - 1) : undefined}
        onVolgende={() => naar(index + 1)}
        onSluit={() => sluit(false)}
      />
      {/* De stapwissel hoort hoorbaar te zijn; de bubbel zelf krijgt focus, maar een schermlezer
          die net iets anders voorleest mist die anders. */}
      <p aria-live="polite" className="sr-only">
        Stap {index + 1} van {stappen.length}: {stap.titel}
      </p>
    </>
  );
}

