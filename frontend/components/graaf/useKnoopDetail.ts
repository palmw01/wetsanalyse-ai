"use client";

import { useEffect, useMemo, useState, type RefObject } from "react";
import { haalElement, haalNodeWeergave, type NodeElement, type NodeSegment, type NodeWeergave } from "@/lib/annotatieNode";
import { hoortBijWeergave } from "@/lib/graaf/bediening";
import { segmentenVan } from "@/lib/graaf/spans";

/** De wettekst van een bronknoop met de markeringen die erop liggen. */
export interface KnoopDetail { segmenten: NodeSegment[]; elementen: NodeElement[] }
export type DetailStand = KnoopDetail | "laden" | "fout" | null;

/** Per paneel: de weergave per bronknoop, één keer opgehaald (`useGraafStand`, leeg na `ververs`). */
export type DetailCache = Map<string, Promise<NodeWeergave>>;

/** De tekst van een gekozen bepaling voor de inspector. Staat ze in de weergave van het paneel, dan
 *  komt ze daaruit; anders – een ander artikel, of de hele kennisgraaf, die bewust geen tekst draagt
 *  (`api/app/graaf.py`) – één keer via de weergave van die bepaling. `null` = geen bepaling. */
export function useKnoopDetail(bron: string | null, eigen: NodeWeergave | undefined, cache: RefObject<DetailCache>,
  /** Verandert na een annotatiewijziging: dan opnieuw ophalen. */
  versie = 0): DetailStand {
  const uitEigen = useMemo<KnoopDetail | null>(() => {
    // Alleen als de weergave van het paneel deze bron helemaal draagt: bij een lid-paneel is het
    // artikel erboven maar voor een deel in beeld, en dan was "de tekst van artikel 9" alleen lid 2.
    if (!bron || !eigen || !hoortBijWeergave(bron, eigen)) return null;
    const segmenten = segmentenVan(eigen.segmenten, bron);
    return segmenten.length ? { segmenten, elementen: eigen.elementen } : null;
  }, [bron, eigen]);
  const [geladen, setGeladen] = useState<{ bron: string; detail: KnoopDetail | "fout" }>();
  useEffect(() => {
    if (!bron || uitEigen) return;
    let weg = false;
    let verzoek = cache.current.get(bron);
    if (!verzoek) {
      verzoek = haalNodeWeergave({ bron_iri: bron });
      cache.current.set(bron, verzoek);
      // Een mislukte poging blijft niet hangen: de volgende keuze probeert het opnieuw.
      verzoek.catch(() => cache.current.delete(bron));
    }
    verzoek.then(
      (w) => { if (!weg) setGeladen({ bron, detail: { segmenten: segmentenVan(w.segmenten, bron), elementen: w.elementen } }); },
      () => { if (!weg) setGeladen({ bron, detail: "fout" }); },
    );
    return () => { weg = true; };
  }, [bron, uitEigen, cache, versie]);
  if (!bron) return null;
  if (uitEigen) return uitEigen;
  return geladen?.bron === bron ? geladen.detail : "laden";
}

/** Het element achter een gekozen markering: uit wat er al is (de weergave van het paneel of de
 *  opgehaalde tekst), anders meteen ophalen – niet pas als je de Waarom-uitklap opent. */
export function useMarkeringElement(elementId: string | undefined, bekend: readonly NodeElement[],
  /** De tekst waar het element meestal in zit, laadt nog: nog niet apart ophalen. */
  wacht = false): NodeElement | "laden" | "fout" | undefined {
  const uitBekend = elementId ? bekend.find((e) => e.id === elementId) : undefined;
  const [geladen, setGeladen] = useState<{ id: string; el: NodeElement | "fout" }>();
  useEffect(() => {
    if (!elementId || uitBekend || wacht) return;
    let weg = false;
    haalElement(elementId).then(
      (el) => { if (!weg) setGeladen({ id: elementId, el }); },
      () => { if (!weg) setGeladen({ id: elementId, el: "fout" }); },
    );
    return () => { weg = true; };
  }, [elementId, uitBekend, wacht]);
  if (!elementId) return undefined;
  if (uitBekend) return uitBekend;
  return geladen?.id === elementId ? geladen.el : "laden";
}
