"use client";

import { Fragment, useState } from "react";
import { ChevronOmlaag } from "@/components/ui/Icoon";
import { datumTekst, type KnoopInfo, type KnoopWaarde } from "@/lib/graaf/knoopinfo";
import { bronHref } from "@/lib/url";

const TEKSTKNOP = "focus-ring max-w-full rounded px-1 py-0.5 text-left text-xs text-lint underline-offset-2 [overflow-wrap:anywhere] hover:underline coarse:min-h-11";
const ZICHTBAAR = 5;
/** Langer dan dit (aanhef, considerans) staat ingeklapt. */
const LANG = 220;

/** "Uit de kennisgraaf": wat de graaf over de gekozen knoop weet, per groep, letterlijk. Een knoop die
 *  op de kaart staat kies je hier in de graaf; een regeling buiten de graaf wordt een link naar
 *  wetten.overheid.nl. Onderaan, ingeklapt, alle triples ruw – zo ontbreekt er nooit iets. */
export function KnoopFeiten({ info, opKaart, onKies }: {
  info: KnoopInfo | "laden" | "fout";
  /** Staat deze knoop op de kaart? Dan kiest een klik hem in de graaf. */
  opKaart: (iri: string) => boolean;
  onKies: (iri: string) => void;
}) {
  const [allesOpen, setAllesOpen] = useState<Record<string, boolean>>({});
  if (info === "laden") return <p className="text-xs text-faint">Graafgegevens ophalen…</p>;
  if (info === "fout") return <p className="text-xs text-faint">De gegevens uit de kennisgraaf zijn nu niet beschikbaar.</p>;
  if (!info.groepen.length && !info.ruw.length) return null;

  const waarde = (w: KnoopWaarde, i: number) => {
    if (w.iri && opKaart(w.iri)) {
      return <button key={i} type="button" className={TEKSTKNOP} onClick={() => onKies(w.iri!)}>{w.tekst}</button>;
    }
    const href = bronHref(w.link ?? w.iri);
    if (href) return <a key={i} href={href} target="_blank" rel="noopener noreferrer" className={TEKSTKNOP}>{w.tekst}</a>;
    return <Tekst key={i} tekst={datumTekst(w.tekst)} />;
  };

  return <section className="space-y-2" data-testid="graaf-feiten">
    <p className="text-[10px] font-semibold uppercase tracking-wide text-faint">Uit de kennisgraaf</p>
    {info.groepen.map((g) => <div key={g.naam}>
      <p className="text-[11px] font-semibold text-muted">{g.naam}</p>
      <dl className="mt-0.5 space-y-1 pl-3">
        {g.feiten.map((f) => {
          const sleutel = `${g.naam}|${f.eigenschap}`;
          const toon = allesOpen[sleutel] ? f.waarden : f.waarden.slice(0, ZICHTBAAR);
          // Een groep met één gelijknamige eigenschap ("Genoemd in") hoeft de naam niet twee keer.
          const zelfdeNaam = g.feiten.length === 1 && f.eigenschap === g.naam;
          return <div key={f.eigenschap} className={zelfdeNaam ? "text-xs" : "grid grid-cols-[minmax(6rem,38%)_minmax(0,1fr)] gap-x-2 text-xs"}>
            <dt className={zelfdeNaam ? "sr-only" : "text-faint"}>{f.eigenschap}{f.waarden.length > 1 ? ` (${f.waarden.length})` : ""}</dt>
            <dd className="min-w-0 text-ink [overflow-wrap:anywhere]">
              <span className="flex min-w-0 flex-col items-start">{toon.map(waarde)}</span>
              {f.waarden.length > ZICHTBAAR && !allesOpen[sleutel] && <button type="button" className={TEKSTKNOP}
                onClick={() => setAllesOpen((a) => ({ ...a, [sleutel]: true }))}>Alle {f.waarden.length} tonen</button>}
            </dd>
          </div>;
        })}
      </dl>
    </div>)}
    {info.ruw.length > 0 && <details className="group" data-testid="graaf-ruw">
      <summary className="focus-ring flex cursor-pointer list-none items-center gap-1.5 rounded py-0.5 text-[11px] font-semibold text-muted">
        <ChevronOmlaag className="-rotate-90 transition-transform group-open:rotate-0" />Alle eigenschappen uit de graaf <span className="font-normal text-faint">({info.ruw.length})</span>
      </summary>
      <dl className="mt-1 space-y-0.5 pl-4 font-mono text-[10px] leading-relaxed">
        {info.ruw.map((r, i) => <div key={i} className="grid grid-cols-[minmax(7rem,38%)_minmax(0,1fr)] gap-x-2">
          <dt className="text-faint">{r.predicaat}</dt>
          <dd className="min-w-0 break-all text-ink">{r.iri && opKaart(r.iri)
            ? <button type="button" className="focus-ring rounded text-left text-lint hover:underline" onClick={() => onKies(r.iri!)}>{r.waarde}</button>
            : r.waarde}</dd>
        </div>)}
      </dl>
    </details>}
  </section>;
}

/** Een lange waarde zonder spaties (een JCI, een sleutel) mag na `&`, `#` en `/` op een nieuwe regel:
 *  zo breekt hij op een leesbare plek in plaats van midden in een woord. */
function Breekbaar({ tekst }: { tekst: string }) {
  if (/\s/.test(tekst) || tekst.length < 30) return <>{tekst}</>;
  return <>{tekst.split(/(?<=[&#/])/).map((deel, i) => <Fragment key={i}>{i > 0 && <wbr />}{deel}</Fragment>)}</>;
}

/** Een tekstwaarde; een lange (aanhef, considerans) ingeklapt tot je hem opent. */
function Tekst({ tekst }: { tekst: string }) {
  const [open, setOpen] = useState(false);
  if (tekst.length <= LANG) return <span className="max-w-full"><Breekbaar tekst={tekst} /></span>;
  return <span>{open ? tekst : `${tekst.slice(0, LANG - 20).trimEnd()}…`}{" "}
    <button type="button" className={TEKSTKNOP} onClick={() => setOpen((v) => !v)}>{open ? "minder" : "meer"}</button></span>;
}
