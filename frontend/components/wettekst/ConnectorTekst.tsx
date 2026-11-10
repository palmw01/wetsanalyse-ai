"use client";

import { Citaat } from "@/components/ui/Citaat";
import { externGroepen, type ExternGroep } from "@/lib/antwoord";
import type { StukPassage } from "@/lib/bronStuk";
import { bronHref } from "@/lib/url";

type Verwijzing = { id: string; label: string; link: string };

/** Elke getekende eenheid (een alinea, een voetnoot, een tabel), in documentvolgorde: om naar een kop te springen. */
export const STUK_EENHEID = "[data-passage], [data-extern-tabel]";

/** De tekst van een stuk uit een bronconnector (ADR-013), op één manier getekend (het bronvenster, PR 6): in het
 *  antwoordblok `extern` en in het venster van een stuk. Een alinea als citaat, een voetnoot klein met de stukken waar
 *  ze naar verwijst, een tabel als tabel (de cellen in hun kolom, de tekst letterlijk). Wat Lex citeerde (`geciteerd`,
 *  de nummers van de passages) staat gemarkeerd; de rest is context. Geen andere plek tekent deze rijsoorten
 *  (`app/connectorTekst.test.ts`). */
export function ConnectorTekst({ passages, geciteerd, onOpen }: {
  passages: readonly StukPassage[];
  geciteerd?: ReadonlySet<number>;
  /** Een verwijzing in een voetnoot openen (een tab naast het gesprek); zonder: de link naar de bron. Ctrl/⌘ opent
   *  altijd de bron zelf. */
  onOpen?: (v: Verwijzing) => void;
}) {
  return (
    <div className="space-y-3">
      {externGroepen(passages).map((g, i) => <Groep key={i} groep={g} geciteerd={geciteerd} onOpen={onOpen} />)}
    </div>
  );
}

function Groep({ groep, geciteerd, onOpen }: { groep: ExternGroep; geciteerd?: ReadonlySet<number>; onOpen?: (v: Verwijzing) => void }) {
  const nrs = groep.soort === "tabel" ? groep.rijen.map((r) => r.nr) : [groep.passage.nr];
  const gemarkeerd = geciteerd && nrs.some((n) => geciteerd.has(n));
  const markering = gemarkeerd ? "rounded-sm border-l-2 border-lint bg-lint/[0.04] pl-2" : "";
  if (groep.soort === "tabel") {
    const kolommen = groep.kop?.cellen ?? [];
    return (
      <div className={`space-y-1 ${markering}`} data-extern-tabel data-geciteerd={gemarkeerd || undefined}>
        {groep.kop?.kop && <p className="text-xs font-medium text-muted">{groep.kop.kop}</p>}
        <div className="max-w-full overflow-x-auto">
          <table className="min-w-full border-collapse text-xs">
            {groep.kop && <caption className="pb-1 text-left font-medium text-ink">{groep.kop.tekst}</caption>}
            {kolommen.some(Boolean) && (
              <thead><tr>{kolommen.map((k, i) => <th key={i} scope="col" className="border-b border-line px-2 py-1 text-left font-medium">{k}</th>)}</tr></thead>
            )}
            <tbody>
              {groep.rijen.map((r) => (
                <tr key={r.nr} className="border-b border-line last:border-0">
                  {(r.cellen ?? [r.tekst]).map((c, i) => <td key={i} className="px-2 py-1 align-top">{c}</td>)}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    );
  }
  const p = groep.passage;
  if (groep.soort === "voetnoot") {
    return (
      <p className={`text-xs text-muted ${markering}`} data-extern-voetnoot data-passage={p.nr} data-geciteerd={gemarkeerd || undefined}>
        <span className="font-medium">Voetnoot:</span> {p.tekst}
        {p.verwijst_naar?.map((v) => {
          const href = bronHref(v.link);
          return <span key={v.id}> · {href ? (
            <a href={href} target="_blank" rel="noopener noreferrer" data-verwijzing={v.id}
              onClick={(e) => { if (!onOpen || e.metaKey || e.ctrlKey || e.shiftKey) return; e.preventDefault(); onOpen(v); }}
              className="focus-ring rounded underline underline-offset-2">{v.label}</a>
          ) : v.label}</span>;
        })}
      </p>
    );
  }
  return (
    <div className={`space-y-1 ${markering}`} data-passage={p.nr} data-geciteerd={gemarkeerd || undefined}>
      {p.kop && <p className="text-xs font-medium text-muted">{p.kop}</p>}
      <Citaat>{p.tekst}</Citaat>
    </div>
  );
}
