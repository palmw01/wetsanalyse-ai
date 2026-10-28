"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState } from "react";

import { ChevronOmlaag } from "@/components/ui/Icoon";
import { Melding } from "@/components/ui/Melding";
import { Skeleton } from "@/components/ui/Skeleton";
import { OnbewaardMelding } from "@/components/werkgebieden/OnbewaardMelding";
import { WerkgebiedSchil } from "@/components/werkgebieden/WerkgebiedSchil";
import { foutTekst, haalWerkgebied, isApiError, verwijderWerkgebied } from "@/lib/api";
import { metSpoor } from "@/lib/uiSpoor";
import { useOnbewaardBewaker } from "@/lib/useOnbewaardBewaker";
import { verwijderdUit, verwijderdZin, type Verwijderd } from "@/lib/verwijderen";
import type { Werkgebied } from "@/lib/types";
import { useWerkgebiedStand, type WerkgebiedStand } from "@/lib/useWerkgebiedStand";
import { isRevisieConflict } from "@/lib/werkgebied";

export interface MutatieOpties {
  /** De bevestiging na afloop; een functie als die van de uitkomst afhangt. */
  gelukt?: string | (() => string);
  /** Een fout die over de invoer zelf gaat en bij het formulier hoort: geef `true` als hij daar is
   *  afgehandeld. Een revisieconflict komt hier niet langs. */
  opFout?: (e: unknown) => boolean;
}
export type Mutatie = (actie: (revisie: number) => Promise<Werkgebied>, opties?: MutatieOpties) => Promise<boolean>;

interface Project {
  wg: Werkgebied;
  laad: () => Promise<void>;
  muteer: Mutatie;
  verwijder: () => Promise<void>;
  meld: (type: "bevestiging" | "waarschuwing", tekst: string) => void;
  /** Ruimer dan de leesbreedte (de begrippen, de graaf); de pagina die het nodig heeft, zet het. */
  zetBreed: (breed: boolean) => void;
  /** Draagt een pagina niet-bewaarde wijzigingen (de begripskaart)? Dan vraagt elke navigatie weg
   *  eerst bevestiging: een link (de tabs, de sidebar, het kruimelpad) en een knop die zelf navigeert. */
  zetOnbewaard: (onbewaard: boolean) => void;
  onbewaard: boolean;
}

const ProjectContext = createContext<Project | null>(null);
const StandContext = createContext<WerkgebiedStand | null>(null);

/** Het werkgebied van de pagina's eronder (`app/werkgebieden/[id]/layout.tsx`), met de stand die de
 *  tellers en kaarten dragen (gesprekken, begrippen, kandidaten, werkvoorraad). */
export function useWerkgebied(): Project & { stand: WerkgebiedStand } {
  const p = useContext(ProjectContext);
  const stand = useContext(StandContext);
  if (!p || !stand) throw new Error("useWerkgebied buiten WerkgebiedProject");
  return { ...p, stand };
}

/** De stand laadt één keer per werkgebied en revisie, hier en niet per tab: deze laag blijft staan bij een
 *  tabwissel, dus de tellers in de tabbalk zijn overal dezelfde en de werkvoorraad (die de graaf vraagt)
 *  wordt niet bij elke klik opnieuw opgehaald. */
function StandLaag({ wg, children }: { wg: Werkgebied; children: React.ReactNode }) {
  const stand = useWerkgebiedStand(wg);
  return <StandContext.Provider value={stand}>{children}</StandContext.Provider>;
}

/** Eén werkgebied als project (spoor G2): de laag die het werkgebied één keer laadt en draagt voor alle
 *  pagina's eronder – de vier tabs en de detailpagina's. Een wissel van tab is een navigatie (eigen URL,
 *  Terug werkt) maar laadt het werkgebied niet opnieuw: deze laag blijft staan.
 *
 *  Werkgebieden zijn gedeeld, dus elke mutatie stuurt de revisie in beeld mee. Wijzigde iemand anders het
 *  werkgebied intussen (412), dan laadt de pagina de nieuwste stand en zegt dat – de handeling wordt niet
 *  stil opnieuw uitgevoerd, want die kan op de nieuwe stand iets anders betekenen. */
