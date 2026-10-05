"use client";

import { useEffect, useState } from "react";
import { ChevronOmlaag } from "@/components/ui/Icoon";
import { foutTekst } from "@/lib/api";
import { haalElementGraaf, type ElementGraaf } from "@/lib/annotatieNode";
import { haalVerklaringen, type Verklaringen } from "@/lib/verklaringen";
import { graafStatusTekst, waaromVan, type WaaromBron, type WaaromRegel } from "@/lib/waarom";

/** De verklaringen, één keer per pagina; tot ze er zijn staan de codes zelf in beeld. */
export function useVerklaringen(): Verklaringen | undefined {
  const [v, setV] = useState<Verklaringen>();
  useEffect(() => {
    let weg = false;
    void haalVerklaringen().then((x) => { if (!weg) setV(x); });
    return () => { weg = true; };
  }, []);
  return v;
}

const KOP = "text-[11px] font-semibold text-muted";

function Regels({ kop, regels }: { kop: string; regels: WaaromRegel[] }) {
  if (!regels.length) return null;
  return <div>
    <p className={KOP}>{kop}</p>
    <ul className="mt-0.5 space-y-0.5 pl-3">
      {regels.map((r) => <li key={r.code + (r.detail ?? "")} className="text-xs text-ink">
        {/* De naam in beeld, het id in de tooltip: de jurist leest de naam, wie het spoor natrekt het id. */}
        <span title={r.uitleg ? `${r.code} – ${r.uitleg}` : r.code} className="underline decoration-dotted decoration-faint underline-offset-2">{r.naam}</span>
        {r.detail && <span className="text-muted"> – {r.detail}</span>}
      </li>)}
    </ul>
  </div>;
}

/** Waarom staat dit element er? Eén uitklapper voor de reviewkaart en de graafinspector, zodat de
 *  twee plekken nooit iets anders vertellen. Ingeklapt is het één regel; de ruwe modelvraag zit nog
 *  een niveau dieper, onder "technisch detail". */
export function WaaromUitklap({ el, laad }: {
  el?: WaaromBron;
  /** Haalt het element pas op bij openklappen, als de aanroeper het niet in handen heeft (een
   *  markering in de graaf buiten het lid dat in het paneel openstaat). */
  laad?: () => Promise<WaaromBron>;
}) {
  const [geladen, setGeladen] = useState<WaaromBron>();
  const [fout, setFout] = useState(false);
  const bron = el ?? geladen;
  return <details className="group mt-1.5" data-testid="waarom" onClick={(e) => e.stopPropagation()}
    onToggle={(e) => {
      if (!(e.currentTarget as HTMLDetailsElement).open || bron || !laad) return;
      setFout(false);
      laad().then(setGeladen, () => setFout(true));
    }}>
    <summary className="focus-ring inline-flex min-h-[24px] cursor-pointer list-none items-center gap-1 rounded text-xs text-lint coarse:min-h-[44px]">
      <ChevronOmlaag className="-rotate-90 transition-transform group-open:rotate-0" />Waarom?
    </summary>
    {bron ? <WaaromInhoud el={bron} />
      : <p className="mt-1 border-l-2 border-lint/20 pl-3 text-xs text-muted">{fout ? "Het spoor kon niet worden opgehaald." : "Laden…"}</p>}
  </details>;
}

