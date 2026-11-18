"use client";

import Link from "next/link";
import { useEffect, useRef, type ReactNode, type Ref } from "react";

import { StandMelding } from "@/components/ui/StandMelding";
import { nogNietInWerking, type NodeElement, type NodeSegment } from "@/lib/annotatieNode";
import { aantalBanen, spansVan } from "@/lib/graaf/spans";
import { markeer } from "@/lib/herbeoordeling";
import { NOG_NIET_IN_WERKING } from "@/lib/herkomst";
import type { SegmentPlek } from "@/lib/annotatieNodeAdapter";
import { jasRandKleur, jasStyle, klasseLabel } from "@/lib/jas";
import { baanStijl, regelhoogte } from "@/lib/markeerbanen";
import { banenInBlok, segmentenVanBlok, type Laag } from "@/lib/markeerlaag";
import { offsetInBlok, snapSelectie } from "@/lib/selectie";
import { ontleed } from "@/lib/wetstructuur";
import { useBepaling } from "@/lib/useBron";
import { bronPad } from "@/lib/werkgebiedPaden";

/** Een plek in de samengestelde bron van een annotatie (UTF-16, `lib/annotatieNodeAdapter.ts`). */
export interface Bereik { start: number; eind: number }

/** De markeerlaag op de wettekst (ontdubbelen PR 4): wat het annoteren aan dezelfde tekst toevoegt – de ene gekozen
 *  markering, de zinsdelen zonder detectortreffer en het zelf selecteren. De posities blijven die van de samengestelde
 *  bron (`plekken`); de reviewlijst, de selectiepopover en het omzetten naar ankers per bronnode rekenen erin. */
export interface MarkeerLaag {
  bron: string;
  plekken: readonly SegmentPlek[];
  /** Alle markeringen in banen (`laagVan`, optie B): een markering die niets omvat als vlak, een die andere omvat als baan. */
  markeringen: Laag | null;
  /** De gekozen markering in de bron (`markeringVan`), of niets: die licht op, de rest dimt. */
  markering: { start: number; eind: number; klasse: string; id?: string; herkomst?: string } | null;
  onKies?: (id?: string) => void;
  ongedekt?: readonly Bereik[];
  /** Een ongedekt zinsdeel aangeklikt: het hele deel, om zelf te markeren. */
  onKiesOngedekt?: (deel: Bereik, el: HTMLElement) => void;
  /** Zelf selecteren; zonder: alleen lezen (vergrendeld, een oude versie). */
  onSelectie?: (sel: Bereik & { x: number; y: number; yBoven: number }) => void;
}

type Bron =
  /** De tekst van een bepaling met haar markeringen in hun JAS-kleur; markeringen staan alleen op hun ankers
   *  (`lib/graaf/spans.ts`). */
  | {
      segmenten: readonly NodeSegment[];
      elementen: readonly NodeElement[];
      /** Het element dat gekozen is: extra nadruk, de rest van de bepaling eromheen. */
      gekozen?: string;
      /** Kan deze markering gekozen worden? Anders is de span alleen kleur. Zonder: niets is te kiezen. */
      kiesbaar?: (elementId: string) => boolean;
      onKies?: (elementId: string) => void;
      tekst?: never;
      laag?: never;
    }
  /** Een losse tekst (de wettekst van nu bij een herbeoordeling), met één fragment aangewezen. */
  | { tekst: string; markeer?: string; segmenten?: never; laag?: never }
  /** De tekst van een annotatie met de markeerlaag erop (`AnnotatieTekst`). */
  | { laag: MarkeerLaag; segmenten?: never; tekst?: never };

/** De wettekst, op één manier getekend (het bronvenster, PR 2): in het paneel naast het gesprek, op de bronpagina en de
 *  elementpagina, in de graafinspector, in een uitklap en bij een herbeoordeling. Geen plek tekent wettekst zelf
 *  (`app/wettekst.test.ts`). `groot` op een eigen pagina, klein in een smalle kolom. */
