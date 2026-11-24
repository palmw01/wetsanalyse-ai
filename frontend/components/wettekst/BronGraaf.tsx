"use client";

import { useEffect, useState, type ReactNode } from "react";

import { Graaf, type GraafContext } from "@/components/graaf/Graaf";
import { useGraafStand, type GraafOpties, type GraafStand } from "@/components/graaf/useGraafStand";
import { TabRij, type TabRijItem } from "@/components/ui/Tabs";
import { usePaneel } from "@/components/ui/Paneel";
import { isVergroot } from "@/lib/paneelBediening";
import type { NodeDoel, NodeWeergave } from "@/lib/annotatieNode";
import type { KnoopData } from "@/lib/graaf/model";
import type { Onderwerp } from "@/lib/vraagLex";

/** Wat het venster van een bron toont: de tekst of de samenhang in de graaf. */
export type Weergave = "tekst" | "graaf";

/** De samenhang die een venster meekrijgt van waar het geopend werd: wat een antwoord of overzicht noemt (`extra`) en met
 *  welk bereik en welke nadruk de graaf opent (`graaf`). Zonder: de bepaling zelf, op de ketting. */
export interface Samenhang {
  extra: NodeDoel[];
  graaf: GraafOpties;
  /** Waar de doelen vandaan komen: een antwoord ("Dit antwoord") of een bepaling ("Deze bepaling"). */
  van?: "antwoord" | "bepaling";
}

/** De graaf van één venster (het bronvenster, ontdubbelen PR 1): de enige plek die de samenhang van een bepaling tekent,
 *  in het venster naast het gesprek, op de bronpagina en onder de annotatie. Het venster roept deze haak aan en tekent
 *  `BronGraaf`; zo kan het Escape laag voor laag afpellen (`escape`) voordat het zelf iets doet.
 *
 *  - De graaf laadt pas als zijn tab de eerste keer opengaat en blijft daarna gemount (de layout staat er dan nog).
 *  - Er is één *Vergroten*, die van het paneel (in de kop, `usePaneel()`); de graaf leest alleen of het paneel groot
 *    is. Op een pagina is hij altijd groot.
 *  - Op de graaf claimt het venster Escape bij het zijpaneel (`claim`), zodat de volgorde lagen → selectie → verkleinen →
 *    verbergen blijft. */
export function useBronGraaf({ doel, samenhang, aan, weergave, claim = false }: {
  doel: NodeDoel;
  samenhang?: Samenhang;
  /** De api kent de samenhang (`samenhangBeschikbaar`), en er valt iets te tekenen. */
  aan: boolean;
  weergave: Weergave;
  /** Het venster staat in het zijpaneel met een sluitknop: dan pelt het zelf Escape af. */
  claim?: boolean;
}) {
  const paneel = usePaneel();
  const [geopend, setGeopend] = useState(weergave === "graaf");
  if (weergave === "graaf" && !geopend) setGeopend(true);
  const stand = useGraafStand(doel, geopend && aan, weergave === "graaf", samenhang?.extra, samenhang?.graaf);
  // Groot is de stand van het paneel (*Vergroten* in de kop), niet van de graaf: er is één weg naar groot.
  const groot = isVergroot(paneel.plek);
  const zetVergroot = paneel.zetVergroot;

  const claimt = Boolean(claim && aan && weergave === "graaf");
  const claimEscape = paneel.claimEscape;
  useEffect(() => {
    if (!claimEscape) return;
    claimEscape(claimt);
    return () => claimEscape(false);
  }, [claimEscape, claimt]);

  /** Eén laag van Escape op de graaf. Onwaar: er viel niets af te pellen, het venster mag verbergen. */
  function escape(actief?: { id?: string; wis: () => void }): boolean {
    if (weergave !== "graaf" || !aan) return false;
    if (stand.lagenOpen) { stand.setLagenOpen(false); return true; }
    if (stand.selectie || actief?.id) { stand.setSelectie(null); actief?.wis(); return true; }
    if (groot && zetVergroot) { zetVergroot(false); return true; }
    return false;
  }

  return { stand, geopend: geopend && aan, groot, escape };
}

export type BronGraafStand = ReturnType<typeof useBronGraaf>;

/** De graaf in het venster. `pagina`: op een eigen pagina, altijd groot. */
export function BronGraaf({ graaf, zichtbaar, pagina = false, herkomst, weergave, dekking, actiefElementId, onKiesElement,
  onOpenTekst, onWisselArtikel, vraagOnderwerp, benaming, bijKnoop }: {
  graaf: BronGraafStand;
  zichtbaar: boolean;
  pagina?: boolean;
  herkomst?: string;
  /** De weergave van de bepaling (annotatie of lezing): de inspector haalt er tekst en markeringen uit. */
  weergave?: NodeWeergave;
  dekking?: Record<string, string[]>;
  actiefElementId?: string;
  onKiesElement?: (id?: string) => void;
  onOpenTekst: (knoop: KnoopData, anker?: string) => void;
  onWisselArtikel?: (doel: NodeDoel, graaf: GraafOpties) => void;
  vraagOnderwerp?: (knoop: KnoopData) => Onderwerp | undefined;
  benaming?: GraafContext;
  bijKnoop?: (knoop: KnoopData & { id: string }) => ReactNode;
}) {
  if (!graaf.geopend) return null;
  return (
    <div className={zichtbaar ? "flex min-h-0 flex-1 flex-col" : "hidden"} data-bron-graaf>
      <Graaf stand={graaf.stand as GraafStand} herkomst={herkomst} zichtbaar={zichtbaar} groot={graaf.groot || pagina}
        actiefElementId={actiefElementId} weergave={weergave} dekking={dekking} onKiesElement={onKiesElement ?? (() => {})}
        onOpenTekst={onOpenTekst} onWisselArtikel={onWisselArtikel} vraagOnderwerp={vraagOnderwerp} benaming={benaming} bijKnoop={bijKnoop} />
    </div>
  );
}

export const WEERGAVE_TABS = [
  { key: "tekst", label: "Tekst" },
  // Geen icoon: Tekst, Graaf en Diagram staan in één rij, en geen ervan heeft er een (melding gebruiker 24 nov 2026).
  { key: "graaf", label: "Graaf" },
] as const;

/** De keuze Tekst | Graaf onder de kop van een venster (`PaneelKop.balk`): dezelfde tabrij als die van het paneel
 *  (`TabRij`). Geen eigen *Vergroten*: dat is een handeling van het paneel, in de kop. */
export function WeergaveBalk<W extends string = Weergave>({ weergave, onKies, tabs = WEERGAVE_TABS }: {
  weergave: W;
  onKies: (w: W) => void;
  /** Standaard Tekst | Graaf; het annotatiepaneel voegt *Diagram* toe (en laat Graaf weg zonder kennisgraaf). */
  tabs?: readonly TabRijItem[];
}) {
  return (
    <div className="flex shrink-0 items-center gap-2 border-b border-line px-4 py-1.5" data-paneel-balk data-weergave={weergave}>
      <TabRij tabs={tabs} active={weergave} onChange={(k) => onKies(k as W)} label="Weergave kiezen" soort="weergave" />
    </div>
  );
}
