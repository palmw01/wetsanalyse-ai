"use client";

import { useContext } from "react";

import { ContextPaneelContext } from "@/components/werkplek/ContextPaneel";
import type { AntwoordVindplaats } from "@/lib/antwoord";
import { vindplaatsTekst } from "@/lib/herkomst";
import { bronHref } from "@/lib/url";

/** Waar iets staat. In de werkplek opent een klik de bepaling naast het gesprek; daarbuiten, of met Ctrl/⌘/Shift, is het
 *  de gewone link naar de bron. Kan `bronHref` er niets mee, dan is het platte tekst. */
export function Vindplaats({ vindplaats: v, kort = false }: {
  vindplaats: AntwoordVindplaats;
  /** Onder een kop die de bepaling al noemt (de leden van één artikel): alleen het eigen label, "lid 2". */
  kort?: boolean;
}) {
  const opener = useContext(ContextPaneelContext);
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