export function WettekstBlok(props: Bron & { groot?: boolean }) {
  const maat = props.groot ? "text-sm leading-7" : "text-xs leading-relaxed";
  const basisEm = props.groot ? 2 : 1.625;
  if (props.tekst !== undefined) {
    const delen = props.markeer ? markeer(props.tekst, props.markeer) : null;
    return (
      <p className={`whitespace-pre-line border-l-2 border-lint/20 pl-3 ${maat} text-ink`} data-testid="wettekst-blok">
        {delen ? <>{delen[0]}<mark className="rounded bg-aandacht-geel-bg px-0.5 text-ink">{delen[1]}</mark>{delen[2]}</> : props.tekst}
      </p>
    );
  }
  if (props.laag) return <MarkeerTekst laag={props.laag} maat={maat} basisEm={basisEm} />;
  const { segmenten, elementen, gekozen, kiesbaar = () => false, onKies } = props;
  const diepte = diepteVan(segmenten);
  const perId = new Map(elementen.map((e) => [e.id, e]));
  const metTekst = segmenten.filter((s) => s.tekst.trim());
  if (!metTekst.length) return null;
  return <>
    {segmenten.some(nogNietInWerking) && <StandMelding meldingen={[NOG_NIET_IN_WERKING]} />}
    <div className={`space-y-1.5 border-l-2 border-lint/20 pl-3 ${maat} text-ink`} data-testid="graaf-knooptekst">
      {metTekst.map((s) => {
        const nummer = s.nummer?.trim();
        const stukken = spansVan(s, elementen);
        const aantal = aantalBanen(stukken);
        return <p key={s.bron_iri} data-segment={s.bron_iri} className={INSPRING[diepte.get(s.bron_iri) ?? 0]}
          style={{ lineHeight: regelhoogte(basisEm, aantal) }}>
          {nummer && <span className="mr-1 text-faint">{nummer.endsWith(".") ? nummer : `${nummer}.`}</span>}
          {stukken.map((stuk, i) => {
            const el = stuk.element ? perId.get(stuk.element) : undefined;
            const banen = (stuk.banen ?? []).flatMap((b) => {
              const e = perId.get(b.element);
              return e ? [{ id: e.id, klasse: e.klasse, baan: b.baan }] : [];
            });
            if (!el && !banen.length) return <span key={i}>{stuk.tekst}</span>;
            return <MarkeerStuk key={i} tekst={stuk.tekst} vlak={el ? { id: el.id, klasse: el.klasse } : undefined}
              banen={banen} aantal={aantal} gekozen={gekozen} kies={onKies} kiesbaar={kiesbaar} />;
          })}
        </p>;
      })}
    </div>
  </>;
}

/** De wettekst van één bepaling, zelf opgehaald (`useBepaling`): met een laadregel, een foutzin en eventueel de link naar
 *  de bepaling. Voor een plek die alleen de tekst toont. */
export function BepalingTekst({ bronIri, werkgebiedId, link = false, groot, kiesbaar, onKies, leeg, className = "" }: {
  bronIri: string;
  werkgebiedId?: string;
  /** *Open de bepaling* eronder (een uitklap); in een paneel staat de pagina al in de kop. */
  link?: boolean;
  groot?: boolean;
  kiesbaar?: (elementId: string) => boolean;
  onKies?: (elementId: string) => void;
  /** Wat er staat als de bepaling geen eigen tekst heeft. */
  leeg?: ReactNode;
  className?: string;
}) {
  const { view, actueel, fout } = useBepaling(bronIri, "De tekst kon niet worden geladen.");
  return (
    <div className={className} data-wettekst={bronIri}>
      {fout ? <p className="text-sm text-muted">{fout}</p>
        : !view ? <p className="text-sm text-muted">Tekst laden…</p>
          : view.segmenten.some((s) => s.tekst.trim())
            ? <WettekstBlok segmenten={view.segmenten} elementen={actueel} groot={groot} kiesbaar={kiesbaar} onKies={onKies} />
            : leeg ?? <p className="text-sm text-muted">Deze bepaling heeft geen eigen tekst.</p>}
      {link && (
        <Link href={bronPad(bronIri, werkgebiedId)} className="focus-ring mt-2 inline-block rounded text-xs font-medium text-lint hover:underline">
          Open de bepaling
        </Link>
      )}
    </div>
  );
}

/** Eén stuk gemarkeerde wettekst (optie B, `lib/markeerbanen.ts`), voor het leesvenster én de markeerlaag: het vlak van
 *  een markering die niets omvat als `<mark>` in haar klassekleur, de markeringen die andere omvatten als banen eronder in
 *  hun randkleur. Is er een markering gekozen, dan krijgt die een ring en dimmen de andere banen; een vlak dimt niet, want
 *  dan haalt de tekst het contrast niet meer (WCAG AA). De tooltip noemt alles wat op dit stuk
 *  ligt. Een stuk met alleen banen kiest met een klik de binnenste baan; met het toetsenbord kies je in de reviewlijst. */
