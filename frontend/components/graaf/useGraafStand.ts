"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import type { CameraState } from "sigma/types";
import { foutTekst } from "@/lib/api";
import type { NodeDoel } from "@/lib/annotatieNode";
import type { Posities } from "@/lib/graaf/layout";
import { haalKennisgraaf } from "@/lib/graaf/data";
import { bouwModel, type GraafBron, type GraafModel, type KennisgraafAntwoord } from "@/lib/graaf/model";
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
export interface GraafOpties {
  bereik?: Bereik;
  focus?: readonly string[];
  /** De kennisgraaf die het vorige paneel al had ("Open in het paneel" remount het paneel). Alleen
   *  een actuele: wie hem doorgeeft, garandeert dat er sindsdien geen annotatie veranderde
   *  (`kennisgraafActueel`). */
  kennisgraaf?: KennisgraafAntwoord;
}

/** Wat het tekenen tegenhoudt, per bron, met de handeling die het herstelt. Een fout geldt in het
 *  bereik waar hij optrad: een kennisgraaf die niet laadde, zegt niets over *Dit antwoord*. */
interface Laadfouten {
  samenhang?: string;
  kennisgraaf?: string;
  layout?: { bereik: Bereik; tekst: string };
}

/** Een fout die de graaf in dit bereik blokkeert, met *Opnieuw proberen*. */
export interface GraafFout { tekst: string; herstel: () => void }

/** De toestand van de graaf. Leeft in het paneel (búiten de `Dialog`): vergroten wisselt de
 *  dialoogvorm en remount daarmee de inhoud; zonder dit waren bijgeladen artikelen, selectie, lagen en
 *  camera dan weg. `actief` laadt pas als de tab voor het eerst opengaat; `zichtbaar` = de tab staat
 *  open (verversen wacht daarop). */
