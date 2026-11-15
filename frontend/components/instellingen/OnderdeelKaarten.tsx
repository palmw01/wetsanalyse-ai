"use client";

import { useEffect, useState } from "react";

import { Regel, Regels } from "@/components/ui/Lijst";
import { Kaart } from "@/components/ui/Pagina";
import { foutTekst, haalCatalogus, haalOnderdeel } from "@/lib/api";
import type { Catalogus, OnderdeelDetail } from "@/lib/catalogus";

/** De bouwstenen van het tweede niveau van Methodes, Agents en Connectors: de catalogus laden, één onderdeel laden, en
 *  de kaarten die meer dan één tab toont. De catalogus komt uit graph-qa (`GET /v1/catalogus`, ADR-014). */

export function useCatalogus(): { data: Catalogus | null; fout: string | null } {
  const [data, setData] = useState<Catalogus | null>(null);
  const [fout, setFout] = useState<string | null>(null);
  useEffect(() => {
    let weg = false;
    haalCatalogus().then((c) => { if (!weg) setData(c); })
      .catch((e) => { if (!weg) setFout(foutTekst(e, "Wat Lex gebruikt kon niet worden geladen.")); });
    return () => { weg = true; };
  }, []);
  return { data, fout };
}

/** Eén onderdeel met zijn inhoud; `null` zolang het laadt of als `id` leeg is. */
export function useOnderdeel(id: string | null): { o: OnderdeelDetail | null; fout: string | null } {
  const [o, setO] = useState<OnderdeelDetail | null>(null);
  const [fout, setFout] = useState<string | null>(null);
  useEffect(() => {
    if (!id) return;
    let weg = false;
    const i = id.indexOf("/");
    haalOnderdeel(id.slice(0, i), id.slice(i + 1)).then((d) => { if (!weg) { setO(d); setFout(null); } })
      .catch((e) => { if (!weg) setFout(foutTekst(e, "Dit onderdeel kon niet worden geladen.")); });
    return () => { weg = true; setO(null); };
  }, [id]);
  return { o, fout };
}

export const tekst = (x: unknown): string =>
  (typeof x === "string" ? x : Array.isArray(x) ? x.join(", ") : x == null ? "" : String(x));

export function HerkomstKaart({ o }: { o: OnderdeelDetail }) {
  return (
    <Kaart titel="Herkomst" data-blok="herkomst">
      <Regels className="text-sm">
        <Regel naam="Bron">{o.herkomst.bron}</Regel>
        <Regel naam="Licentie">{o.herkomst.licentie === "repo" ? "eigen werk, de licentie van deze repo" : o.herkomst.licentie}</Regel>
        <Regel naam="Tekst">{o.herkomst.letterlijk ? "letterlijk uit de bron, met de licentietekst erbij" : "in eigen woorden"}</Regel>
      </Regels>
    </Kaart>
  );
}

/** Een tekst die lang kan zijn (een methodesectie, de opdracht van een agent): ingeklapt tot je hem opent. */
export function LangeTekst({ titel, toelichting, children, ...rest }: {
  titel: string;
  toelichting?: string;
  children: React.ReactNode;
} & Record<`data-${string}`, string>) {
  const [open, setOpen] = useState(false);
  return (
    <Kaart titel={titel} toelichting={toelichting} {...rest}
      acties={<button type="button" onClick={() => setOpen((x) => !x)} aria-expanded={open}
        className="focus-ring rounded text-xs font-medium text-lint hover:underline">{open ? "Inklappen" : "Lezen"}</button>}>
      {open && <div className="whitespace-pre-wrap text-sm text-ink">{children}</div>}
    </Kaart>
  );
}