function MarkeerStuk({ tekst, vlak, banen, aantal, gekozen, kies, kiesbaar = () => true, markRef, klasse = "" }: {
  tekst: string;
  vlak?: { id: string; klasse: string; herkomst?: string };
  banen: { id: string; klasse: string; baan: number }[];
  /** Het aantal banen van de alinea, zodat een baan op elke regel even hoog ligt. */
  aantal: number;
  gekozen?: string;
  kies?: (id: string) => void;
  kiesbaar?: (id: string) => boolean;
  markRef?: Ref<HTMLElement>;
  /** Opmaak van de wettekst zelf (nummer, term). */
  klasse?: string;
}) {
  const alles = [...(vlak ? [vlak] : []), ...banen];
  const uitleg = alles.map((m) => `${klasseLabel(m.klasse)}${"herkomst" in m && m.herkomst === "mens" ? " – door jou gemarkeerd" : ""}`).join(" · ");
  let inhoud: ReactNode = tekst;
  if (vlak) {
    const kleur = `rounded-sm border-b-2 px-0.5 box-decoration-clone ${jasStyle(vlak.klasse)} ${klasse} ${
      vlak.herkomst === "mens" ? "underline decoration-dotted underline-offset-2" : ""} ${
      gekozen === vlak.id ? "ring-2 ring-lint ring-offset-1" : ""}`;
    const kies1 = kies && kiesbaar(vlak.id) ? () => kies(vlak.id) : undefined;
    inhoud = kies1 ? (
      <mark ref={markRef} role="button" tabIndex={0} data-element={vlak.id} title={uitleg}
        aria-label={`${uitleg}: ${tekst}`}
        onClick={kies1} onKeyDown={(e) => { if (e.key !== "Enter" && e.key !== " ") return; e.preventDefault(); kies1(); }}
        className={`focus-ring cursor-pointer ${kleur}`}>{tekst}</mark>
    ) : <mark ref={markRef} data-element={vlak.id} title={uitleg} className={kleur}>{tekst}</mark>;
  } else if (klasse) {
    inhoud = <span className={klasse}>{tekst}</span>;
  }
  if (!banen.length) return <>{inhoud}</>;
  const kiesBaan = !vlak && kies && kiesbaar(banen[0].id) ? () => kies(banen[0].id) : undefined;
  return (
    <span data-banen={banen.map((b) => b.id).join(" ")} title={uitleg} onClick={kiesBaan}
      ref={vlak ? undefined : markRef as Ref<HTMLSpanElement>}
      className={`box-decoration-clone ${kiesBaan ? "cursor-pointer" : ""}`}
      style={baanStijl(banen.map((b) => ({ kleur: jasRandKleur(b.klasse), baan: b.baan, gedimd: Boolean(gekozen && gekozen !== b.id) })), aantal)}>
      {inhoud}
    </span>
  );
}

/** Inspringing per niveau: een onderdeel onder zijn lid, een genest onderdeel (1°) daar weer onder. */
const INSPRING = ["", "pl-3", "pl-6"] as const;

/** Hoe diep een segment staat: één stap per ouder met eigen tekst in de weergave (`parent_iri`), hoogstens twee. De echte
 *  nesting uit de graaf, niet geraden uit de nummervorm; een los onderdeel (de weergave van onderdeel k) staat dus op de
 *  marge, zonder een lege lidregel erboven. */
function diepteVan(segmenten: readonly NodeSegment[]): Map<string, number> {
  // Alleen ouders die zelf tekst hebben staan in beeld; een artikel of lid zonder eigen tekst schuift niets op.
  const per = new Map(segmenten.filter((s) => s.tekst.trim()).map((s) => [s.bron_iri, s]));
  const uit = new Map<string, number>();
  for (const s of segmenten) {
    let d = 0;
    for (let p = s.parent_iri ? per.get(s.parent_iri) : undefined; p && d < 2; p = p.parent_iri ? per.get(p.parent_iri) : undefined) d += 1;
    uit.set(s.bron_iri, d);
  }
  return uit;
}

function nummerVan(s: NodeSegment): string {
  const nummer = s.nummer?.trim();
  return nummer ? (nummer.endsWith(".") ? nummer : `${nummer}.`) : "";
}

/** De gedefinieerde term aan het begin van een segment ("belastingschuldige: …"), in de positie van het segment. */
function termVan(tekst: string): { termStart: number; termEind: number } {
  const o = ontleed(`a. ${tekst}`);
  const start = o.term ? tekst.indexOf(o.term) : -1;
  return { termStart: start, termEind: start >= 0 ? start + o.term.length : -1 };
}

