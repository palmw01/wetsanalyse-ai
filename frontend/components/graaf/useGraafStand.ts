"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import type { CameraState } from "sigma/types";
import { foutTekst } from "@/lib/api";
import type { NodeDoel } from "@/lib/annotatieNode";
import type { Posities } from "@/lib/graaf/layout";
import { bouwModel, type GraafModel } from "@/lib/graaf/model";
import { layoutVoor } from "@/lib/graaf/rekenaar";
import { STANDAARD_LAGEN, type Lagen } from "@/lib/graaf/weergave";
import { haalSamenhang, haalSamenhangen, type MarkeringFilter, type Samenhang } from "@/lib/samenhang";
import type { GraafBediening } from "./GraafTekenaar";

/** Waar het laden is: de data ophalen (duur onbekend), de layout rekenen (met voortgang), klaar. */
export type Laadfase = { fase: "ophalen" } | { fase: "layout"; fractie: number } | { fase: "klaar" };

/** Wat er getekend wordt: een model mét de posities die erbij horen. Ze worden samen vervangen, zodat
 *  er nooit een beeld is met knopen zonder plek. */
export interface Getekend { model: GraafModel; posities: Posities }

/** De toestand van de graaf. Leeft in het paneel (búiten de `Dialog`): vergroten wisselt de
 *  dialoogvorm en remount daarmee de inhoud; zonder dit waren bijgeladen artikelen, selectie, lagen en
 *  camera dan weg. `actief` laadt pas als de tab voor het eerst opengaat. */
export function useGraafStand(doel: NodeDoel, actief: boolean, extra: NodeDoel[] = []) {
  // Een nieuwe array met dezelfde doelen mag niet opnieuw laden: vergelijk op de bron-IRI's.
  const extraSleutel = extra.map((d) => d.bron_iri).join("|");
  // eslint-disable-next-line react-hooks/exhaustive-deps
  const extraDoelen = useMemo(() => extra, [extraSleutel]);
  const [bronnen, setBronnen] = useState<Samenhang[]>();
  const [nietGeladen, setNietGeladen] = useState(0);
  const [fout, setFout] = useState("");
  const [laadfase, setLaadfase] = useState<Laadfase>({ fase: "ophalen" });
  const [getekend, setGetekend] = useState<Getekend>();
  const [selectie, setSelectie] = useState<string | null>(doel.bron_iri);
  const [lagen, setLagen] = useState<Lagen>(STANDAARD_LAGEN);
  const [markering, setMarkering] = useState<MarkeringFilter>("alle");
  const [lagenOpen, setLagenOpen] = useState(false);
  const [aangeraakt, setAangeraakt] = useState(false);
  const [laadtBij, setLaadtBij] = useState("");
  const camera = useRef<CameraState | null>(null);
  const bediening = useRef<GraafBediening | null>(null);

  const laad = useCallback(async () => {
    setFout("");
    setLaadfase({ fase: "ophalen" });
    try {
      // Het doel van het paneel eerst; de andere doelen uit het antwoord in één verzoek (één bronboom
      // per regeling). Een doel dat niet laadt is een melding, geen fout voor het geheel.
      let geladen: Samenhang[];
      if (extraDoelen.length) {
        const { resultaten, fouten } = await haalSamenhangen([doel, ...extraDoelen]);
        const eigen = fouten.find((f) => f.bron_iri === doel.bron_iri);
        if (eigen || !resultaten.length) throw { status: 422, detail: eigen?.reden ?? "De samenhang is niet geladen." };
        geladen = resultaten;
        setNietGeladen(fouten.length);
      } else {
        geladen = [await haalSamenhang(doel)];
        setNietGeladen(0);
      }
      setBronnen(geladen.filter((d, i) => geladen.findIndex((x) => x.artikel_iri === d.artikel_iri) === i));
    } catch (e) { setFout(foutTekst(e, "De samenhang is niet geladen.")); }
  }, [doel, extraDoelen]);
  useEffect(() => {
    // Externe request initialiseren; dezelfde actie dient ook de retryknop.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    if (actief) void laad();
  }, [laad, actief]);

  const model = useMemo(() => bouwModel(bronnen ?? []), [bronnen]);

  // De layout volgt het model. Een vorige stand ligt vast: alleen nieuwe wettekst wordt geplaatst, en
  // na een annotatiewijziging wordt er niets gerekend (`layoutVoor`).
  const vorige = useRef<Posities | undefined>(undefined);
  useEffect(() => {
    if (!bronnen) return;
    const afbreken = new AbortController();
    layoutVoor(model, {
      vast: vorige.current,
      signal: afbreken.signal,
      opVoortgang: (fractie) => setLaadfase({ fase: "layout", fractie }),
    }).then(({ posities }) => {
      vorige.current = posities;
      setGetekend({ model, posities });
      setLaadfase({ fase: "klaar" });
    }).catch((e: unknown) => {
      if (afbreken.signal.aborted) return;
      setFout(foutTekst(e, "De layout van de graaf kon niet worden berekend."));
    });
    return () => afbreken.abort();
  }, [model, bronnen]);

  /** Na een annotatiewijziging: elk geladen deel opnieuw ophalen, per artikel vervangen. Selectie,
   *  lagen en camera blijven; de kaart verschuift niet. */
  const ververs = useCallback(async () => {
    if (!bronnen?.length) return;
    try {
      const nieuw = await Promise.all(bronnen.map((d) => haalSamenhang({ bron_iri: d.doel.bron_iri })));
      setBronnen((oud) => oud?.map((d) => nieuw.find((n) => n.artikel_iri === d.artikel_iri) ?? d));
    } catch (e) { setFout(foutTekst(e, "De graaf is niet bijgewerkt; herlaad om de laatste stand te zien.")); }
  }, [bronnen]);

  /** Een bepaling buiten wat geladen is erbij laden, als eigen deel. De kaart blijft liggen; alleen
   *  het nieuwe wordt geplaatst. */
  const laadErbij = useCallback(async (id: string) => {
    setLaadtBij(id);
    try {
      const nieuw = await haalSamenhang({ bron_iri: id });
      setBronnen((oud) => (oud?.some((d) => d.artikel_iri === nieuw.artikel_iri) ? oud : [...(oud ?? []), nieuw]));
    } catch (e) { setFout(foutTekst(e, "Deze bepaling kon niet worden bijgeladen.")); }
    finally { setLaadtBij(""); }
  }, []);

  return {
    bronnen, getekend, laadfase, nietGeladen, fout, setFout, laad, ververs, laadErbij, laadtBij,
    selectie, setSelectie, lagen, setLagen, markering, setMarkering, lagenOpen, setLagenOpen,
    aangeraakt, setAangeraakt, camera, bediening,
  };
}
export type GraafStand = ReturnType<typeof useGraafStand>;
