"use client";

import { useRouter } from "next/navigation";
import { useCallback, useEffect, useState } from "react";

import { verlaatPagina } from "@/lib/onbewaard";

/** Bewaakt niet-bewaarde wijzigingen buiten de eigen knoppen om: een link elders op de pagina (de
 *  sidebar, "Alle werkgebieden", "Open het werkgebied") of een knop die zelf navigeert. Herladen en
 *  sluiten vangt `BegripKaart` al met `beforeunload`.
 *
 *  Een link vangen we in de capture-fase op `document`, vóór React hem ziet; de navigatie wacht dan op
 *  `toch`. Knoppen die zelf navigeren (een gesprek openen in de sidebar) halen hun handeling door
 *  `bewaak`.
 *
 *  `wachtend` staat tot de gebruiker kiest; toon dan `OnbewaardMelding` met zijn `handeling`, `blijf`
 *  en `toch` (die zet de vlag zelf niet terug: dat doet de eigenaar van `onbewaard`). */
interface Wachtend {
  handeling: "verlaten" | "sluiten";
  doe: () => void;
}

export function useOnbewaardBewaker(onbewaard: boolean) {
  const router = useRouter();
  const [wachtend, setWachtend] = useState<Wachtend | null>(null);

  useEffect(() => {
    if (!onbewaard) return;
    const opKlik = (e: MouseEvent) => {
      if (e.defaultPrevented || e.button !== 0 || e.metaKey || e.ctrlKey || e.shiftKey || e.altKey) return;
      const a = (e.target as Element | null)?.closest?.("a[href]") as HTMLAnchorElement | null;
      if (!a || (a.target && a.target !== "_self") || a.hasAttribute("download")) return;
      const href = a.getAttribute("href") ?? "";
      if (!verlaatPagina(href, window.location)) return;
      e.preventDefault();
      e.stopPropagation();
      const url = new URL(href, window.location.href);
      setWachtend({ handeling: "verlaten", doe: () => router.push(url.pathname + url.search + url.hash) });
    };
    document.addEventListener("click", opKlik, true);
    return () => {
      document.removeEventListener("click", opKlik, true);
    };
  }, [onbewaard, router]);

  // Zonder wijzigingen valt er niets te vragen; een oude vraag vervalt dan ook.
  const [vorige, setVorige] = useState(onbewaard);
  if (vorige !== onbewaard) {
    setVorige(onbewaard);
    if (!onbewaard) setWachtend(null);
  }

  const bewaak = useCallback(
    (doe: () => void, handeling: Wachtend["handeling"] = "verlaten") => {
      if (onbewaard) setWachtend({ handeling, doe });
      else doe();
    },
    [onbewaard],
  );
  const blijf = useCallback(() => setWachtend(null), []);
  const toch = useCallback(() => {
    setWachtend(null);
    wachtend?.doe();
  }, [wachtend]);
  return { wachtend, bewaak, blijf, toch };
}