const NADRUK = { nummer: "font-semibold text-lint", term: "font-semibold text-ink", geen: "" } as const;

/** De absolute offset van één grens van een DOM-selectie: het blok (`[data-offset]`) waar de knoop in staat, en de
 *  tekstknopen daarbinnen zonder het nummer (`data-buiten-tekst`). Een grens op het nummer telt als het begin van het
 *  segment; -1 buiten een blok. De rekenstap is `offsetInBlok` (`lib/selectie.ts`, getest). */
function offsetVanGrens(houder: HTMLElement, knoop: Node, offsetInKnoop: number): number {
  const start = knoop.nodeType === Node.TEXT_NODE ? knoop.parentElement : (knoop as Element);
  const blok = start?.closest<HTMLElement>("[data-offset]");
  if (!blok || !houder.contains(blok)) return -1;
  const begin = Number(blok.dataset.offset ?? 0);
  if (start?.closest("[data-buiten-tekst]")) return begin;
  const knopen: Text[] = [];
  const walker = document.createTreeWalker(blok, NodeFilter.SHOW_TEXT, {
    acceptNode: (n) => (n.parentElement?.closest("[data-buiten-tekst]") ? NodeFilter.FILTER_REJECT : NodeFilter.FILTER_ACCEPT),
  });
  for (let n = walker.nextNode(); n; n = walker.nextNode()) knopen.push(n as Text);
  const idx = knopen.indexOf(knoop as Text);
  if (idx < 0) return knoop === blok ? begin : -1;
  return offsetInBlok(knopen.map((n) => n.data.length), idx, offsetInKnoop, begin);
}

/** De wettekst met de markeerlaag: dezelfde blokken als bij lezen (een leesblok met een streep, het nummer ervoor, de
 *  inspringing uit de graaf), per segment een blok met zijn begin in de samengestelde bron als `data-offset`. Het nummer
 *  staat erbuiten (`data-buiten-tekst`), zodat de tekstknopen binnen een blok samen exact het segment zijn. **Haal
 *  `data-offset` niet weg** en zet er geen tekst naast: dan landt elke zelfgemaakte markering stil op de verkeerde plek.
 *
 *  Een selectie eindigt niet altijd met een muisklik: met Shift+pijltjes komt er geen muisevent langs (WCAG 2.1.1), en op
 *  een aanraakscherm zijn de selectiegrepen systeem-UI. Daarom luistert de laag ook op `keyup`, `touchend` en – na een
 *  aanraking, als de selectie even stilstaat – `selectionchange`. */
