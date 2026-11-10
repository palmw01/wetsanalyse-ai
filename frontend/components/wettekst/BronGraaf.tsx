"use client";

import { useContext, useEffect, useState, type ReactNode } from "react";

import { GraafIcoon } from "@/components/graaf/GraafIcoon";
import { Graaf, type GraafContext } from "@/components/graaf/Graaf";
import { useGraafStand, type GraafOpties, type GraafStand } from "@/components/graaf/useGraafStand";
import { TabRij } from "@/components/ui/Tabs";
import { ZijpaneelContext } from "@/components/ui/Zijpaneel";
import type { NodeDoel, NodeWeergave } from "@/lib/annotatieNode";
import type { KnoopData } from "@/lib/graaf/model";

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
 *  - In het zijpaneel is er één *Vergroten*, die van het paneel (`ZijpaneelContext`); daarbuiten (de sheet) een eigen. Op
 *    een pagina is hij altijd groot.
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
  const zijpaneel = useContext(ZijpaneelContext);
  const [geopend, setGeopend] = useState(weergave === "graaf");
  if (weergave === "graaf" && !geopend) setGeopend(true);
  const stand = useGraafStand(doel, geopend && aan, weergave === "graaf", samenhang?.extra, samenhang?.graaf);
  const [grootLokaal, setGrootLokaal] = useState(false);
  const groot = zijpaneel ? zijpaneel.vergroot : grootLokaal;
  const setGroot = zijpaneel ? zijpaneel.zetVergroot : setGrootLokaal;

  const claimt = Boolean(zijpaneel && claim && aan && weergave === "graaf");
  const claimEscape = zijpaneel?.claimEscape;
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
    if (groot) { setGroot(false); return true; }
    return false;
  }

  return { stand, geopend: geopend && aan, groot, setGroot, inZijpaneel: !!zijpaneel, escape };
}

export type BronGraafStand = ReturnType<typeof useBronGraaf>;

/** De graaf in het venster. `pagina`: op een eigen pagina, altijd groot. */
export function BronGraaf({ graaf, zichtbaar, pagina = false, herkomst, weergave, dekking, actiefElementId, onKiesElement,
  onOpenTekst, onWisselArtikel, onVraag, benaming, bijKnoop }: {
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
  onVraag?: (knoop: KnoopData) => void;
  benaming?: GraafContext;
  bijKnoop?: (knoop: KnoopData & { id: string }) => ReactNode;
}) {
  if (!graaf.geopend) return null;
  return (
    <div className={zichtbaar ? "flex min-h-0 flex-1 flex-col" : "hidden"} data-bron-graaf>
      <Graaf stand={graaf.stand as GraafStand} herkomst={herkomst} zichtbaar={zichtbaar} groot={graaf.groot || pagina}
        actiefElementId={actiefElementId} weergave={weergave} dekking={dekking} onKiesElement={onKiesElement ?? (() => {})}
        onOpenTekst={onOpenTekst} onWisselArtikel={onWisselArtikel} onVraag={onVraag} benaming={benaming} bijKnoop={bijKnoop} />
    </div>
  );
}

const TABS = [
  { key: "tekst", label: "Tekst" },
  { key: "graaf", label: "Graaf", icoon: <GraafIcoon className="h-3.5 w-3.5" /> },
] as const;

/** De keuze Tekst | Graaf onder de kop van een venster (`PaneelKop.balk`): dezelfde tabrij als die van het paneel
 *  (`TabRij`), zonder sluitknoppen. Buiten het zijpaneel staat *Vergroten* van de graaf rechts ernaast. */
export function WeergaveBalk({ weergave, onKies, graaf }: {
  weergave: Weergave;
  onKies: (w: Weergave) => void;
  /** Voor *Vergroten* buiten het zijpaneel (de sheet); in het zijpaneel en op een pagina niet. */
  graaf?: Pick<BronGraafStand, "groot" | "setGroot" | "inZijpaneel">;
}) {
  return (
    <div className="flex shrink-0 items-center gap-2 border-b border-line px-4 py-1.5" data-paneel-balk data-weergave={weergave}>
      <TabRij tabs={TABS} active={weergave} onChange={(k) => onKies(k as Weergave)} label="Weergave kiezen" soort="weergave" />
      {weergave === "graaf" && graaf && !graaf.inZijpaneel && (
        <button type="button" className="focus-ring rounded-knop p-2 text-muted hover:bg-surface" onClick={() => graaf.setGroot(!graaf.groot)}
          aria-label={graaf.groot ? "Verkleinen" : "Vergroten"} title={graaf.groot ? "Terug naar zijpaneel" : "Graaf vergroten"}>
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" aria-hidden="true">
            <path d={graaf.groot ? "M9 3v6H3m18 6h-6v6M3 9l6-6m6 18 6-6" : "M8 3H3v5m13 13h5v-5M3 3l6 6m6 6 6 6"} /></svg>
        </button>
      )}
    </div>
  );
}
