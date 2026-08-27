"use client";

import { usePathname } from "next/navigation";
import { useCallback, useEffect, useRef, useState } from "react";

import { Dialog } from "@/components/ui/Dialog";
import type { BeslissingType } from "@/lib/types";
import { TourBubbel } from "@/components/rondleiding/TourBubbel";
import {
  artefactActie, domineert, hervatIndex, RONDLEIDING_VERSIE, schrijfStand, zichtbareStappen,
  type Stap,
} from "@/lib/rondleiding";

/** Waar de rondleiding thuishoort. Buiten dit pad wijst hij niets aan, dus dan pauzeert hij. */
const THUIS = "/workbench";

/** Hoe lang de rondleiding wacht tot de gebruiker in stap "De annotatie openen" zelf klikt. */
const WACHT_OP_KLIK_MS = 6000;

/** Wat de bubbel bevestigt na een handeling in een interactieve stap – per soort beslissing.
 *
 *  Eerder stond hier één regel, gekoppeld aan `stap.interactie`. De stap nodigt echter tot méér uit
 *  dan akkoord geven, en elke beslissing in de demo loopt langs dezelfde teller: koos je een andere
 *  klasse, dan bevestigde de rondleiding "Beoordeeld … staat al klaar" terwijl er niets was
 *  goedgekeurd en er niets doorsprong. Losse export zodat de werkplek hem kan aanroepen zonder de
 *  motor te kennen. */
export const INTERACTIE_BEVESTIGING: Record<BeslissingType, string> = {
  approve: "Beoordeeld. De volgende die aandacht vraagt staat al klaar.",
  edit: "Aangepast. Wat jij wijzigt komt zo in het auditspoor terecht.",
  reject: "Verworpen. Het voorstel blijft zichtbaar, met jouw reden erbij.",
  comment: "Opmerking vastgelegd bij deze markering.",
  heropen: "Heropend. De markering staat weer in de review.",
};

export type TourFase = "welkom" | "stappen" | "slot";

interface Props {
  isBeheerder: boolean;
  /** Staat het annotatie-artefact open? De rondleiding wacht daarop bij de reviewstappen. */
  artefactOpen: boolean;
  /** Het voorbeeldartefact openen (stap 7 doet dat als de gebruiker niet zelf klikt). */
  onOpenArtefact: () => void;
  /** Het voorbeeldartefact sluiten. Nodig bij teruglopen: de stappen vóór de review wijzen naar de
   *  thread, en met het paneel ervoor is daar niets van te zien. */
  onSluitArtefact: () => void;
  /** De rondleiding is voorbij: demo opruimen en de gewone werkplek terugzetten. */
  onKlaar: () => void;
  /** Meldt of de werkplek eronder op slot moet. Aan tijdens de gewone stappen, uit zodra de stap om
   *  een handeling vraagt — dan moet de knop eronder juist bereikbaar zijn, ook met het toetsenbord. */
  onAchtergrondSlot: (slot: boolean) => void;
  /** Loopt op bij elke beslissing in de voorbeeldannotatie. De interactieve stap wacht daarop en
   *  bevestigt de handeling in plaats van hem stil te laten gebeuren. */
  beslissingen: number;
  /** Wát er als laatste beslist is – de bevestiging hoort te passen bij de handeling. */
  laatsteBeslissing: BeslissingType | null;
}

/** De motor van de rondleiding: welke stap staat er, waar hangt hij aan, en wat onderbreekt hem. */
export function Rondleiding({
  isBeheerder, artefactOpen, onOpenArtefact, onSluitArtefact, onKlaar, beslissingen,
  laatsteBeslissing, onAchtergrondSlot,
}: Props) {
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
      setGedaan(INTERACTIE_BEVESTIGING[laatsteBeslissing ?? "approve"]);
    }
  }, [beslissingen, laatsteBeslissing, stap?.interactie]);

  // Het slot volgt de stap. Bij afsluiten of unmounten gaat het er hoe dan ook af: een werkplek die
  // inert blijft staan is erger dan een rondleiding die te vroeg loslaat.
  //
  // In de interactieve stap staat het slot uit, want daar moet de Akkoord-knop bereikbaar zijn —
  // ook met het toetsenbord. De dimlaag houdt de muis daar tegen (op het gat na), maar tabben naar
  // de achtergrond kan er wél. Dat is een bewuste rest: `inert` geldt voor een hele boom, en de
  // ene knop die door moet zit er middenin. De stap nodigt uit tot klikken en noemt de sneltoets,
  // dus in de praktijk komt niemand daar tabbend langs.
  useEffect(() => {
    onAchtergrondSlot(fase === "stappen" && !stap?.interactie);
    return () => onAchtergrondSlot(false);
  }, [fase, stap?.interactie, onAchtergrondSlot]);

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
   *  rondleiding niet afgewezen – die zou hem alleen niet meer terugkrijgen als we hier `gezien`
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
      // de stap terug op een gecentreerde kaart – een rondleiding hoort niet te breken omdat één
      // element ontbreekt.
      if (pogingen++ < 20) timer = setTimeout(zoek, 100);
      else setDoel(null);
    };
    zoek();
    return () => clearTimeout(timer);
  }, [fase, stap, artefactOpen]);

  // Stap 7 laat de gebruiker zélf de annotatie openen. Doet hij dat niet, dan opent de rondleiding
  // hem alsnog – anders loopt hij vast op een handeling die hij misschien niet herkent.
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
      const actie = artefactActie(artefactOpen, doelStap);
      if (actie === "openen") onOpenArtefact();
      else if (actie === "sluiten") onSluitArtefact();
      setGedaan(undefined);
      setIndex(Math.max(0, nieuw));
      schrijfStand({ versie: RONDLEIDING_VERSIE, gezien: false, gestoptBij: doelStap?.id });
    },
    [stappen, artefactOpen, onOpenArtefact, onSluitArtefact],
  );

  // Toetsenbordbediening. Pijltjes en Enter sturen de rondleiding, Escape sluit hem – behalve
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
            Hier laat je wetsartikelen duiden volgens het JAS. Ik loop met je langs de werkstroom, van
            vraag tot beoordeelde annotatie. Je hoeft niets in te vullen: ik gebruik een voorbeeld.
            In {stappen.length} stappen, ongeveer twee minuten.
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
              Nu even niet
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
            Je annotaties vind je terug onder <span className="font-medium text-ink">Annotaties</span> in
            de zijbalk. Deze rondleiding start je opnieuw via je naam linksonder.
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