function WaaromInhoud({ el }: { el: WaaromBron }) {
  const v = useVerklaringen();
  // Pas bij het openklappen van het technisch detail: de graafcontrole haalt een graph op.
  const [graafOpen, setGraafOpen] = useState(false);
  const w = waaromVan(el, v);
  return <div className="mt-1 space-y-2 border-l-2 border-lint/20 pl-3">
      {w.handmatig ? (
        <p className="text-xs text-ink">{el.herkomst === "mens"
          ? "Door een jurist zelf gemarkeerd; er is geen spoor van Lex."
          : "Bij dit voorstel is geen spoor bewaard."}</p>
      ) : w.besluit && (
        <p className="text-xs text-ink">
          Besloten door <span title={w.besluit.uitleg ? `${w.besluit.code} – ${w.besluit.uitleg}` : w.besluit.code} className="font-medium underline decoration-dotted decoration-faint underline-offset-2">{w.besluit.naam}</span>
          {w.besluit.detail && <> ({w.besluit.detail})</>}.
        </p>
      )}
      {w.jurist && <p className="text-xs text-ink">Daarna {w.jurist}.</p>}
      {w.subtype && <p className="text-xs text-muted">Subtype: <span className="text-ink">{w.subtype}</span></p>}
      {w.gedegradeerd && <p className="text-xs text-aandacht-geel-tekst">Beoordeeld zonder zinsontleding: alleen de woordpatronen spraken mee.</p>}
      <Regels kop="Bewijs" regels={w.bewijs} />
      <Regels kop="Twijfel" regels={w.twijfel} />
      <Regels kop="Afgehandeld met" regels={w.resolutie} />
      <Regels kop="Controles" regels={w.validatie} />
      {(w.trace || el.id) && <details className="group/tech" onToggle={(e) => {
        if ((e.currentTarget as HTMLDetailsElement).open && el.id) setGraafOpen(true);
      }}>
        <summary className="focus-ring inline-flex cursor-pointer list-none items-center gap-1 rounded text-[11px] text-muted">
          <ChevronOmlaag className="-rotate-90 transition-transform group-open/tech:rotate-0" />Technisch detail
        </summary>
        {w.vraag && <>
          <p className={`${KOP} mt-1`}>Wat het model zag</p>
          <pre className="mt-0.5 max-h-40 overflow-auto whitespace-pre-wrap break-words rounded bg-surface p-2 text-[11px] text-ink">{w.vraag}</pre>
        </>}
        {w.trace && <>
          <p className={`${KOP} mt-1`}>Spoor</p>
          <pre className="mt-0.5 max-h-60 overflow-auto whitespace-pre-wrap break-words rounded bg-surface p-2 text-[11px] text-ink">{JSON.stringify(w.trace, null, 2)}</pre>
        </>}
        {graafOpen && el.id && <GraafDetail id={el.id} />}
      </details>}
  </div>;
}

const PIL = {
  goed: "border-line bg-surface text-ink",
  neutraal: "border-line bg-surface text-muted",
  aandacht: "border-aandacht-geel-rand bg-aandacht-geel-bg text-aandacht-geel-tekst",
} as const;

/** De RDF van deze markering en de graafcontrole van haar laag. Eén keer opgehaald per element. */
function GraafDetail({ id }: { id: string }) {
  const [data, setData] = useState<ElementGraaf>();
  const [fout, setFout] = useState("");
  const [gekopieerd, setGekopieerd] = useState(false);
  useEffect(() => {
    let weg = false;
    haalElementGraaf(id).then((d) => { if (!weg) setData(d); }, (e) => { if (!weg) setFout(foutTekst(e)); });
    return () => { weg = true; };
  }, [id]);
  if (fout) return <p className="mt-1 text-[11px] text-muted" data-testid="graaf-detail-fout">Graafdetail niet beschikbaar: {fout}</p>;
  if (!data) return <p className="mt-1 text-[11px] text-muted">Graaf ophalen…</p>;
  const status = graafStatusTekst(data.graafcontrole);
  return <div data-testid="graaf-technisch">
    <p className={`${KOP} mt-1`}>Graafcontrole van deze laag</p>
    <p className={`mt-0.5 inline-flex rounded-full border px-2 py-0.5 text-[11px] ${PIL[status.ernst]}`}>{status.tekst}</p>
    <p className={`${KOP} mt-1 flex items-center gap-2`}>
      RDF (Turtle)
      <button type="button" className="focus-ring rounded text-[11px] font-normal text-lint underline underline-offset-2 hover:no-underline"
        onClick={() => { void navigator.clipboard?.writeText(data.turtle).then(() => setGekopieerd(true), () => {}); }}>
        {gekopieerd ? "Gekopieerd" : "Kopiëren"}
      </button>
    </p>
    <pre className="mt-0.5 max-h-60 overflow-auto whitespace-pre-wrap break-words rounded bg-surface p-2 text-[11px] text-ink">{data.turtle}</pre>
  </div>;
}
