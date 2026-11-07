"use client";

import { useCallback, useEffect, useRef, useState } from "react";

import { Dialog } from "@/components/ui/Dialog";
import { GesprekSidebar } from "@/components/werkplek/GesprekSidebar";
import type { GesprekLijstStand } from "@/components/werkplek/GesprekLijst";
import type { GesprekRunStand } from "@/lib/runStanden";
import { foutTekst, hernoemGesprek, laadGesprekken, verwijderGesprek, wijzigGesprek } from "@/lib/api";
import { metSpoor } from "@/lib/uiSpoor";
import type { GesprekSamenvatting, Verbruiksstand } from "@/lib/types";

interface Props {
  /** Welk gesprek is actief (highlight). `null` op schermen buiten de chat. */
  activeId: string | null;
  onNieuw: () => void;
  /** Een nieuw gesprek dat bij dit werkgebied hoort. Weglaten verbergt de knop bij de groep. */
  onNieuwInWerkgebied?: (werkgebiedId: string) => void;
  onOpen: (id: string) => void;
  /** Een gesprek kreeg een ander werkgebied (of werd los) – de werkplek past zijn context aan. */
  onVerplaatst?: (id: string, werkgebiedId: string) => void;
  /** Het actieve gesprek is zojuist verwijderd – de aanroeper beslist wat er dan gebeurt. */
  onVerwijderd?: (id: string) => void;
  /** Hapering bij hernoemen/verwijderen. Wie de sidebar plaatst, bepaalt waar de melding landt. */
  onFout?: (melding: string) => void;
  /** De lijst zoals hij nu is – bv. om er een schermtitel uit af te leiden. */
  onLijst?: (gesprekken: GesprekSamenvatting[]) => void;
  /** Verhoog dit getal om de lijst opnieuw op te halen (bv. nadat een beurt een gesprek aanmaakte). */
  verversSignaal?: number;
  /** Mobiel: staat de off-canvas drawer open, en hoe sluit hij. */
  drawerOpen?: boolean;
  onDrawerSluit?: () => void;
  /** Start de rondleiding opnieuw (alleen de werkplek geeft dit mee). */
  onRondleiding?: () => void;
  /** De voorbeeldlijst van de rondleiding. Is die gezet, dan draait de sidebar als demo: de lijst
   *  komt hiervandaan en hernoemen/verwijderen blijven in dit geheugen – er gaat geen enkel verzoek
   *  naar de api. Zonder dit hing de rondleiding af van wat er in het account staat, en dat is bij
   *  een nieuwe gebruiker niets. */
  demoGesprekken?: GesprekSamenvatting[];
  /** Eigen verbruiksstand, doorgegeven aan het gebruikersblok onderin. */
  verbruik?: Verbruiksstand | null;
  /** Per gesprek de stip *Lex is bezig* of *Nieuw antwoord* (E6); alleen de werkplek geeft dit mee. */
  runStanden?: Record<string, GesprekRunStand>;
}

/** Zoveel gesprekken per keer; *Meer laden* vraagt de volgende pagina erbij. */
export const GESPREK_PAGINA = 100;

/** Wacht even na de laatste toets voor er gezocht wordt: niet bij elke letter een verzoek. */
const ZOEK_WACHT_MS = 250;

/** Een lijst die per pagina groeit (actief, archief of zoekresultaten). `null` = nog niet opgehaald. */
interface Pagina {
  lijst: GesprekSamenvatting[] | null;
  meer: boolean;
  aantal: number;
  laden: boolean;
  fout: string | null;
}
const LEGE_PAGINA: Pagina = { lijst: null, meer: false, aantal: GESPREK_PAGINA, laden: false, fout: null };

/** De gesprekssidebar met alles eromheen: laden, hernoemen, verwijderen, en de mobiele drawer.
 *
 *  Gedeeld door de werkplek en het annotatie-overzicht, zodat je bij het wisselen niet "uit de app"
 *  stapt – dat is wat Claude's artifacts-tab ook doet: de sidebar blijft, alleen het hoofdgebied
 *  verandert. De handlers verschillen wél per scherm: in de werkplek wisselt een klik van gesprek in
 *  lokale state, op het overzicht navigeert hij terug naar de werkplek. */
