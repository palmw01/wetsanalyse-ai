"use client";

import type { MouseEvent, ReactNode } from "react";
import { INSTELLINGEN_PARAM, type TabKey } from "@/lib/instellingen";
import { openInstellingen } from "@/lib/instellingenVenster";

/** Een link die het instellingenvenster opent over de pagina waar je bent. Een gewone klik is geen navigatie (zie
 *  `openInstellingen`); een middelklik of Ctrl-klik opent de link zoals elke link, en dan staat het venster open op de
 *  pagina in het nieuwe tabblad. */
export function InstellingenLink({ tab, className, onClick, children }: {
  tab: TabKey;
  className?: string;
  onClick?: () => void;
  children: ReactNode;
}) {
  function klik(e: MouseEvent<HTMLAnchorElement>) {
    if (e.defaultPrevented || e.button !== 0 || e.metaKey || e.ctrlKey || e.shiftKey || e.altKey) return;
    e.preventDefault();
    onClick?.();
    openInstellingen(tab);
  }
  return (
    <a href={`?${INSTELLINGEN_PARAM}=${tab}`} className={className} onClick={klik}>
      {children}
    </a>
  );
}
