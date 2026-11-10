"use client";

import Link from "next/link";
import type { ReactNode } from "react";

import { StandMelding } from "@/components/ui/StandMelding";
import { nogNietInWerking, type NodeElement, type NodeSegment } from "@/lib/annotatieNode";
import { spansVan } from "@/lib/graaf/spans";
import { markeer } from "@/lib/herbeoordeling";
import { NOG_NIET_IN_WERKING } from "@/lib/herkomst";
import { jasStyle } from "@/lib/jas";
import { useBepaling } from "@/lib/useBron";
import { bronPad } from "@/lib/werkgebiedPaden";

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
    }
  /** Een losse tekst (de wettekst van nu bij een herbeoordeling), met één fragment aangewezen. */
  | { tekst: string; markeer?: string; segmenten?: never };

/** De wettekst, op één manier getekend (het bronvenster, PR 2): in het paneel naast het gesprek, op de bronpagina en de
 *  elementpagina, in de graafinspector, in een uitklap en bij een herbeoordeling. Geen plek tekent wettekst zelf
 *  (`app/wettekst.test.ts`). `groot` op een eigen pagina, klein in een smalle kolom. */
export function WettekstBlok(props: Bron & { groot?: boolean }) {
  const maat = props.groot ? "text-sm leading-7" : "text-xs leading-relaxed";
  if (props.tekst !== undefined) {
    const delen = props.markeer ? markeer(props.tekst, props.markeer) : null;
    return (
      <p className={`whitespace-pre-line border-l-2 border-lint/20 pl-3 ${maat} text-ink`} data-testid="wettekst-blok">
        {delen ? <>{delen[0]}<mark className="rounded bg-aandacht-geel-bg px-0.5 text-ink">{delen[1]}</mark>{delen[2]}</> : props.tekst}
      </p>
    );
  }
  const { segmenten, elementen, gekozen, kiesbaar = () => false, onKies } = props;
  const perId = new Map(elementen.map((e) => [e.id, e]));
  const metTekst = segmenten.filter((s) => s.tekst.trim());
  if (!metTekst.length) return null;
  return <>
    {segmenten.some(nogNietInWerking) && <StandMelding meldingen={[NOG_NIET_IN_WERKING]} />}
    <div className={`space-y-1.5 border-l-2 border-lint/20 pl-3 ${maat} text-ink`} data-testid="graaf-knooptekst">
      {metTekst.map((s) => {
        const nummer = s.nummer?.trim();
        return <p key={s.bron_iri} className={s.type === "Onderdeel" ? "pl-3" : ""}>
          {nummer && <span className="mr-1 text-faint">{nummer.endsWith(".") ? nummer : `${nummer}.`}</span>}
          {spansVan(s, elementen).map((stuk, i) => {
            const el = stuk.element ? perId.get(stuk.element) : undefined;
            if (!el) return <span key={i}>{stuk.tekst}</span>;
            const kleur = `rounded-sm border-b-2 px-0.5 box-decoration-clone ${jasStyle(el.klasse)}`;
            if (!onKies || !kiesbaar(el.id)) return <mark key={i} title={el.klasse} data-element={el.id} className={kleur}>{stuk.tekst}</mark>;
            const kies = () => onKies(el.id);
            return <mark key={i} role="button" tabIndex={0} title={el.klasse} data-element={el.id}
              onClick={kies} onKeyDown={(e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); kies(); } }}
              className={`focus-ring cursor-pointer ${kleur} ${gekozen === el.id ? "ring-2 ring-lint ring-offset-1" : gekozen ? "opacity-60" : ""}`}>
              {stuk.tekst}</mark>;
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