export function AppSidebar({
  activeId, onNieuw, onNieuwInWerkgebied, onOpen, onVerplaatst, onVerwijderd, onFout, onLijst, verversSignaal = 0,
  drawerOpen = false, onDrawerSluit, onRondleiding, demoGesprekken, verbruik = null, runStanden,
}: Props) {
  const [gesprekken, setGesprekken] = useState<GesprekSamenvatting[]>(demoGesprekken ?? []);
  const [laden, setLaden] = useState(!demoGesprekken);
  // Een mislukte lijst is iets anders dan een lege: anders staat er "Nog geen gesprekken" terwijl de api
  // alleen even niet antwoordde (acceptatie, 28 okt 2026).
  const [laadFout, setLaadFout] = useState<string | null>(null);
  // Actief en archief komen apart (UI-02): in één pagina samen duwde een groot archief de oudere actieve
  // gesprekken er stil uit. Het archief komt pas als je het opent; elke lijst heeft zijn eigen *Meer laden*.
  const [meer, setMeer] = useState(false);
  const [archiefOpen, setArchiefOpen] = useState(false);
  const [archief, setArchief] = useState<Pagina>(LEGE_PAGINA);
  // Zoeken in de eigen gesprekken (UI-03): server-side, over titel én berichttekst, actief en archief.
  const [zoekterm, setZoekterm] = useState("");
  const [zoek, setZoek] = useState<Pagina>(LEGE_PAGINA);
  const demo = Boolean(demoGesprekken);
  // Elke ophaalronde krijgt een nummer; alleen het antwoord van de laatste telt. De rondleiding
  // start bij een eerste bezoek vlak na het openen van de werkplek, terwijl de echte lijst nog
  // onderweg is. Kwam dat (lege) antwoord daarna binnen, dan overschreef het de voorbeeldlijst, en
  // wees "Je werk terugvinden" naar "Nog geen gesprekken".
  const ronde = useRef(0);
  const archiefRonde = useRef(0);
  const zoekRonde = useRef(0);
  // De handlers hieronder zijn stabiel; wat ze nodig hebben van de huidige stand lezen ze hieruit.
  // `aantal` (hoeveel actieve gesprekken er geladen zijn) verandert alleen in `meerActief`.
  const stand = useRef({ aantal: GESPREK_PAGINA, archiefOpen, archiefAantal: GESPREK_PAGINA, zoekterm, zoekAantal: GESPREK_PAGINA });
  useEffect(() => {
    stand.current = { ...stand.current, archiefOpen, archiefAantal: archief.aantal, zoekterm, zoekAantal: zoek.aantal };
  }, [archiefOpen, archief.aantal, zoekterm, zoek.aantal]);
  useEffect(() => {
    if (demo) ronde.current++;
  }, [demo]);

  // De aanroeper (de werkplek leidt er de titel en het werkgebied van het open gesprek uit af) krijgt
  // alles wat de sidebar kent: ook een gesprek dat je uit het archief of uit een zoekresultaat opende.
  const onLijstRef = useRef(onLijst);
  useEffect(() => {
    onLijstRef.current = onLijst;
  }, [onLijst]);
  useEffect(() => {
    if (demo) return;
    const gezien = new Set<string>();
    const alle = [...gesprekken, ...(archief.lijst ?? []), ...(zoek.lijst ?? [])]
      .filter((g) => !gezien.has(g.id) && Boolean(gezien.add(g.id)));
    onLijstRef.current?.(alle);
  }, [demo, gesprekken, archief.lijst, zoek.lijst]);

  const haalArchief = useCallback((aantal: number) => {
    const deze = ++archiefRonde.current;
    setArchief((a) => ({ ...a, aantal, laden: true }));
    laadGesprekken({ gearchiveerd: true }, aantal)
      .then(({ lijst, meer }) => {
        if (deze === archiefRonde.current) setArchief({ lijst, meer, aantal, laden: false, fout: null });
      })
      .catch((e) => {
        if (deze === archiefRonde.current)
          setArchief((a) => ({ ...a, laden: false, fout: foutTekst(e, "Het archief kon niet geladen worden.") }));
      });
  }, []);

  const haalZoek = useCallback((term: string, aantal: number) => {
    const deze = ++zoekRonde.current;
    setZoek((z) => ({ ...z, aantal, laden: true }));
    laadGesprekken({ q: term }, aantal)
      .then(({ lijst, meer }) => {
        if (deze === zoekRonde.current) setZoek({ lijst, meer, aantal, laden: false, fout: null });
      })
      .catch((e) => {
        if (deze === zoekRonde.current)
          setZoek((z) => ({ ...z, laden: false, fout: foutTekst(e, "Zoeken lukte niet.") }));
      });
  }, []);

  const verversLijst = useCallback(() => {
    // In de rondleiding is deze lijst een voorbeeld; ophalen zou hem overschrijven met de (vaak
    // lege) echte lijst.
    if (demo) return;
    const deze = ++ronde.current;
    laadGesprekken({ gearchiveerd: false }, stand.current.aantal)
      .then(({ lijst, meer }) => {
        if (deze !== ronde.current) return;
        setGesprekken(lijst);
        setMeer(meer);
        setLaadFout(null);
      })
      .catch((e) => {
        if (deze === ronde.current) setLaadFout(foutTekst(e, "De gesprekken konden niet geladen worden."));
      })
      .finally(() => setLaden(false));
    // Wat openstaat, blijft kloppen na een handeling (archiveren, herstellen, hernoemen).
    if (stand.current.archiefOpen) haalArchief(stand.current.archiefAantal);
    if (stand.current.zoekterm.trim()) haalZoek(stand.current.zoekterm.trim(), stand.current.zoekAantal);
  }, [demo, haalArchief, haalZoek]);

  useEffect(() => {
    verversLijst();
  }, [verversLijst, verversSignaal]);

  function meerActief() {
    stand.current.aantal += GESPREK_PAGINA;
    setLaden(true);
    verversLijst();
  }

  function wisselArchief() {
    const open = !archiefOpen;
    setArchiefOpen(open);
    if (open && !demo) haalArchief(archief.aantal);
  }

  const meerArchief = () => haalArchief(archief.aantal + GESPREK_PAGINA);
  const meerZoek = () => haalZoek(zoekterm.trim(), zoek.aantal + GESPREK_PAGINA);

  /** Een handeling (hernoemen, archiveren, verplaatsen, verwijderen) is meteen zichtbaar in elke lijst
   *  waar het gesprek staat; `herstel` zet ze bij een fout terug. */
  function pasAan(f: (lijst: GesprekSamenvatting[]) => GesprekSamenvatting[]): () => void {
    const vorige = { gesprekken, archief, zoek };
    setGesprekken(f);
    setArchief((a) => (a.lijst ? { ...a, lijst: f(a.lijst) } : a));
    setZoek((z) => (z.lijst ? { ...z, lijst: f(z.lijst) } : z));
    return () => {
      setGesprekken(vorige.gesprekken);
      setArchief(vorige.archief);
      setZoek(vorige.zoek);
    };
  }

  /** Een lege term zet de gewone lijst terug; een antwoord dat nog onderweg is, telt dan niet meer. */
  function zetZoekterm(term: string) {
    setZoekterm(term);
    if (!term.trim()) {
      zoekRonde.current++;
      setZoek(LEGE_PAGINA);
    }
  }

  // Zoeken pas na een korte pauze in het typen.
  useEffect(() => {
    const term = zoekterm.trim();
    if (demo || !term) return;
    const t = window.setTimeout(() => haalZoek(term, GESPREK_PAGINA), ZOEK_WACHT_MS);
    return () => window.clearTimeout(t);
  }, [zoekterm, demo, haalZoek]);

  // De rondleiding kan tussentijds starten of stoppen. Dat bijstellen hoort in de render en niet in
  // een effect: anders rendert de sidebar eerst één frame met de vórige lijst – bij het starten dus
  // met de (vaak lege) echte lijst waar de rondleiding juist omheen werkt.
  const [vorigeDemo, setVorigeDemo] = useState(demoGesprekken);
  if (demoGesprekken !== vorigeDemo) {
    setVorigeDemo(demoGesprekken);
    if (demoGesprekken) setGesprekken(demoGesprekken);
  }

  async function hernoem(id: string, titel: string) {
    if (demo) {
      setGesprekken((lijst) => lijst.map((g) => (g.id === id ? { ...g, titel } : g)));
      return;
    }
    try {
      await metSpoor("gesprek_hernoemen", () => hernoemGesprek(id, titel));
      verversLijst();
    } catch {
      onFout?.("De nieuwe naam is niet opgeslagen.");
    }
  }

  /** De bevestiging zit in de knop zelf (`BevestigKnop`, twee klikken) – hetzelfde gebaar als in het
   *  artefact; geen `window.confirm` midden in een app met een eigen vormtaal.
   *
   *  **De rij gaat meteen weg en komt bij een fout terug.** Dat stond andersom: eerst de call, dan
   *  pas de rij. Die volgorde geeft het voordeel van optimistisch bijwerken juist weg — en de call
   *  duurt op acceptatie soms lang (de BFF belt drie diensten, waarvan twee vanuit een koude start).
   *  Tot die terugkwam gebeurde er zichtbaar niets, en dat is niet te onderscheiden van een klik die
   *  niet is aangekomen. */
  async function verwijder(id: string) {
    if (demo) {
      setGesprekken((lijst) => lijst.filter((g) => g.id !== id));
      return;
    }
    const herstel = pasAan((lijst) => lijst.filter((g) => g.id !== id));
    try {
      await metSpoor("gesprek_verwijderen", () => verwijderGesprek(id));
      onVerwijderd?.(id);
      verversLijst();
    } catch {
      herstel();
      onFout?.("Het gesprek is niet verwijderd.");
    }
  }

  /** Archiveren en verplaatsen zijn, net als verwijderen, meteen zichtbaar en worden bij een fout
   *  teruggezet. De werkgebiednaam komt bij het verversen van de api. */
  async function wijzig(
    id: string,
    wijziging: { werkgebied_id?: string; gearchiveerd?: boolean },
    actie: "gesprek_archiveren" | "gesprek_verplaatsen",
    melding: string,
  ) {
    const lokaal = (g: GesprekSamenvatting): GesprekSamenvatting => ({
      ...g,
      ...(wijziging.werkgebied_id !== undefined && { werkgebied_id: wijziging.werkgebied_id }),
      ...(wijziging.gearchiveerd !== undefined && { gearchiveerd: wijziging.gearchiveerd ? new Date().toISOString() : null }),
    });
    if (demo) {
      setGesprekken((lijst) => lijst.map((g) => (g.id === id ? lokaal(g) : g)));
      return;
    }
    const herstel = pasAan((lijst) => lijst.map((g) => (g.id === id ? lokaal(g) : g)));
    try {
      await metSpoor(actie, () => wijzigGesprek(id, wijziging));
      if (wijziging.werkgebied_id !== undefined) onVerplaatst?.(id, wijziging.werkgebied_id);
      verversLijst();
    } catch {
      herstel();
      onFout?.(melding);
    }
  }

  const archiveer = (id: string, gearchiveerd: boolean) =>
    wijzig(id, { gearchiveerd }, "gesprek_archiveren",
      gearchiveerd ? "Het gesprek is niet gearchiveerd." : "Het gesprek is niet hersteld.");
  const verplaats = (id: string, werkgebiedId: string) =>
    wijzig(id, { werkgebied_id: werkgebiedId }, "gesprek_verplaatsen", "Het gesprek is niet verplaatst.");

  // Wordt het scherm breed genoeg voor de vaste sidebar terwijl de drawer openstaat, dan is die
  // drawer onzichtbaar (`lg:hidden`) maar nog wél modaal – met een focus-trap op knoppen die je niet
  // ziet. Dan sluiten we hem; 1024px is Tailwinds `lg`.
  useEffect(() => {
    if (!drawerOpen || !onDrawerSluit) return;
    const mq = window.matchMedia("(min-width: 1024px)");
    const opWijziging = () => { if (mq.matches) onDrawerSluit(); };
    opWijziging();
    mq.addEventListener("change", opWijziging);
    return () => mq.removeEventListener("change", opWijziging);
  }, [drawerOpen, onDrawerSluit]);

  // In de rondleiding is er geen zoekveld en geen apart archief: de voorbeeldlijst is alles.
  const lijstStand: GesprekLijstStand | undefined = demo ? undefined : {
    meer,
    onMeer: meerActief,
    archief: { open: archiefOpen, onWissel: wisselArchief, ...archief, onMeer: meerArchief },
    zoek: { term: zoekterm, onTerm: zetZoekterm, ...zoek, onMeer: meerZoek },
    runStanden,
  };

  const inhoud = (extra?: { onSluit: () => void }) => (
    <GesprekSidebar
      gesprekken={gesprekken}
      stand={lijstStand}
      activeId={activeId}
      onNieuw={onNieuw}
      onOpen={onOpen}
      onHernoem={hernoem}
      onVerwijder={verwijder}
      onArchiveer={archiveer}
      onVerplaats={verplaats}
      onNieuwInWerkgebied={onNieuwInWerkgebied}
      laden={laden}
      laadFout={laadFout}
      onOpnieuw={() => {
        setLaden(true);
        verversLijst();
      }}
      onSluit={extra?.onSluit}
      onRondleiding={onRondleiding}
      verbruik={verbruik}
    />
  );

  return (
    <>
      <aside data-tour="sidebar" className="hidden w-[17rem] shrink-0 border-r border-line lg:block">{inhoud()}</aside>

      {/* Mobiele off-canvas drawer. Via `Dialog` en niet als eigen constructie: die draagt de
          focus-trap, Escape en de backdrop. */}
      {drawerOpen && onDrawerSluit && (
        <Dialog
          label="Gesprekken"
          variant="drawer"
          wrapperClassName="lg:hidden"
          onSluit={onDrawerSluit}
        >
          {inhoud({ onSluit: onDrawerSluit })}
        </Dialog>
      )}
    </>
  );
}