export function WerkgebiedProject({ id, children }: { id: string; children: React.ReactNode }) {
  const router = useRouter();
  const [wg, setWg] = useState<Werkgebied | null>(null);
  const [nietGevonden, setNietGevonden] = useState(false);
  const [verwijderd, setVerwijderd] = useState<Verwijderd | null>(null);
  const [fout, setFout] = useState<string | null>(null);
  const [melding, setMelding] = useState<{ type: "bevestiging" | "waarschuwing"; tekst: string } | null>(null);
  const [breed, setBreed] = useState(false);
  const [onbewaard, setOnbewaard] = useState(false);
  const bewaker = useOnbewaardBewaker(onbewaard);
  const vraagRef = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (bewaker.wachtend) vraagRef.current?.scrollIntoView({ block: "nearest" });
  }, [bewaker.wachtend]);

  const laad = useCallback(async () => {
    try {
      setWg(await haalWerkgebied(id));
    } catch (e) {
      if (isApiError(e) && e.status === 404) {
        setNietGevonden(true);
        setVerwijderd(verwijderdUit(e));
      } else setFout(foutTekst(e, "Het werkgebied kon niet worden geladen."));
    }
  }, [id]);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    laad();
  }, [laad]);

  const muteer: Mutatie = useCallback(
    async (actie, { gelukt, opFout } = {}) => {
      if (!wg) return false;
      setFout(null);
      setMelding(null);
      try {
        setWg(await actie(wg.revisie));
        if (gelukt) setMelding({ type: "bevestiging", tekst: typeof gelukt === "function" ? gelukt() : gelukt });
        return true;
      } catch (e) {
        if (isRevisieConflict(e)) {
          await laad();
          setMelding({
            type: "waarschuwing",
            tekst: "Iemand anders wijzigde dit werkgebied net. De nieuwste stand staat nu in beeld; kijk of je wijziging nog nodig is.",
          });
        } else if (!opFout?.(e)) {
          setFout(foutTekst(e));
        }
        return false;
      }
    },
    [wg, laad],
  );

  /** Echt wissen, zoals een annotatie (`lib/verwijderen.ts`); daarna naar de lijst. Een 412 laadt de
   *  nieuwste stand: op die stand kan verwijderen iets anders betekenen. */
  const verwijder = useCallback(async () => {
    if (!wg) return;
    setFout(null);
    setMelding(null);
    try {
      await metSpoor("werkgebied_verwijderen", () => verwijderWerkgebied(id, wg.revisie));
      router.push("/werkgebieden");
    } catch (e) {
      if (isRevisieConflict(e)) {
        await laad();
        setMelding({ type: "waarschuwing", tekst: "Iemand anders wijzigde dit werkgebied net. Bekijk de nieuwe stand voordat je het verwijdert." });
      } else setFout(foutTekst(e, "Het werkgebied is niet verwijderd."));
    }
  }, [wg, id, laad, router]);

  const waarde = useMemo<Project | null>(() => wg && ({
    wg, laad, muteer, verwijder, onbewaard,
    meld: (type, tekst) => setMelding({ type, tekst }),
    zetBreed: setBreed,
    zetOnbewaard: setOnbewaard,
  }), [wg, laad, muteer, verwijder, onbewaard]);

  if (nietGevonden)
    return (
      <WerkgebiedSchil titel="Werkgebied" onFout={setFout}>
        <Link href="/werkgebieden"
          className="focus-ring mb-2 inline-flex items-center gap-1 rounded text-xs text-muted transition-colors hover:text-ink">
          <ChevronOmlaag className="rotate-90" /> Alle werkgebieden
        </Link>
        <Melding type="uitleg">
          <span data-verwijderd>{verwijderd ? verwijderdZin(verwijderd) : "Dit werkgebied bestaat niet (meer)."}</span>
        </Melding>
      </WerkgebiedSchil>
    );

  return (
    <WerkgebiedSchil titel={wg?.naam ?? "Werkgebied"} onFout={setFout} breed={breed} bewaak={bewaker.bewaak}>
      {fout && <Melding type="fout" className="mb-4">{fout}</Melding>}
      {melding && <Melding type={melding.type} compact className="mb-4">{melding.tekst}</Melding>}
      {bewaker.wachtend && (
        <div ref={vraagRef}>
          <OnbewaardMelding className="mb-4" handeling="verlaten" onBlijf={bewaker.blijf}
            onToch={() => {
              setOnbewaard(false);
              bewaker.toch();
            }} />
        </div>
      )}
      {waarde ? (
        <ProjectContext.Provider value={waarde}><StandLaag wg={waarde.wg}>{children}</StandLaag></ProjectContext.Provider>
      ) : !fout && (
        <div className="space-y-3">
          <Skeleton className="h-6 w-64" />
          <Skeleton className="h-3 w-96 max-w-full" />
        </div>
      )}
    </WerkgebiedSchil>
  );
}
