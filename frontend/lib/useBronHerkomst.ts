"use client";

import { useEffect, useState } from "react";

import { haalToestanden } from "@/lib/api";
import { haalBepalingDetail, type BepalingDetail } from "@/lib/bepalingDetail";
import { herkomstVan, standMeldingen, type Herkomst, type StandMeldingData } from "@/lib/herkomst";

/** De herkomst van een bepaling voor de kop van het paneel: het detail uit de graaf (gedeeld met *Wat de graaf weet*,
 *  `haalBepalingDetail` cachet) en, in een werkgebied, de peildatum. Tot het detail er is: alleen wat de IRI zegt. Faalt
 *  het detail, dan blijft het daarbij – de kop is nooit leeg. */
export function useBronHerkomst(doel: { bron_iri: string; jci?: string; werkgebied_id?: string } | undefined): {
  herkomst: Herkomst | undefined;
  meldingen: StandMeldingData[];
  detail: BepalingDetail | undefined;
} {
  const iri = doel?.bron_iri;
  const wg = doel?.werkgebied_id;
  const [detail, setDetail] = useState<{ iri: string; d: BepalingDetail | undefined }>();
  const [peil, setPeil] = useState<{ wg: string; peildatum: string | null }>();
  useEffect(() => {
    if (!iri) return;
    let levend = true;
    haalBepalingDetail(iri).then((d) => levend && setDetail({ iri, d })).catch(() => levend && setDetail({ iri, d: undefined }));
    return () => { levend = false; };
  }, [iri]);
  useEffect(() => {
    if (!wg) return;
    let levend = true;
    haalToestanden(wg).then((t) => levend && setPeil({ wg, peildatum: t?.peildatum ?? null }));
    return () => { levend = false; };
  }, [wg]);
  if (!doel || !iri) return { herkomst: undefined, meldingen: [], detail: undefined };
  const d = detail?.iri === iri && detail.d?.beschikbaar ? detail.d : undefined;
  const herkomst = herkomstVan(d
    ? { iri, label: d.vindplaats.label, regeling: d.vindplaats.regeling, jci: d.vindplaats.jci || doel.jci, plaats: d.plaats,
        geldig_vanaf: d.geldig_vanaf, url: d.url }
    : { iri, jci: doel.jci });
  const peildatum = wg && peil?.wg === wg ? peil.peildatum : null;
  const meldingen = d ? standMeldingen({ geldig_vanaf: d.geldig_vanaf, gelezenJci: doel.jci, peildatum }) : [];
  return { herkomst, meldingen, detail: d };
}
