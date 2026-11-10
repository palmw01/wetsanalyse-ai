"use client";


import { useOpenBron } from "@/components/werkplek/ContextPaneel";
import type { AntwoordVindplaats } from "@/lib/antwoord";
import type { StukPassage } from "@/lib/bronStuk";
import { vindplaatsTekst } from "@/lib/herkomst";
import { bronHref } from "@/lib/url";

/** Waar iets staat. In de werkplek opent een klik de bepaling naast het gesprek; daarbuiten, of met Ctrl/⌘/Shift, is het
 *  de gewone link naar de bron. Kan `bronHref` er niets mee, dan is het platte tekst. */
export function Vindplaats({ vindplaats: v, kort = false }: {
  vindplaats: AntwoordVindplaats;
  /** Onder een kop die de bepaling al noemt (de leden van één artikel): alleen het eigen label, "lid 2". */
  kort?: boolean;
}) {
  const opener = useOpenBron();
  const label = kort ? v.label : vindplaatsTekst(v);
  const href = bronHref(v.jci || v.iri);
  if (!href) return <span>{label}</span>;
  return (
    <a href={href} target="_blank" rel="noopener noreferrer" data-vindplaats={v.iri}
      onClick={(e) => {
        if (!opener || e.metaKey || e.ctrlKey || e.shiftKey) return;
        e.preventDefault();
        opener({ soort: "bron", bron_iri: v.iri, titel: vindplaatsTekst(v), jci: v.jci || undefined });
      }}
      className="focus-ring rounded text-lint underline underline-offset-2 [overflow-wrap:anywhere]">{label}</a>
  );
}

/** Een stuk uit een bronconnector (ADR-013), zoals `Vindplaats` een bepaling: in de werkplek opent een klik het stuk als
 *  tab naast het gesprek (het bronvenster, PR 6), met wat Lex las; daarbuiten, of met Ctrl/⌘/Shift, de bron zelf. */
export function StukVindplaats({ brontype, id, label, link, gelezen, voorbeeld, className = "" }: {
  brontype: string; id: string; label: string; link?: string;
  /** De versie die Lex las en de passages die hij citeerde: het venster markeert ze en meldt een andere versie. */
  gelezen?: { bron_hash: string; passages: number[] };
  /** Wat in het bericht staat: het venster toont het als de bron niet te bereiken is. */
  voorbeeld?: StukPassage[];
  className?: string;
}) {
  const opener = useOpenBron();
  const href = bronHref(link);
  const open = (e: React.MouseEvent) => {
    if (!opener || e.metaKey || e.ctrlKey || e.shiftKey) return;
    e.preventDefault();
    opener({ soort: "stuk", brontype, id, titel: label, gelezen, voorbeeld });
  };
  if (!href && !opener) return <span className={className}>{label}</span>;
  return (
    <a href={href ?? "#"} target="_blank" rel="noopener noreferrer" data-stuk-link={id} onClick={open}
      className={`focus-ring rounded underline underline-offset-2 [overflow-wrap:anywhere] ${className}`}>{label}</a>
  );
}
