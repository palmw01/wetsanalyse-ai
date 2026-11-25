"use client";

import { useEffect, useMemo, useState, type RefObject } from "react";
import type { NodeElement, NodeSegment, NodeWeergave } from "@/lib/annotatieNode";
import { hoortBijWeergave } from "@/lib/graaf/bediening";
import { apiGraafBron, type GraafDataBron } from "@/lib/graaf/databron";
import type { KnoopInfo } from "@/lib/graaf/knoopinfo";
import { segmentenVan } from "@/lib/graaf/spans";

/** De wettekst van een bronknoop met de markeringen die erop liggen. */
export interface KnoopDetail { segmenten: NodeSegment[]; elementen: NodeElement[] }
export type DetailStand = KnoopDetail | "laden" | "fout" | null;

/** Per paneel: de weergave per bronknoop, één keer opgehaald (`useGraafStand`, leeg na `ververs`). */
export type DetailCache = Map<string, Promise<NodeWeergave>>;
/** Per paneel: wat de graaf over een knoop weet (`GET knoop`), één keer opgehaald. Annotaties raken
 *  dit niet (het is de BWB-graaf), dus een annotatiewijziging leegt deze cache niet. */
export type InfoCache = Map<string, Promise<KnoopInfo>>;

/** Wat de kennisgraaf over een knoop weet, voor het blok "Uit de kennisgraaf". `null` = niets te
 *  vragen (geen keuze, of een markering of klasse: die staan niet in de BWB-graaf). */
export function useKnoopInfo(iri: string | null, cache: RefObject<InfoCache>,
  bron: GraafDataBron = apiGraafBron): KnoopInfo | "laden" | "fout" | null {
  const [geladen, setGeladen] = useState<{ iri: string; info: KnoopInfo | "fout" }>();
  useEffect(() => {
    if (!iri) return;
    let weg = false;
    let verzoek = cache.current.get(iri);
    if (!verzoek) {
      verzoek = bron.knoopInfo(iri);
      cache.current.set(iri, verzoek);
      verzoek.catch(() => cache.current.delete(iri));
    }
    verzoek.then(
      (info) => { if (!weg) setGeladen({ iri, info }); },
      () => { if (!weg) setGeladen({ iri, info: "fout" }); },
    );
    return () => { weg = true; };
  }, [iri, cache, bron]);
  if (!iri) return null;
  return geladen?.iri === iri ? geladen.info : "laden";
}

/** De tekst van een gekozen bepaling voor de inspector. Staat ze in de weergave van het paneel, dan
 *  komt ze daaruit; anders – een ander artikel, of de hele kennisgraaf, die bewust geen tekst draagt
 *  (`api/app/graaf.py`) – één keer via de weergave van die bepaling. `null` = geen bepaling. */
export function useKnoopDetail(bron: string | null, eigen: NodeWeergave | undefined, cache: RefObject<DetailCache>,
  /** Verandert na een annotatiewijziging: dan opnieuw ophalen. */
  versie = 0, gegevens: GraafDataBron = apiGraafBron): DetailStand {
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
      verzoek = gegevens.bepaling(bron);
      cache.current.set(bron, verzoek);
      // Een mislukte poging blijft niet hangen: de volgende keuze probeert het opnieuw.
      verzoek.catch(() => cache.current.delete(bron));
    }
    verzoek.then(
      (w) => { if (!weg) setGeladen({ bron, detail: { segmenten: segmentenVan(w.segmenten, bron), elementen: w.elementen } }); },
      () => { if (!weg) setGeladen({ bron, detail: "fout" }); },
    );
    return () => { weg = true; };
  }, [bron, uitEigen, cache, versie, gegevens]);
  if (!bron) return null;
  if (uitEigen) return uitEigen;
  return geladen?.bron === bron ? geladen.detail : "laden";
}

/** Het element achter een gekozen markering: uit wat er al is (de weergave van het paneel of de
 *  opgehaalde tekst), anders meteen ophalen – niet pas als je de Waarom-uitklap opent. */
export function useMarkeringElement(elementId: string | undefined, bekend: readonly NodeElement[],
  /** De tekst waar het element meestal in zit, laadt nog: nog niet apart ophalen. */
  wacht = false, bron: GraafDataBron = apiGraafBron): NodeElement | "laden" | "fout" | undefined {
  const uitBekend = elementId ? bekend.find((e) => e.id === elementId) : undefined;
  const [geladen, setGeladen] = useState<{ id: string; el: NodeElement | "fout" }>();
  useEffect(() => {
    if (!elementId || uitBekend || wacht) return;
    let weg = false;
    bron.element(elementId).then(
      (el) => { if (!weg) setGeladen({ id: elementId, el }); },
      () => { if (!weg) setGeladen({ id: elementId, el: "fout" }); },
    );
    return () => { weg = true; };
  }, [elementId, uitBekend, wacht, bron]);
  if (!elementId) return undefined;
  if (uitBekend) return uitBekend;
  return geladen?.id === elementId ? geladen.el : "laden";
}