export function useGraafStand(doel: NodeDoel, actief: boolean, zichtbaar: boolean, extra: NodeDoel[] = [],
  opties: GraafOpties = {},
  /** Knopen en relaties die niet uit de graaf komen maar erbij horen: de begrippen van een werkgebied
   *  (tab Samenhang, fase F3). Een nieuwe toevoeging bouwt het model opnieuw; de wettekst blijft liggen
   *  en de begrippen worden afgeleid geplaatst, dus er wordt niets gerekend. Stabiel houden (memo). */
  toevoeging?: GraafBron) {
  // Een nieuwe array met dezelfde doelen mag niet opnieuw laden: vergelijk op de bron-IRI's.
  const extraSleutel = extra.map((d) => d.bron_iri).join("|");
  // eslint-disable-next-line react-hooks/exhaustive-deps
  const extraDoelen = useMemo(() => extra, [extraSleutel]);
  // Wat het antwoord noemt: expliciet (een overzicht: al zijn delen en bepalingen, zonder grens), anders
  // de doelen zelf.
  const focusSleutel = (opties.focus ?? [doel.bron_iri, ...extraDoelen.map((d) => d.bron_iri)]).join("|");
  const focusIds = useMemo(() => focusSleutel.split("|").filter(Boolean), [focusSleutel]);
  const [bereik, setBereik] = useState<Bereik>(opties.bereik ?? "antwoord");
  const [kennisgraaf, setKennisgraaf] = useState<KennisgraafAntwoord | undefined>(opties.kennisgraaf);
  const [bronnen, setBronnen] = useState<Samenhang[]>();
  const [nietGeladen, setNietGeladen] = useState(0);
  const [fouten, setFouten] = useState<Laadfouten>({});
  // Wat niet blokkeert (verversen of bijladen mislukt): staat tot de volgende geslaagde handeling.
  const [melding, setMelding] = useState("");
  const [laadfase, setLaadfase] = useState<Laadfase>({ fase: "ophalen" });
  const [getekend, setGetekend] = useState<Getekend>();
  // Geen beginkeuze: het begin is de focus (wat het antwoord noemt). Een keuze is wat je daarna
  // aanklikt, en haar opheffen brengt het begin terug.
  const [selectie, setSelectie] = useState<string | null>(null);
  // Een keuze voor een knoop die nog niet op de kaart staat (het overzichtsblok wijst iets uit de
  // kennisgraaf aan terwijl die nog laadt). `Graaf` maakt er een echte keuze van zodra hij er is.
  const [wachtendeKeuze, setWachtendeKeuze] = useState<string | null>(null);
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
  // Telt op bij elke verversing: de inspector haalt de tekst van de gekozen knoop dan opnieuw op.
  const [detailVersie, setDetailVersie] = useState(0);
  const levend = useRef(true);
  // Ook bij de tweede montage van StrictMode weer aan: die doet eerst een cleanup.
  useEffect(() => {
    levend.current = true;
    return () => { levend.current = false; };
  }, []);

  // Verversen is een toestand, geen handeling: `gevraagd` telt de annotatiewijzigingen, `gedaan` tot
  // waar de geladen data bij is. Zie `ververs` hieronder.
  const gevraagdRef = useRef(0);
  const [gevraagd, setGevraagd] = useState(0);
  const [gedaan, setGedaan] = useState(0);
  const bijTot = useCallback((ronde: number) => setGedaan((g) => Math.max(g, ronde)), []);

  const laad = useCallback(async () => {
    const ronde = gevraagdRef.current;
    setFouten((f) => ({ ...f, samenhang: undefined }));
    setLaadfase({ fase: "ophalen" });
    try {
      // Het doel van het paneel eerst; de andere doelen uit het antwoord in één verzoek (één bronboom
      // per regeling). Een doel dat niet laadt is een melding, geen fout voor het geheel – behalve het
      // doel van het paneel zelf.
      const { resultaten, fouten: nietGelukt } = extraDoelen.length
        ? await haalSamenhangen([doel, ...extraDoelen])
        : { resultaten: [await haalSamenhang(doel)], fouten: [] };
      const eigen = nietGelukt.find((f) => f.bron_iri === doel.bron_iri);
      if (eigen || !resultaten.length) {
        setFouten((f) => ({ ...f, samenhang: eigen?.reden ?? "De samenhang is niet geladen." }));
        return;
      }
      setNietGeladen(nietGelukt.length);
      setBronnen(resultaten.filter((d, i) => resultaten.findIndex((x) => x.artikel_iri === d.artikel_iri) === i));
      bijTot(ronde);
    } catch (e) { setFouten((f) => ({ ...f, samenhang: foutTekst(e, "De samenhang is niet geladen.") })); }
  }, [doel, extraDoelen, bijTot]);
  useEffect(() => {
    // Externe request initialiseren; dezelfde actie dient ook de retryknop.
    if (actief) void laad();
  }, [laad, actief]);

  /** De hele kennisgraaf (`/graaf`), één keer per paneel; opnieuw na een annotatiewijziging, want de
   *  markeringen erin komen vers uit de api. */
  const laadKennisgraaf = useCallback(async () => {
    setFouten((f) => ({ ...f, kennisgraaf: undefined }));
    setLaadfase({ fase: "ophalen" });
    try { setKennisgraaf(await haalKennisgraaf()); }
    catch (e) { setFouten((f) => ({ ...f, kennisgraaf: foutTekst(e, "De kennisgraaf is niet geladen.") })); }
  }, []);
  const kennisgraafGevraagd = useRef(!!opties.kennisgraaf);
  useEffect(() => {
    if (!actief || bereik !== "kennisgraaf" || kennisgraafGevraagd.current) return;
    kennisgraafGevraagd.current = true;
    // Externe request initialiseren, één keer; een fout herstelt de knop "Opnieuw proberen".
    void laadKennisgraaf();
  }, [actief, bereik, laadKennisgraaf]);

  // In de kennisgraaf komen de geladen samenhangen eerst: die dragen de wettekst van wat het antwoord
  // noemt, en een knoop houdt bij het samenvoegen de gegevens van het eerste antwoord dat hem levert.
  const model = useMemo(() => {
    const extraBron = toevoeging ? [toevoeging] : [];
    return bereik === "kennisgraaf"
      ? (kennisgraaf && bronnen ? bouwModel([...bronnen, kennisgraaf, ...extraBron]) : undefined)
      : (bronnen ? bouwModel([...bronnen, ...extraBron]) : undefined);
  }, [bereik, bronnen, kennisgraaf, toevoeging]);

  // De layout volgt het model, per bereik een eigen kaart. Een vorige stand van hetzelfde bereik ligt
  // vast: alleen nieuwe wettekst wordt geplaatst, en na een annotatiewijziging wordt er niets gerekend
  // (`layoutVoor`). De eerste kaart van een bereik komt uit de cache of wordt gerekend.
  const vorige = useRef<Partial<Record<Bereik, Posities>>>({});
  const [layoutPoging, setLayoutPoging] = useState(0);
  useEffect(() => {
    if (!model) return;
    const afbreken = new AbortController();
    const voor = bereik;
    layoutVoor(model, {
      vast: vorige.current[voor],
      signal: afbreken.signal,
      opVoortgang: (fractie) => setLaadfase({ fase: "layout", fractie }),
    }).then(({ posities }) => {
      // Een vervallen run (nieuw model, ander bereik) zet niets: anders komt een oude kaart over een
      // nieuwere heen.
      if (afbreken.signal.aborted) return;
      vorige.current[voor] = posities;
      setGetekend({ model, posities, bereik: voor });
      setLaadfase({ fase: "klaar" });
      setFouten((f) => (f.layout?.bereik === voor ? { ...f, layout: undefined } : f));
    }).catch((e: unknown) => {
      if (afbreken.signal.aborted) return;
      setFouten((f) => ({ ...f, layout: { bereik: voor, tekst: foutTekst(e, "De layout van de graaf kon niet worden berekend.") } }));
    });
    return () => afbreken.abort();
  }, [model, bereik, layoutPoging]);

  /** Na een annotatiewijziging. Mutaties gebeuren op de Tekst-tab, dus de graaf is dan niet te zien:
   *  er wordt alleen genoteerd dát hij achterloopt. Ophalen gebeurt pas als hij zichtbaar is (het
   *  effect hieronder) – één ronde, hoeveel beoordelingen er ook tussen zaten. */
  const ververs = useCallback(() => {
    gevraagdRef.current += 1;
    setGevraagd(gevraagdRef.current);
  }, []);

  // Eén verversing tegelijk, dus antwoorden komen nooit in de verkeerde volgorde binnen. Kwam er
  // tijdens een ronde nog een wijziging bij, dan volgt er daarna precies één.
  const bezig = useRef(false);
  useEffect(() => {
    if (!zichtbaar || gevraagd <= gedaan || bezig.current || !bronnen?.length) return;
    bezig.current = true;
    const ronde = gevraagdRef.current;
    const doelen = bronnen.map((d) => d.doel);
    const metKennisgraaf = !!kennisgraaf;
    void (async () => {
      // De markeringen in de opgehaalde teksten kunnen veranderd zijn.
      detailCache.current = new Map();
      setDetailVersie((v) => v + 1);
      try {
        const [{ resultaten }, kg] = await Promise.all([
          haalSamenhangen(doelen),
          metKennisgraaf ? haalKennisgraaf() : Promise.resolve(undefined),
        ]);
        if (!levend.current) return;
        setBronnen((oud) => oud?.map((d) => resultaten.find((n) => n.artikel_iri === d.artikel_iri) ?? d));
        if (kg) setKennisgraaf(kg);
        setMelding("");
      } catch (e) {
        if (levend.current) setMelding(foutTekst(e, "De graaf is niet bijgewerkt; herlaad om de laatste stand te zien."));
      } finally {
        bezig.current = false;
        // Ook na een fout: anders probeert hij het eindeloos. De volgende wijziging probeert opnieuw.
        if (levend.current) bijTot(ronde);
      }
    })();
  }, [zichtbaar, gevraagd, gedaan, bronnen, kennisgraaf, bijTot]);

  /** Een bepaling buiten wat geladen is erbij laden, als eigen deel. De kaart blijft liggen; alleen
   *  het nieuwe wordt geplaatst. */
  const laadErbij = useCallback(async (id: string) => {
    setLaadtBij(id);
    try {
      const nieuw = await haalSamenhang({ bron_iri: id });
      setBronnen((oud) => (oud?.some((d) => d.artikel_iri === nieuw.artikel_iri) ? oud : [...(oud ?? []), nieuw]));
      setMelding("");
    } catch (e) { setMelding(foutTekst(e, "Deze bepaling kon niet worden bijgeladen.")); }
    finally { setLaadtBij(""); }
  }, []);

  // De fout die in dit bereik het tekenen tegenhoudt, met de handeling die hem herstelt.
  const herberekenLayout = useCallback(() => setLayoutPoging((n) => n + 1), []);
  const fout: GraafFout | null = fouten.samenhang ? { tekst: fouten.samenhang, herstel: () => void laad() }
    : bereik === "kennisgraaf" && fouten.kennisgraaf ? { tekst: fouten.kennisgraaf, herstel: () => void laadKennisgraaf() }
      : fouten.layout?.bereik === bereik ? { tekst: fouten.layout.tekst, herstel: herberekenLayout }
        : null;

  return {
    bronnen, getekend, laadfase, nietGeladen, fout, melding, ververs, laadErbij, laadtBij,
    bereik, setBereik, focusIds,
    /** De geladen kennisgraaf, als er sinds het laden geen annotatie veranderde: die mag een volgend
     *  paneel overnemen (`GraafOpties.kennisgraaf`). */
    kennisgraafActueel: gevraagd <= gedaan ? kennisgraaf : undefined,
    selectie, setSelectie, wachtendeKeuze, setWachtendeKeuze,
    lagen, setLagen, markering, setMarkering, lagenOpen, setLagenOpen,
    aangeraakt, setAangeraakt, camera, bediening, detailCache, infoCache, detailVersie,
  };
}
export type GraafStand = ReturnType<typeof useGraafStand>;
