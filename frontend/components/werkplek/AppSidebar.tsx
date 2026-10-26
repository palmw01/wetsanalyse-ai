"use client";

import { useCallback, useEffect, useRef, useState } from "react";

import { Dialog } from "@/components/ui/Dialog";
import { GesprekSidebar } from "@/components/werkplek/GesprekSidebar";
import { hernoemGesprek, lijstGesprekken, verwijderGesprek, wijzigGesprek } from "@/lib/api";
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
}

/** De gesprekssidebar met alles eromheen: laden, hernoemen, verwijderen, en de mobiele drawer.
 *
 *  Gedeeld door de werkplek en het annotatie-overzicht, zodat je bij het wisselen niet "uit de app"
 *  stapt – dat is wat Claude's artifacts-tab ook doet: de sidebar blijft, alleen het hoofdgebied
 *  verandert. De handlers verschillen wél per scherm: in de werkplek wisselt een klik van gesprek in
 *  lokale state, op het overzicht navigeert hij terug naar de werkplek. */
export function AppSidebar({
  activeId, onNieuw, onNieuwInWerkgebied, onOpen, onVerplaatst, onVerwijderd, onFout, onLijst, verversSignaal = 0,
  drawerOpen = false, onDrawerSluit, onRondleiding, demoGesprekken, verbruik = null,
}: Props) {
  const [gesprekken, setGesprekken] = useState<GesprekSamenvatting[]>(demoGesprekken ?? []);
  const [laden, setLaden] = useState(!demoGesprekken);
  const demo = Boolean(demoGesprekken);
  // Elke ophaalronde krijgt een nummer; alleen het antwoord van de laatste telt. De rondleiding
  // start bij een eerste bezoek vlak na het openen van de werkplek, terwijl de echte lijst nog
  // onderweg is. Kwam dat (lege) antwoord daarna binnen, dan overschreef het de voorbeeldlijst, en
  // wees "Je werk terugvinden" naar "Nog geen gesprekken".
  const ronde = useRef(0);
  useEffect(() => {
    if (demo) ronde.current++;
  }, [demo]);

  const verversLijst = useCallback(() => {
    // In de rondleiding is deze lijst een voorbeeld; ophalen zou hem overschrijven met de (vaak
    // lege) echte lijst.
    if (demo) return;
    const deze = ++ronde.current;
    lijstGesprekken()
      .then((lijst) => {
        if (deze !== ronde.current) return;
        setGesprekken(lijst);
        onLijst?.(lijst);
      })
      .catch(() => {})
      .finally(() => setLaden(false));
    // `onLijst` bewust buiten de deps: het is vaak een inline callback en zou de fetch anders bij
    // elke render opnieuw laten lopen.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [demo]);

  useEffect(() => {
    verversLijst();
  }, [verversLijst, verversSignaal]);

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
    const vorige = gesprekken;
    setGesprekken((lijst) => lijst.filter((g) => g.id !== id));
    try {
      await metSpoor("gesprek_verwijderen", () => verwijderGesprek(id));
      onVerwijderd?.(id);
      verversLijst();
    } catch {
      setGesprekken(vorige);
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
    const vorige = gesprekken;
    setGesprekken((lijst) => lijst.map((g) => (g.id === id ? lokaal(g) : g)));
    try {
      await metSpoor(actie, () => wijzigGesprek(id, wijziging));
      if (wijziging.werkgebied_id !== undefined) onVerplaatst?.(id, wijziging.werkgebied_id);
      verversLijst();
    } catch {
      setGesprekken(vorige);
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

  const inhoud = (extra?: { onSluit: () => void }) => (
    <GesprekSidebar
      gesprekken={gesprekken}
      activeId={activeId}
      onNieuw={onNieuw}
      onOpen={onOpen}
      onHernoem={hernoem}
      onVerwijder={verwijder}
      onArchiveer={archiveer}
      onVerplaats={verplaats}
      onNieuwInWerkgebied={onNieuwInWerkgebied}
      laden={laden}
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
