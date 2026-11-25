"use client";

import { SluitKnop } from "@/components/ui/PaneelKop";
import { useEffect, useLayoutEffect, useRef, useState } from "react";

import { knopKlasse } from "@/components/ui/Button";
import { Melding } from "@/components/ui/Melding";
import { Meter } from "@/components/ui/Meter";
import {
  FASE_LABEL, klikGat, maskRechthoeken, plaatsBubbel, spotKader, uitsnede, vakVan, zichtbaarDeel,
  type Afmeting, type Plaatsing, type Stap, type Vak,
} from "@/lib/rondleiding";

/** Hoe ver de spotlight om het element heen valt. */
const SPOT_MARGE = 6;
/** De outline van het kader (2px) plus haar afstand (2px): ook die hoort binnen het venster. */
const SPOT_RAND = 4;
/** Hoe ver het klikbare gat om het element heen valt, in een stap die om een handeling vraagt.
 *  Ruimer dan de spotlight: het gat mag best iets over de rand vallen, maar een meting die een paar
 *  pixels achterloopt mag nooit de knop afdekken waar de rondleiding juist om vraagt. */
const GAT_MARGE = 14;
const BUBBEL_BREEDTE = 360;
/** Waar we vanuit gaan zolang de bubbel nog niet gemeten is (eerste frame van een stap). */
const BUBBEL_HOOGTE_SCHATTING = 230;

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
 *  De dimlaag bestaat uit losse rechthoeken die kliks opvangen (`maskRechthoeken`). Dat moet wel:
 *  eerst was het één vlak met een box-shadow, en een box-shadow tekent wel maar vangt niets — de
 *  hele werkplek bleef tijdens de rondleiding bedienbaar, en één klik op "Nieuw gesprek" gooide weg
 *  waar de volgende stap naar wees.
 *
 *  In een stap die om een handeling vraagt blijft er een gat op het aangewezen element, zodat je
 *  daar wél kunt klikken. Klik je ergens anders, dan pulseert de bubbel: een geblokkeerde klik mag
 *  niet als een bevroren scherm voelen.
 *
 *  Bewust géén `aria-modal`: de rondleiding wijst de échte werkplek aan, en die moet leesbaar
 *  blijven voor een schermlezer. Het aangewezen element houdt zijn volle kleur, want bij dit product
 *  ís die kleur de uitleg (de JAS-klassen). */
