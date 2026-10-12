"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import type { CameraState } from "sigma/types";
import { foutTekst } from "@/lib/api";
import type { NodeDoel } from "@/lib/annotatieNode";
import type { Posities } from "@/lib/graaf/layout";
import { haalKennisgraaf } from "@/lib/graaf/data";
import { bouwModel, type GraafModel, type KennisgraafAntwoord } from "@/lib/graaf/model";
import { layoutVoor } from "@/lib/graaf/rekenaar";
import { STANDAARD_LAGEN, type Lagen } from "@/lib/graaf/weergave";
import { haalSamenhang, haalSamenhangen, type MarkeringFilter, type Samenhang } from "@/lib/samenhang";
import type { GraafBediening } from "./GraafTekenaar";
import type { DetailCache, InfoCache } from "./useKnoopDetail";

/** Waar het laden is: de data ophalen (duur onbekend), de layout rekenen (met voortgang), klaar. */
export type Laadfase = { fase: "ophalen" } | { fase: "layout"; fractie: number } | { fase: "klaar" };

/** Wat de graaf laat zien: wat het antwoord noemt (de samenhang van die bepalingen of delen), of de
 *  hele kennisgraaf met de nadruk op wat het antwoord noemt. */
export type Bereik = "antwoord" | "kennisgraaf";

/** Wat er getekend wordt: een model mét de posities die erbij horen, en het bereik waarvoor ze gelden.
 *  Ze worden samen vervangen, zodat er nooit een beeld is met knopen zonder plek. */
export interface Getekend { model: GraafModel; posities: Posities; bereik: Bereik }

/** Hoe de graaf opent: met welk bereik, en wat in de kennisgraaf de nadruk krijgt (zonder: de doelen). */
export interface GraafOpties { bereik?: Bereik; focus?: readonly string[] }

/** De toestand van de graaf. Leeft in het paneel (búiten de `Dialog`): vergroten wisselt de
 *  dialoogvorm en remount daarmee de inhoud; zonder dit waren bijgeladen artikelen, selectie, lagen en
 *  camera dan weg. `actief` laadt pas als de tab voor het eerst opengaat. */
