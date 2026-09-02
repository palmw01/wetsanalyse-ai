"use client";

import { useEffect, useMemo, useRef } from "react";

import { jasStyle } from "@/lib/jas";
import { lidUitOffset, offsetInBlok, snapSelectie, vindPositie, type LidRegel } from "@/lib/selectie";
import { blokkenVan } from "@/lib/wetstructuur";
import { bronVan } from "@/lib/annotatie";
import type { Anker } from "@/lib/types";

/** Minimaal element voor highlighting: klasse + letterlijk fragment (+ optioneel id/anker/herkomst). */
export interface Markeerbaar {
  id?: string;
  klasse: string;
  tekst: string;
  herkomst?: string;
  anker?: Anker | null;
}

interface Segment {
  tekst: string;
  klasse?: string;
  id?: string;
  herkomst?: string;
  /** Opmaak van dit stuk wettekst: het onderdeelnummer of de gedefinieerde term. */
  nadruk?: "nummer" | "term";
}

/** Knip `bron` in segmenten, met hoogstens ÉÉN gemarkeerd: de geselecteerde.
 *
 *  Alles tegelijk kleuren was onleesbaar én onvolledig. Twee markeringen kunnen niet op dezelfde
 *  tekst liggen, dus een markering die binnen een langere valt – een Rechtsobject in een zin die als
 *  geheel een Afleidingsregel is – verdween gewoon uit beeld. Nu is de reviewlijst de ingang en laat
 *  de tekst zien wáár het gekozen element staat; zonder selectie blijft de tekst schoon.
 *
 *  De positie komt uit `vindPositie`: eerst het anker (exacte offsets), dan de omringende tekst, dan
 *  het eerste voorkomen. Dat houdt twee identieke fragmenten in één artikel uit elkaar – zonder
 *  anker zou de tweede "De ontvanger" op de eerste landen.
 */
export function segmenteer(bron: string, elementen: Markeerbaar[], actiefId?: string): Segment[] {
  const m = markeringVan(bron, elementen, actiefId);
  if (!m) return [{ tekst: bron }];
  return [
    ...(m.start > 0 ? [{ tekst: bron.slice(0, m.start) }] : []),
    { tekst: bron.slice(m.start, m.eind), klasse: m.klasse, id: m.id, herkomst: m.herkomst },
    ...(m.eind < bron.length ? [{ tekst: bron.slice(m.eind) }] : []),
  ];
}

/** Waar staat de geselecteerde markering in de bron? `null` als er geen is of hij zweeft.
 *
 *  Eén plek waar dat wordt uitgerekend, want de tekst wordt op twee manieren opgebouwd: als hele
 *  bron (`segmenteer`, waar de bestaande tests aan hangen) en per blok (`segmentenVanBlok`). Zouden
 *  die elk hun eigen `vindPositie` doen, dan kunnen ze op een ander voorkomen uitkomen. */
export function markeringVan(
  bron: string,
  elementen: Markeerbaar[],
  actiefId?: string,
): { start: number; eind: number; klasse: string; id?: string; herkomst?: string } | null {
  const el = actiefId ? elementen.find((e) => e.id === actiefId) : undefined;
  const fragment = el?.tekst.trim() ?? "";
  const start = fragment ? vindPositie(bron, fragment, el?.anker, []) : -1;
  if (!el || start < 0) return null;
  return { start, eind: start + fragment.length, klasse: el.klasse, id: el.id, herkomst: el.herkomst };
}