export function TourBubbel({
  stap, nummer, totaal, doel, gedaan, onVorige, onVolgende, onSluit,
}: Props) {
  const [vak, setVak] = useState<Vak | null>(null);
  const [viewport, setViewport] = useState<Afmeting>({ breedte: 1024, hoogte: 768 });
  const [plaatsing, setPlaatsing] = useState<Plaatsing>({ modus: "midden" });
  // De kant die deze stap eerder koos. Het aangewezen element kan tijdens de stap groeien – het
  // klassepalet, de verwerp-chips, de kaart die uitklapt bij selectie – en zonder dit geheugen koos
  // `plaatsBubbel` opnieuw, waarna de bubbel middenin je handeling van kant wisselde of naar het
  // scherm-midden sprong. Hij mag meeschuiven, niet verspringen.
  const vorigeKant = useRef<Plaatsing["modus"] | null>(null);
  const bubbelRef = useRef<HTMLDivElement>(null);
  const kopRef = useRef<HTMLParagraphElement>(null);
  // Korte nadruk na een klik op de dimlaag: "je moet hier zijn".
  const [pulse, setPulse] = useState(false);

  // Meebewegen met de pagina. Het artefact en de reviewlijst hebben hun eigen scrollers, dus
  // luisteren op `window` is niet genoeg: een scroll in een binnenpaneel bubbelt alleen in de
  // capture-fase omhoog. Vandaar `capture: true`.
  //
  // In dezelfde slag meten we de bubbel en de viewport: die drie horen bij elkaar, want samen
  // bepalen ze de plaatsing. Ook zonder doel loopt dit effect – de bubbel kan dan nog steeds van
  // maat veranderen, en de viewport hoort na een draai van het toestel te kloppen.
  useLayoutEffect(() => {
    let frame = 0;
    // Een nieuwe stap of een nieuw element begint blanco: de vastgehouden kant hoorde bij de vorige.
    vorigeKant.current = null;
    const meet = () => {
      cancelAnimationFrame(frame);
      frame = requestAnimationFrame(() => {
        const scherm = { breedte: window.innerWidth, hoogte: window.innerHeight };
        // De eigen afmeting van de bubbel. Zonder die te meten valt niet te bepalen of hij ergens
        // *past* – en dat is precies wat er misging: "de kant met de meeste ruimte" kan nog altijd
        // te weinig ruimte zijn, waarna de bubbel half onder de schermrand hing.
        const r = bubbelRef.current?.getBoundingClientRect();
        const eigen: Afmeting =
          r && r.height > 0
            ? { breedte: r.width, hoogte: r.height }
            : { breedte: BUBBEL_BREEDTE, hoogte: BUBBEL_HOOGTE_SCHATTING };
        const gemeten = doel ? vakVan(doel) : null;
        // Meten en plaatsen in één slag: de plaatsing hangt van alle drie de metingen af, en de
        // vastgehouden kant hoort maar op één plek bijgewerkt te worden.
        const plek = plaatsBubbel(gemeten, eigen, scherm, vorigeKant.current ?? undefined);
        if (plek.modus !== "midden") vorigeKant.current = plek.modus;
        setVak(gemeten);
        setViewport(scherm);
        setPlaatsing(plek);

        // In een stap die om een handeling vraagt hoort het element héél in beeld te staan. Het
        // klassepalet maakt de reviewkaart in één klap honderden pixels hoger, en de reviewlijst
        // scrolt alleen mee als de selectie verspringt – opende het palet op de kaart die al
        // geselecteerd was, dan stonden de klassen onder de schermrand. `nearest` doet niets zodra
        // het element past, dus dit blijft niet heen en weer scrollen.
        if (doel && stap.interactie && gemeten) {
          const heel = gemeten.top >= 0 && gemeten.top + gemeten.hoogte <= scherm.hoogte;
          if (!heel) {
            doel.scrollIntoView({
              block: "nearest",
              behavior: window.matchMedia("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth",
            });
          }
        }
      });
    };
    meet();
    window.addEventListener("resize", meet);
    window.addEventListener("scroll", meet, { capture: true, passive: true });

    // Het aangewezen element kan zélf van maat veranderen, zonder scroll of resize. Dat gebeurt
    // precies in de stap die om een handeling vraagt: klik je op Akkoord, dan verdwijnt die knop en
    // komt Heropenen ervoor in de plaats, en de actierij krimpt. Zonder deze waarneming bleef de
    // spotlight op de oude maat staan en dekte het gat in de dimlaag de knop af — je kon er daarna
    // niet meer op klikken.
    const observer = new ResizeObserver(meet);
    if (doel) observer.observe(doel);
    // De bubbel ook: een langere tekst maakt hem hoger, en dat verplaatst hem.
    if (bubbelRef.current) observer.observe(bubbelRef.current);

    return () => {
      cancelAnimationFrame(frame);
      observer.disconnect();
      window.removeEventListener("resize", meet);
      window.removeEventListener("scroll", meet, { capture: true });
    };
    // `stap.id` hoort erbij: een andere tekst is een andere bubbelhoogte.
  }, [doel, stap.id, stap.interactie]);

  useEffect(() => {
    if (!pulse) return;
    const timer = setTimeout(() => setPulse(false), 420);
    return () => clearTimeout(timer);
  }, [pulse]);

  // De focus hoort bij elke stap in de bubbel te landen, anders staat hij nog op de knop van de
  // vorige stap en leest een schermlezer de nieuwe tekst nooit voor.
  useEffect(() => {
    kopRef.current?.focus();
  }, [stap.id]);

  // Zonder doel telt een eerder gemeten vak niet meer: dan hoort de bubbel gecentreerd te staan in
  // plaats van bij het element van de vórige stap. Afgeleid in plaats van weggeschreven, zodat het
  // effect hierboven geen state hoeft te wissen.
  const actiefVak = doel ? vak : null;

  // Wat er van het aangewezen element in beeld staat. Rand én gat komen hieruit, zodat ze niet uit
  // elkaar kunnen lopen: is er niets te zien – een element dat `display: none` is na een
  // breekpuntwissel, of dat uit zijn scroller is gescrold – dan wijst de rondleiding niets aan in
  // plaats van een vierkantje van een paar pixels in de hoek van het scherm te tekenen.
  const zichtbaar = actiefVak ? zichtbaarDeel(actiefVak, viewport) : null;

  // De rand hangt aan het élement, niet aan de plaatsing van de bubbel. Hing hij aan
  // `plaatsing.modus === "midden"`, dan verdween hij precies bij het gespreksvenster en de sidebar:
  // die vullen bijna het scherm, dus de bubbel centreert, en dan openden de eerste twee stappen van
  // de rondleiding met een kaart die niets aanwees. Juist daar gáát de stap over dat hele gebied.
  const spotVak = spotKader(actiefVak, viewport, SPOT_MARGE, SPOT_RAND);

  // Wat de dimlaag openlaat. Dat is er in élke stap: gedimd wijst het aangewezen element niets aan –
  // dan staat er een rand om iets grijs. Bedienen mag alleen waar de stap erom vraagt; buiten die
  // stap ligt er een onzichtbare vanger overheen (hieronder), zodat een klik nog steeds niet bij de
  // werkplek komt maar de bubbel wel laat pulseren.
  const gat = zichtbaar ? uitsnede(zichtbaar, GAT_MARGE) : null;
  const bedienbaar = Boolean(klikGat(stap, actiefVak, GAT_MARGE));

  // Centreren zonder `transform`: de bubbel draait `animate-rise`, en die animatie houdt (fill-mode
  // `both`) haar eigen `transform: translateY(0)` vast. Een `translate(-50%, -50%)` hier viel daardoor
  // weg, en de linkerbovenhoek van de bubbel stond op het midden van het scherm – op een telefoon met
  // *Volgende* buiten beeld, waarna de rondleiding niet verder kon.
  const stijl: React.CSSProperties =
    plaatsing.modus === "midden"
      ? {
          inset: 0,
          margin: "auto",
          height: "fit-content",
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
      {/* De dimlaag: losse rechthoeken die kliks opvangen, met een gat waar de stap om een
          handeling vraagt. Zie `maskRechthoeken` voor waarom dit geen box-shadow meer is.

          De container staat op `pointer-events-none` en alleen de rechthoeken zelf vangen. Zonder
          dat is het gat een illusie: de container dekt het hele scherm, dus een klik "in het gat"
          landt nog steeds op hém en bereikt de knop eronder nooit. */}
      <div className="pointer-events-none fixed inset-0 z-[60]" aria-hidden>
        {maskRechthoeken(gat, viewport).map((v, i) => (
          // Bewust zónder transitie: een animerende rechthoek wordt ook geanimeerd geraakt door de
          // muis, dus tijdens die 150 ms zou hij de knop nog afdekken. De rand hieronder beweegt wel
          // mee; die vangt niets.
          <div
            key={i}
            onClick={() => setPulse(true)}
            className="pointer-events-auto absolute bg-ink/40"
            style={{ top: v.top, left: v.left, width: v.breedte, height: v.hoogte }}
          />
        ))}
        {/* Buiten een interactieve stap dekt deze onzichtbare laag het gat af: je ziet het element
            onverminderd, maar een klik komt er niet doorheen – die pulseert de bubbel, net als op de
            dimlaag zelf. Bewust zonder achtergrond en zonder transitie (zie hierboven). */}
        {gat && !bedienbaar && (
          <div
            onClick={() => setPulse(true)}
            className="pointer-events-auto absolute"
            style={{ top: gat.top, left: gat.left, width: gat.breedte, height: gat.hoogte }}
          />
        )}
        {/* De rand om het aangewezen element. Los van de dimlaag, zodat hij het gat niet afdekt. */}
        {spotVak && (
          <div
            className="pointer-events-none absolute rounded-kaart transition-all duration-150 motion-reduce:transition-none"
            style={{
              top: spotVak.top,
              left: spotVak.left,
              width: spotVak.breedte,
              height: spotVak.hoogte,
              outline: "2px solid rgb(var(--lint))",
              outlineOffset: "2px",
            }}
          />
        )}
      </div>

      {/* De bubbel heeft de vorm van een venster in de app (`DialoogKop`, `PaneelKop`): kop met de soort klein boven de titel
          en het kruisje, dan de tekst, dan een voet met de voortgang en de knoppen. Geen eigen knopstijl: `knopKlasse`. */}
      <div
        ref={bubbelRef}
        data-rondleiding-bubbel=""
        role="dialog"
        aria-label={`Rondleiding, stap ${nummer} van ${totaal}: ${stap.titel}`}
        className={`fixed z-[61] overflow-hidden rounded-kaart border bg-paper shadow-kaart animate-rise transition-[border-color,box-shadow,transform] duration-200 motion-reduce:animate-none motion-reduce:transition-none ${
          pulse ? "scale-[1.02] border-accent ring-2 ring-accent/40" : "border-line"
        }`}
        style={stijl}
      >
        <div className="flex items-start gap-3 border-b border-line px-5 pb-3 pt-3.5">
          <div className="min-w-0 flex-1">
            <p className="text-xs text-muted">{FASE_LABEL[stap.fase]} · {nummer} van {totaal}</p>
            <p
              ref={kopRef}
              data-rondleiding-titel=""
              tabIndex={-1}
              // De focus staat hier voor de schermlezer, niet als bediening: geen zichtbare ring (`globals.css`).
              className="font-display text-base font-semibold text-lint outline-none"
            >
              {stap.titel}
            </p>
          </div>
          <div className="flex h-10 shrink-0 items-center">
            <SluitKnop onSluit={onSluit} label="Rondleiding afsluiten" />
          </div>
        </div>

        <div className="px-5 py-3.5">
          <p className="text-sm leading-6 text-ink">{stap.tekst}</p>
          {gedaan && <Melding type="bevestiging" compact className="mt-3">{gedaan}</Melding>}
        </div>

        <div className="border-t border-line bg-surface/60 px-5 py-3">
          <Meter percentage={(nummer / totaal) * 100} label={`Voortgang rondleiding: stap ${nummer} van ${totaal}`} dun />
          <div className="mt-3 flex items-center gap-2">
            <button type="button" onClick={onSluit} className={`${knopKlasse("ghost", "sm")} -ml-2`}>
              Overslaan
            </button>
            <span className="ml-auto" />
            {onVorige && (
              <button type="button" onClick={onVorige} className={knopKlasse("secondary", "sm")}>
                Vorige
              </button>
            )}
            <button type="button" onClick={onVolgende} className={knopKlasse("primary", "sm")}>
              {nummer === totaal ? "Afronden" : "Volgende"}
            </button>
          </div>
        </div>
      </div>
    </>
  );
}
