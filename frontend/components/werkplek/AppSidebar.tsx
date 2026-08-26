"use client";

import { useCallback, useEffect, useState } from "react";

import { Dialog } from "@/components/ui/Dialog";
import { GesprekSidebar } from "@/components/werkplek/GesprekSidebar";
import { hernoemGesprek, lijstGesprekken, verwijderGesprek } from "@/lib/api";
import type { GesprekSamenvatting } from "@/lib/types";

interface Props {
  /** Welk gesprek is actief (highlight). `null` op schermen buiten de chat. */
  activeId: string | null;
  onNieuw: () => void;
  onOpen: (id: string) => void;
  /** Het actieve gesprek is zojuist verwijderd — de aanroeper beslist wat er dan gebeurt. */
  onVerwijderd?: (id: string) => void;
  /** Hapering bij hernoemen/verwijderen. Wie de sidebar plaatst, bepaalt waar de melding landt. */
  onFout?: (melding: string) => void;
  /** De lijst zoals hij nu is — bv. om er een schermtitel uit af te leiden. */
  onLijst?: (gesprekken: GesprekSamenvatting[]) => void;
  /** Verhoog dit getal om de lijst opnieuw op te halen (bv. nadat een beurt een gesprek aanmaakte). */
  verversSignaal?: number;
  /** Mobiel: staat de off-canvas drawer open, en hoe sluit hij. */
  drawerOpen?: boolean;
  onDrawerSluit?: () => void;
  /** Start de rondleiding opnieuw (alleen de werkplek geeft dit mee). */
  onRondleiding?: () => void;
  /** De voorbeeldlijst van de rondleiding. Is die gezet, dan draait de sidebar als demo: de lijst
   *  komt hiervandaan en hernoemen/verwijderen blijven in dit geheugen — er gaat geen enkel verzoek
   *  naar de api. Zonder dit hing de rondleiding af van wat er in het account staat, en dat is bij
   *  een nieuwe gebruiker niets. */
  demoGesprekken?: GesprekSamenvatting[];
}

/** De gesprekssidebar met alles eromheen: laden, hernoemen, verwijderen, en de mobiele drawer.
 *
 *  Gedeeld door de werkplek en het annotatie-overzicht, zodat je bij het wisselen niet "uit de app"
 *  stapt — dat is wat Claude's artifacts-tab ook doet: de sidebar blijft, alleen het hoofdgebied
 *  verandert. De handlers verschillen wél per scherm: in de werkplek wisselt een klik van gesprek in
 *  lokale state, op het overzicht navigeert hij terug naar de werkplek. */
export function AppSidebar({
  activeId, onNieuw, onOpen, onVerwijderd, onFout, onLijst, verversSignaal = 0,
  drawerOpen = false, onDrawerSluit, onRondleiding, demoGesprekken,
}: Props) {
  const [gesprekken, setGesprekken] = useState<GesprekSamenvatting[]>(demoGesprekken ?? []);
  const [laden, setLaden] = useState(!demoGesprekken);
  const demo = Boolean(demoGesprekken);

  const verversLijst = useCallback(() => {
    // In de rondleiding is deze lijst een voorbeeld; ophalen zou hem overschrijven met de (vaak
    // lege) echte lijst.
    if (demo) return;
    lijstGesprekken()
      .then((lijst) => {
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
  // een effect: anders rendert de sidebar eerst één frame met de vórige lijst — bij het starten dus
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
      await hernoemGesprek(id, titel);
      verversLijst();
    } catch {
      onFout?.("De nieuwe naam is niet opgeslagen.");
    }
  }

  /** De bevestiging zit in de knop zelf (`BevestigKnop`, twee klikken) — hetzelfde gebaar als in het
   *  artefact; geen `window.confirm` midden in een app met een eigen vormtaal. */
  async function verwijder(id: string) {
    if (demo) {
      setGesprekken((lijst) => lijst.filter((g) => g.id !== id));
      return;
    }
    try {
      await verwijderGesprek(id);
      // Meteen uit de lijst halen en dáárna pas verversen: de DELETE is al geslaagd, dus wachten op
      // een round trip laat de rij onnodig staan — en het verwijderde gesprek is meestal het gesprek
      // dat je open hebt.
      setGesprekken((lijst) => lijst.filter((g) => g.id !== id));
      onVerwijderd?.(id);
      verversLijst();
    } catch {
      onFout?.("Het gesprek is niet verwijderd.");
    }
  }

  const inhoud = (extra?: { onSluit: () => void }) => (
    <GesprekSidebar
      gesprekken={gesprekken}
      activeId={activeId}
      onNieuw={onNieuw}
      onOpen={onOpen}
      onHernoem={hernoem}
      onVerwijder={verwijder}
      laden={laden}
      onSluit={extra?.onSluit}
      onRondleiding={onRondleiding}
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