/** De segmenten van één blok: de tekst van dit blok, geknipt op alles wat er anders uitziet.
 *
 *  ÉÉN BRON VAN TEKST. De weergave mag nummer en term niet zelf opnieuw samenstellen naast deze
 *  segmenten — dan staat de tekst dubbel in de DOM én lopen de offsets mis, want `offsetVanGrens`
 *  telt de tekstknopen binnen het blok op. Die fout zat er op 2 sep 2026 in en was niet te zien in
 *  de losse tests van `blokkenVan` en deze functie; alleen hun combinatie brak. Vandaar de test die
 *  eist dat de segmenten samen exact `blok.regel` vormen.
 *
 *  Geknipt wordt op twee soorten grenzen tegelijk: de markering (waar de jurist naar kijkt) en de
 *  opmaak (nummer, term). Een `<mark>` kan bovendien niet over twee blokken heen — die zijn aparte
 *  elementen — dus een markering die van de aanhef doorloopt tot in een onderdeel wordt hier per
 *  blok afgekapt, met dezelfde klasse en hetzelfde id; `box-decoration-clone` laat ze doorlopen.
 */
export function segmentenVanBlok(
  blok: { offset: number; regel: string; nummerEind: number; termStart: number; termEind: number },
  markering: { start: number; eind: number; klasse: string; id?: string; herkomst?: string } | null,
): Segment[] {
  const n = blok.regel.length;
  const eindeBlok = blok.offset + n;
  const raakt = markering && markering.eind > blok.offset && markering.start < eindeBlok;
  const mVan = raakt ? Math.max(markering!.start - blok.offset, 0) : -1;
  const mTot = raakt ? Math.min(markering!.eind - blok.offset, n) : -1;

  const grenzen = [0, n, blok.nummerEind, blok.termStart, blok.termEind, mVan, mTot]
    .filter((g) => g >= 0 && g <= n)
    .sort((a, b) => a - b);

  const uit: Segment[] = [];
  for (let i = 0; i < grenzen.length - 1; i++) {
    const [van, tot] = [grenzen[i], grenzen[i + 1]];
    if (van === tot) continue;   // dubbele grenzen (nummer eindigt waar de term begint)
    const seg: Segment = { tekst: blok.regel.slice(van, tot) };
    if (blok.nummerEind > 0 && tot <= blok.nummerEind) seg.nadruk = "nummer";
    else if (blok.termStart >= 0 && van >= blok.termStart && tot <= blok.termEind) seg.nadruk = "term";
    if (raakt && van >= mVan && tot <= mTot) {
      seg.klasse = markering!.klasse;
      seg.id = markering!.id;
      seg.herkomst = markering!.herkomst;
    }
    uit.push(seg);
  }
  return uit.length ? uit : [{ tekst: blok.regel }];
}

/** De absolute offset in de bron van één grens van een DOM-selectie.
 *
 *  Zoekt het blok waar de knoop in zit (`[data-offset]`), telt de tekstknopen binnen dát blok op tot
 *  aan de grens, en telt de startpositie van het blok erbij. `-1` als de grens buiten elk blok valt —
 *  dan is er niets zinnigs te zeggen over de positie en markeren we liever niet.
 *
 *  Dit werkt alleen zolang de tekstknopen binnen een blok samen exact `blok.regel` zijn. Daarom mag
 *  de weergave geen tekst toevoegen naast `segmentenVanBlok`; zie de waarschuwing daar.
 *
 *  De DOM-wandeling staat hier omdat vitest in node-env geen DOM heeft; de rekenstap zelf is
 *  `offsetInBlok` in `lib/selectie.ts` en is daar getest.
 */
function offsetVanGrens(houder: HTMLElement, knoop: Node, offsetInKnoop: number): number {
  const start = knoop.nodeType === Node.TEXT_NODE ? knoop.parentElement : (knoop as Element);
  const blok = start?.closest<HTMLElement>("[data-offset]");
  if (!blok || !houder.contains(blok)) return -1;

  const knopen: Text[] = [];
  const walker = document.createTreeWalker(blok, NodeFilter.SHOW_TEXT);
  for (let n = walker.nextNode(); n; n = walker.nextNode()) knopen.push(n as Text);

  const idx = knopen.indexOf(knoop as Text);
  if (idx < 0) return -1;
  return offsetInBlok(
    knopen.map((n) => n.data.length),
    idx,
    offsetInKnoop,
    Number(blok.dataset.offset ?? 0),
  );
}