function MarkeerTekst({ laag, maat, basisEm }: { laag: MarkeerLaag; maat: string; basisEm: number }) {
  const { bron, plekken, markeringen, markering, onKies, ongedekt = [], onKiesOngedekt, onSelectie } = laag;
  const houderRef = useRef<HTMLDivElement>(null);
  const markRef = useRef<HTMLElement>(null);
  const diepte = diepteVan(plekken.map((p) => p.segment));

  const verwerkRef = useRef<() => void>(() => {});
  useEffect(() => {
    verwerkRef.current = () => {
      if (!onSelectie) return;
      const sel = window.getSelection();
      const houder = houderRef.current;
      if (!sel || sel.isCollapsed || sel.rangeCount === 0 || !houder) return;
      const range = sel.getRangeAt(0);
      if (!houder.contains(range.commonAncestorContainer)) return;
      const ruwStart = offsetVanGrens(houder, range.startContainer, range.startOffset);
      const ruwEind = offsetVanGrens(houder, range.endContainer, range.endOffset);
      if (ruwStart < 0 || ruwEind < 0) return;
      const { start, eind } = snapSelectie(bron, ruwStart, ruwEind);
      if (eind - start < 2) return;   // losse letter of alleen witruimte: geen markering
      const rect = range.getBoundingClientRect();
      onSelectie({ start, eind, x: rect.left + rect.width / 2, y: rect.bottom, yBoven: rect.top });
    };
  });
  const selecteerbaar = Boolean(onSelectie);
  useEffect(() => {
    if (!selecteerbaar) return;
    let aanwijzer = "mouse";
    let wacht: ReturnType<typeof setTimeout> | undefined;
    const verwerk = () => verwerkRef.current();
    const opAanwijzer = (e: PointerEvent) => { aanwijzer = e.pointerType; };
    // Alleen na een selectie-gebaar kijken: anders draait dit bij elke toetsaanslag in de pagina.
    const opToets = (e: KeyboardEvent) => { if (e.shiftKey || e.key === "Shift") verwerk(); };
    const opSelectie = () => {
      if (aanwijzer === "mouse") return;
      clearTimeout(wacht);
      wacht = setTimeout(verwerk, 400);
    };
    document.addEventListener("pointerdown", opAanwijzer, true);
    document.addEventListener("keyup", opToets);
    document.addEventListener("touchend", verwerk);
    document.addEventListener("selectionchange", opSelectie);
    return () => {
      clearTimeout(wacht);
      document.removeEventListener("pointerdown", opAanwijzer, true);
      document.removeEventListener("keyup", opToets);
      document.removeEventListener("touchend", verwerk);
      document.removeEventListener("selectionchange", opSelectie);
    };
  }, [selecteerbaar]);

  // De gekozen markering in beeld brengen: bij een lange bepaling sta je anders naar de verkeerde alinea te kijken.
  const actiefId = markering?.id;
  useEffect(() => {
    if (!actiefId || !markRef.current) return;
    const rustig = window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;
    markRef.current.scrollIntoView({ block: "center", behavior: rustig ? "auto" : "smooth" });
  }, [actiefId]);

  return (
    <div ref={houderRef} onMouseUp={() => verwerkRef.current()} data-testid="wettekst-markeerlaag"
      className={`space-y-1.5 border-l-2 border-lint/20 pl-3 ${maat} text-ink`}>
      {plekken.map((p) => {
        const s = p.segment;
        const nummer = nummerVan(s);
        const blok = { offset: p.begin, regel: s.tekst, nummerEind: 0, ...termVan(s.tekst) };
        const delen = segmentenVanBlok(blok, markeringen, [...ongedekt]);
        const aantal = banenInBlok(delen);
        // De gekozen markering in beeld brengen: de ref op het eerste stuk waar ze op ligt.
        const metRef = actiefId && markering && markering.start >= p.begin && markering.start < p.begin + s.tekst.length
          ? delen.findIndex((d) => d.id === actiefId || d.banen?.some((b) => b.id === actiefId)) : -1;
        return (
          <p key={s.bron_iri} data-segment={s.bron_iri} data-lid={p.lid} data-offset={p.begin}
            className={INSPRING[diepte.get(s.bron_iri) ?? 0]} style={{ lineHeight: regelhoogte(basisEm, aantal) }}>
            {nummer && <span data-buiten-tekst className="mr-1 select-none text-faint">{nummer}</span>}
            {delen.map((d, i) => (d.klasse || d.banen) ? (
              // Een `<mark>`, geen knop: inline, dus hij breekt met de tekst mee; `box-decoration-clone` tekent de rand op
              // elk regelfragment. Toetsenbord via role/tabIndex/onKeyDown.
              <MarkeerStuk key={i} tekst={d.tekst} aantal={aantal} gekozen={actiefId}
                vlak={d.klasse && d.id ? { id: d.id, klasse: d.klasse, herkomst: d.herkomst } : undefined}
                banen={d.banen ?? []} kies={onKies ? (id) => onKies(id) : undefined}
                markRef={i === metRef ? markRef : undefined} klasse={NADRUK[d.nadruk ?? "geen"]} />
            ) : d.ongedekt ? (
              <span key={i} data-ongedekt
                {...(onKiesOngedekt ? {
                  role: "button", tabIndex: 0,
                  onClick: (e: React.MouseEvent<HTMLSpanElement>) => onKiesOngedekt(d.ongedekt!, e.currentTarget),
                  onKeyDown: (e: React.KeyboardEvent<HTMLSpanElement>) => {
                    if (e.key !== "Enter" && e.key !== " ") return;
                    e.preventDefault();
                    onKiesOngedekt(d.ongedekt!, e.currentTarget);
                  },
                } : {})}
                title={onKiesOngedekt ? "Hier vond geen detector iets – klik om zelf te markeren" : "Hier vond geen detector iets"}
                className={`${NADRUK[d.nadruk ?? "geen"]} underline decoration-aandacht-geel-rand decoration-dotted decoration-2 underline-offset-4 ${
                  onKiesOngedekt ? "focus-ring cursor-pointer rounded-sm hover:bg-aandacht-geel-bg/60" : ""}`}>{d.tekst}</span>
            ) : <span key={i} className={NADRUK[d.nadruk ?? "geen"]}>{d.tekst}</span>)}
          </p>
        );
      })}
    </div>
  );
}