export function useGraafStand(doel: NodeDoel, actief: boolean, extra: NodeDoel[] = [],
  opties: GraafOpties = {}) {
  // Een nieuwe array met dezelfde doelen mag niet opnieuw laden: vergelijk op de bron-IRI's.
  const extraSleutel = extra.map((d) => d.bron_iri).join("|");
  // eslint-disable-next-line react-hooks/exhaustive-deps
  const extraDoelen = useMemo(() => extra, [extraSleutel]);
  // Wat het antwoord noemt: expliciet (een overzicht: al zijn delen en bepalingen, zonder grens), anders
  // de doelen zelf.
  const focusSleutel = (opties.focus ?? [doel.bron_iri, ...extraDoelen.map((d) => d.bron_iri)]).join("|");
  const focusIds = useMemo(() => focusSleutel.split("|").filter(Boolean), [focusSleutel]);
  const [bereik, setBereik] = useState<Bereik>(opties.bereik ?? "antwoord");
  const [kennisgraaf, setKennisgraaf] = useState<KennisgraafAntwoord>();
  const [bronnen, setBronnen] = useState<Samenhang[]>();
  const [nietGeladen, setNietGeladen] = useState(0);
  const [fout, setFout] = useState("");
  const [laadfase, setLaadfase] = useState<Laadfase>({ fase: "ophalen" });
  const [getekend, setGetekend] = useState<Getekend>();
  // Geen beginkeuze: het begin is de focus (wat het antwoord noemt). Een keuze is wat je daarna
  // aanklikt, en haar opheffen brengt het begin terug.
  const [selectie, setSelectie] = useState<string | null>(null);
  const [lagen, setLagen] = useState<Lagen>(STANDAARD_LAGEN);
  const [markering, setMarkering] = useState<MarkeringFilter>("alle");
  const [lagenOpen, setLagenOpen] = useState(false);
  const [aangeraakt, setAangeraakt] = useState(false);
  const [laadtBij, setLaadtBij] = useState("");
  const camera = useRef<CameraState | null>(null);
  const bediening = useRef<GraafBediening | null>(null);
  // De tekst van gekozen bepalingen voor de inspector, per paneel één keer opgehaald (`useKnoopDetail`).
  const detailCache = useRef<DetailCache>(new Map());
  const infoCache = useRef<InfoCache>(new Map());
  // Telt op bij elke `ververs`: de inspector haalt de tekst van de gekozen knoop dan opnieuw op.
  const [detailVersie, setDetailVersie] = useState(0);

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

  /** De hele kennisgraaf (`/graaf`), één keer per paneel; opnieuw na een annotatiewijziging, want de
   *  markeringen erin komen vers uit de api. */
  const laadKennisgraaf = useCallback(async () => {
    setFout("");
    setLaadfase({ fase: "ophalen" });
    try { setKennisgraaf(await haalKennisgraaf()); }
    catch (e) { setFout(foutTekst(e, "De kennisgraaf is niet geladen.")); }
  }, []);
  const kennisgraafGevraagd = useRef(false);
  useEffect(() => {
    if (!actief || bereik !== "kennisgraaf" || kennisgraafGevraagd.current) return;
    kennisgraafGevraagd.current = true;
    // Externe request initialiseren, één keer; een fout herstelt de knop "Opnieuw proberen".
    void laadKennisgraaf();
  }, [actief, bereik, laadKennisgraaf]);

  // In de kennisgraaf komen de geladen samenhangen eerst: die dragen de wettekst van wat het antwoord
  // noemt, en een knoop houdt bij het samenvoegen de gegevens van het eerste antwoord dat hem levert.
  const model = useMemo(() => bereik === "kennisgraaf"
    ? (kennisgraaf && bronnen ? bouwModel([...bronnen, kennisgraaf]) : undefined)
    : (bronnen ? bouwModel(bronnen) : undefined), [bereik, bronnen, kennisgraaf]);

  // De layout volgt het model, per bereik een eigen kaart. Een vorige stand van hetzelfde bereik ligt
  // vast: alleen nieuwe wettekst wordt geplaatst, en na een annotatiewijziging wordt er niets gerekend
  // (`layoutVoor`). De hele kennisgraaf begint altijd vers – dan komt hij uit de cache.
  const vorige = useRef<Partial<Record<Bereik, Posities>>>({});
  useEffect(() => {
    if (!model) return;
    const afbreken = new AbortController();
    const voor = bereik;
    layoutVoor(model, {
      vast: vorige.current[voor],
      signal: afbreken.signal,
      opVoortgang: (fractie) => setLaadfase({ fase: "layout", fractie }),
    }).then(({ posities }) => {
      vorige.current[voor] = posities;
      setGetekend({ model, posities, bereik: voor });
      setLaadfase({ fase: "klaar" });
    }).catch((e: unknown) => {
      if (afbreken.signal.aborted) return;
      setFout(foutTekst(e, "De layout van de graaf kon niet worden berekend."));
    });
    return () => afbreken.abort();
  }, [model, bereik]);

  /** Na een annotatiewijziging: elk geladen deel opnieuw ophalen, per artikel vervangen. Selectie,
   *  lagen en camera blijven; de kaart verschuift niet. */
  const ververs = useCallback(async () => {
    if (!bronnen?.length) return;
    // De markeringen in de opgehaalde teksten kunnen veranderd zijn.
    detailCache.current = new Map();
    setDetailVersie((v) => v + 1);
    try {
      const [nieuw, kg] = await Promise.all([
        Promise.all(bronnen.map((d) => haalSamenhang({ bron_iri: d.doel.bron_iri }))),
        kennisgraaf ? haalKennisgraaf() : Promise.resolve(undefined),
      ]);
      setBronnen((oud) => oud?.map((d) => nieuw.find((n) => n.artikel_iri === d.artikel_iri) ?? d));
      if (kg) setKennisgraaf(kg);
    } catch (e) { setFout(foutTekst(e, "De graaf is niet bijgewerkt; herlaad om de laatste stand te zien.")); }
  }, [bronnen, kennisgraaf]);

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
    bereik, setBereik, focusIds, kennisgraaf, laadKennisgraaf,
    selectie, setSelectie, lagen, setLagen, markering, setMarkering, lagenOpen, setLagenOpen,
    aangeraakt, setAangeraakt, camera, bediening, detailCache, infoCache, detailVersie,
  };
}
export type GraafStand = ReturnType<typeof useGraafStand>;