/** Inspringing per nestingniveau. Niveau 0 (lidkop/lopende tekst) staat op de marge; elk niveau
 *  dieper schuift een vaste stap op, met een hangend nummer ervoor. */
const INSPRING = ["pl-0", "pl-7", "pl-14"] as const;

/** Opmaak per soort tekst. Het onderdeelnummer krijgt de lintkleur, de gedefinieerde term
 *  halfvet – zo is in een definitieartikel in één oogopslag te zien wát er gedefinieerd wordt. */
const NADRUK = {
  nummer: "font-semibold text-lint",
  term: "font-semibold text-ink",
  geen: "",
} as const;

export function DocumentPaneel({
  opschrift,
  regels,
  elementen,
  actiefId,
  onKies,
  onSelectie,
}: {
  opschrift: string;
  /** De artikeltekst als regels mét hun lidnummer (`regelsVan`). Niet als kale strings: het lidnummer
   *  is niet uit de volgorde af te leiden, en een markering draagt het wél. */
  regels: LidRegel[];
  elementen: Markeerbaar[];
  actiefId?: string;
  onKies?: (id?: string) => void;
  /** De jurist heeft tekst geselecteerd om zelf te markeren. Weglaten = alleen-lezen. */
  onSelectie?: (sel: {
    fragment: string; start: number; eind: number; lid: string; bron: string;
    x: number; y: number; yBoven: number;
  }) => void;
}) {
  const bron = useMemo(() => bronVan(regels), [regels]);
  const blokken = useMemo(() => blokkenVan(regels), [regels]);
  const markering = useMemo(
    () => markeringVan(bron, elementen, actiefId),
    [bron, elementen, actiefId],
  );
  const gekozen = actiefId ? elementen.find((e) => e.id === actiefId) : undefined;
  const tekstRef = useRef<HTMLParagraphElement>(null);
  const markRef = useRef<HTMLElement>(null);

  // Een selectie eindigt niet altijd met een muisklik. Met Shift+pijltjes komt er geen enkel
  // muisevent langs – dan is zelf markeren met het toetsenbord onmogelijk (WCAG 2.1.1) – en op een
  // aanraakscherm laat het verslepen van een selectiegreep geen `mouseup` achter. Beide luisteraars
  // hangen aan het document omdat de vinger of de cursor buiten de alinea kan loslaten;
  // `verwerkSelectie` controleert zelf al of de selectie wél binnen de tekst valt.
  useEffect(() => {
    if (!onSelectie) return;
    const opToets = (e: KeyboardEvent) => {
      // Alleen na een selectie-gebaar kijken: anders draait dit bij elke toetsaanslag in de pagina.
      if (e.shiftKey || e.key === "Shift") verwerkSelectie();
    };
    document.addEventListener("keyup", opToets);
    document.addEventListener("touchend", verwerkSelectie);
    return () => {
      document.removeEventListener("keyup", opToets);
      document.removeEventListener("touchend", verwerkSelectie);
    };
    // Bewust zonder dependency-array: `verwerkSelectie` leest de actuele bron en moet elke render
    // vers zijn, net als de sneltoetsen in het artefactpaneel.
  });

  // De gekozen markering in beeld brengen. Zonder dit sta je bij een lange bepaling naar de verkeerde
  // alinea te kijken terwijl je in de lijst al drie elementen verder bent.
  useEffect(() => {
    if (!actiefId || !markRef.current) return;
    const rustig = window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;
    markRef.current.scrollIntoView({ block: "center", behavior: rustig ? "auto" : "smooth" });
  }, [actiefId]);

  /** Zet een DOM-selectie om naar offsets in `bron`.
   *
   *  Dit kan omdat de alinea één aaneengesloten reeks span/mark is waarvan de tekstknopen samen
   *  exact `bron` vormen – dus de lengtes optellen tot de startknoop geeft de absolute positie.
   *  De rekenstap zelf staat in `lib/selectie.ts` en is daar getest; hier blijft alleen de
   *  DOM-wandeling over, die in de node-omgeving van vitest toch niet te testen is. */
  function verwerkSelectie() {
    if (!onSelectie) return;
    const sel = window.getSelection();
    const houder = tekstRef.current;
    if (!sel || sel.isCollapsed || sel.rangeCount === 0 || !houder) return;
    const range = sel.getRangeAt(0);
    if (!houder.contains(range.commonAncestorContainer)) return;

    // Per BLOK omrekenen, niet over de hele alinea. De tekst staat sinds 2 sep 2026 in aparte
    // blokken met eigen inspringing, dus de scheidingstekens tussen leden en onderdelen zitten niet
    // meer in de DOM — de tekstknopen vormen samen niet langer exact de bron. Elk blok draagt
    // daarom zijn startpositie als `data-offset`, en binnen dat blok klopt het optellen weer.
    const ruwStart = offsetVanGrens(houder, range.startContainer, range.startOffset);
    const ruwEind = offsetVanGrens(houder, range.endContainer, range.endOffset);
    if (ruwStart < 0 || ruwEind < 0) return;
    const { start, eind } = snapSelectie(bron, ruwStart, ruwEind);
    if (eind - start < 2) return;   // losse letter of alleen witruimte: geen markering

    const rect = range.getBoundingClientRect();
    onSelectie({
      fragment: bron.slice(start, eind),
      start,
      eind,
      lid: lidUitOffset(regels, start),
      bron,
      x: rect.left + rect.width / 2,
      y: rect.bottom,
      yBoven: rect.top,
    });
  }

  return (
    <div data-tour="wettekst" className="rounded-kaart border border-line bg-white p-5 shadow-zacht">
      {opschrift && <h2 className="mb-3 font-display text-lg font-semibold text-lint">{opschrift}</h2>}
      {elementen.length > 0 && (
        <div className="mb-3 flex items-center justify-between gap-3 rounded-kaart bg-lint/5 px-3 py-2 text-xs text-muted">
          {gekozen ? (
            <>
              <span>
                <span className="font-medium text-ink">{gekozen.klasse}</span> in beeld
              </span>
              <button
                type="button"
                onClick={() => onKies?.(undefined)}
                className="shrink-0 font-medium text-lint underline underline-offset-2 hover:no-underline focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-lint"
              >
                Verbergen
              </button>
            </>
          ) : (
            <span>
              Kies een markering in de lijst om te zien waar hij staat, of selecteer tekst om zelf te
              markeren.
            </span>
          )}
        </div>
      )}
      {/* Volle breedte, op verzoek van de jurist (19 aug 2026). Hier stond een leeskolom van ~66
          tekens – de klassieke leesmaat – maar op de losse annotatiepagina begrenst niets anders de
          breedte, en dan plakt een smalle kolom tegen de linkerrand van een breed scherm alsof er
          harde regelafbrekingen in de wettekst zitten. De afweging is bekend en bewust gemaakt:
          lange regels lezen minder prettig, maar er past meer tekst tegelijk in beeld. Verander dit
          dus niet "terug" zonder het te vragen.

          BLOKKEN, GEEN PRE-WRAP. Tot 2 sep 2026 stond alles in één `<p>` met `whitespace-pre-wrap`:
          leden en onderdelen op dezelfde marge, alleen door regeleindes gescheiden. Bij art. 2 lid 1
          IW 1990 lazen de geneste `1°.`–`4°.` daardoor als zelfstandige onderdelen in plaats van als
          uitwerking van de `a.` waar ze onder hangen – een verschil in juridische strekking.

          De scheidingstekens zitten nu niet meer in de DOM; elk blok draagt zijn positie als
          `data-offset` en `offsetVanGrens` rekent daarbinnen. Haal dat attribuut dus niet weg: dan
          landt elke zelfgemaakte markering op de verkeerde tekst, en dat gebeurt stil. */}
      <div ref={tekstRef} onMouseUp={verwerkSelectie} className="text-[0.95rem] leading-7 text-ink">
        {blokken.map((blok, bi) => (
          <div
            key={bi}
            data-offset={blok.offset}
            className={`${INSPRING[Math.min(blok.niveau, INSPRING.length - 1)]} ${
              blok.eersteVanLid && bi > 0 ? "mt-4" : blok.niveau > 0 ? "mt-1" : "mt-2"
            } ${blok.nummer ? "relative" : ""}`}
          >
            {/* ALLEEN deze segmenten – nummer en term worden hier NIET apart gerenderd. Ze zitten
                in de segmenten en dragen daar hun opmaak via `nadruk`. Zet er niets naast: dan
                staat de tekst dubbel in de DOM en telt `offsetVanGrens` te veel op, waarna elke
                zelfgemaakte markering op de verkeerde plek landt. Dat ging op 2 sep 2026 mis. */}
            {segmentenVanBlok(blok, markering).map((s, i) =>
              s.klasse ? (
                // Nadrukkelijk géén `<button>`: die is inline-block en dus één atomaire box. Zodra de
                // markering over meer dan één regel liep, groeide hij naar de volle regelbreedte – een
                // rechthoekig blok tot aan de rechterrand in plaats van een markering om de woorden – en
                // zakte de tekst erna (bij een hele zin: de afsluitende punt) naar de volgende regel.
                // Een `<mark>` is inline en breekt dus gewoon met de tekst mee; `box-decoration-clone`
                // tekent achtergrond, afronding en `px-0.5` opnieuw op elk regelfragment, anders krijgt
                // alleen het eerste stuk een linkerrand en het laatste een rechter. Dat geldt nu ook
                // over blokgrenzen heen: een markering die twee onderdelen raakt wordt in stukken
                // geknipt (`segmentenVanBlok`) en moet er optisch één blijven. De WCAG-2.1.1-eis die
                // de knop kwam oplossen staat hier als `role="button"` + `tabIndex` + `onKeyDown`.
                <mark
                  key={i}
                  ref={
                    // Alleen op het blok waar de markering BEGINT: bij een markering die twee
                    // onderdelen raakt zijn er meerdere <mark>s, en scrollen naar het laatste
                    // zet de kop van het fragment juist buiten beeld.
                    s.id === actiefId && markering !== null &&
                    markering.start >= blok.offset &&
                    markering.start < blok.offset + blok.regel.length
                      ? markRef
                      : undefined
                  }
                  role="button"
                  tabIndex={0}
                  onClick={() => onKies?.(s.id)}
                  onKeyDown={(e) => {
                    if (e.key !== "Enter" && e.key !== " ") return;
                    e.preventDefault();   // Space scrolt anders de tekst weg onder je vinger vandaan
                    onKies?.(s.id);
                  }}
                  aria-label={`${s.klasse}: ${s.tekst}${s.herkomst === "mens" ? " – door jou gemarkeerd" : ""}`}
                  title={s.herkomst === "mens" ? `${s.klasse} – door jou gemarkeerd` : s.klasse}
                  className={`focus-ring box-decoration-clone cursor-pointer rounded px-0.5 ${jasStyle(s.klasse)} ${
                    s.herkomst === "mens" ? "underline decoration-dotted underline-offset-2" : ""
                  } ${actiefId && s.id === actiefId ? "ring-2 ring-lint" : ""}`}
                >
                  {s.tekst}
                </mark>
              ) : (
                <span key={i} className={NADRUK[s.nadruk ?? "geen"]}>
                  {s.tekst}
                </span>
              ),
            )}
          </div>
        ))}
      </div>
    </div>
  );
}
