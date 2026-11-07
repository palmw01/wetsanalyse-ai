"use client";

// De beurt van één werkplekvenster: starten, meekijken, opnieuw verbinden, stoppen en weer aanhaken.
//
// De beurt is van de server, niet van dit tabblad (zie `frontend/CLAUDE.md`). Deze hook houdt alleen bij waar de
// werkplek staat (`lib/beurtFase.ts`) en volgt de run met de lus uit `lib/beurtLus.ts`. Wat er op het scherm gebeurt –
// de bubbel bijwerken, een paneel openen, het artefact tonen – geeft het component mee als callbacks. De rekenkern
// staat in `lib/`: vitest draait zonder DOM, en een hook is daar niet te toetsen.
//
// De regels die hier vastliggen:
// - unmount koppelt alleen los: de cleanup aborteert de kijker, nooit de run;
// - alleen `done` sluit een beurt (`verwerkSseStroom` gooit anders, en de lus haakt opnieuw aan);
// - tokens hooguit één keer per frame (`frameplanner`);
// - de functies zijn stabiel (één object per venster), zodat `ThreadRij` een `memo` blijft.

import { useEffect, useLayoutEffect, useRef, useState } from "react";

import { haalActieveRun, stopRun, volgRun, type AgentHandlers } from "./api";
import { RUST, faseReducer, isBezig, lopendeRunId, magStarten, stoptNu, type BeurtFase, type FaseActie } from "./beurtFase";
import { volgTotEinde, type PogingStand } from "./beurtLus";
import { frameplanner, type StroomStand } from "./beurtStroom";
import {
  aankondiging, leesLopendeRuns, onthoudRun, schrijfLopendeRuns, standVanVorigeRun, vergeetRun, wachtMetWekker,
} from "./lopendeRun";

export type Frameplanner = ReturnType<typeof frameplanner>;

export interface BeurtScherm {
  /** De bubbel van deze beurt met de tekst en het denkproces van nu (hooguit één keer per frame). */
  schrijfStroom: (antId: string, stand: StroomStand) => void;
  /** De handlers voor wat het scherm met de stroom doet. `onLeeft` en `onDone` zet de hook zelf. */
  handlers: (antId: string, p: PogingStand, stroom: Frameplanner) => AgentHandlers;
  /** De stroom liep tot `done`: toon wat de agent vastlegde. Een fout hierin is geen verbroken verbinding. */
  opKlaar: (antId: string, stand: StroomStand) => Promise<void>;
  /** Een definitieve fout: de bubbel krijgt de melding. */
  opMislukt: (antId: string, stand: StroomStand, fout: unknown) => void;
  /** De naverwerking na `done` faalde. */
  opNaverwerkingFout: (fout: unknown) => void;
  /** Hervatten: maak de bubbel voor een run die doorliep, en geef zijn id. */
  voorHervatten: (runId: string) => string;
  /** Na elke poging: het verbruik is opgelopen. */
  onBeurtKlaar?: () => void;
}

export function useBeurt(scherm: BeurtScherm) {
  const [fase, setFase] = useState<BeurtFase>(RUST);
  // Synchroon bijgehouden: de state komt te laat voor twee Enters in dezelfde tick (vóór de eerste `await`).
  const faseRef = useRef<BeurtFase>(RUST);
  // De verbinding met de lopende beurt is weg en we haken opnieuw aan. Een tóéstand en geen tekst in de
  // antwoordbubbel: alleen zo kan de melding vanzelf verdwijnen zodra de stroom weer loopt.
  const [verbindingWeg, setVerbindingWeg] = useState(false);
  // De vorige beurt van dit gesprek is nooit afgekomen: het run-register van de agent is leeg (een herstart of
  // deploy). Beter dit zeggen dan een gesprek dat halverwege ophoudt zonder uitleg.
  const [runVerdwenen, setRunVerdwenen] = useState(false);
  // Hoe de laatste beurt afliep, voor de live-regio: een gewone beurt heeft geen melding.
  const [beurtEinde, setBeurtEinde] = useState("");
  // Waarmee de kijker van een lopende beurt is los te koppelen.
  const afbrekenRef = useRef<AbortController | null>(null);
  // Leeft dit venster nog? De unmount-cleanup aborteert `afbrekenRef`, maar een aanhaakactie die ná die cleanup zijn
  // controller zet, wordt door niets meer opgeruimd – en laat dan een SSE-stroom open staan voor een scherm dat
  // niemand ziet.
  const levendRef = useRef(true);
  // De callbacks van de laatste render; de functies hieronder blijven zo gelijk.
  const schermRef = useRef(scherm);
  useLayoutEffect(() => { schermRef.current = scherm; });

  // Verdwijnt dit venster (van gesprek wisselen remount het component), dan koppelen we alleen de KIJKER los. De run
  // zelf draait bij de agent door en wordt opgepakt zodra je terugkomt. Geen `abort()` op de beurt zelf: stoppen is
  // een expliciete handeling (`stop()`), geen bijwerking van navigeren.
  useEffect(() => {
    levendRef.current = true;
    return () => {
      levendRef.current = false;
      afbrekenRef.current?.abort();
    };
  }, []);

  const [api] = useState(() => {
    const zet = (a: FaseActie) => {
      faseRef.current = faseReducer(faseRef.current, a);
      setFase(faseRef.current);
    };
    const vergeetLopendeRun = (gid: string) => schrijfLopendeRuns(vergeetRun(leesLopendeRuns(), gid));

    /** Haak aan bij een run en volg hem tot het eind. Eén functie voor elke ingang – een verse beurt, een 409 en het
     *  weer oppakken van een beurt die doorliep – zodat de paden niet uit elkaar lopen. */
    async function volg(runId: string, gid: string, antId: string) {
      const s = () => schermRef.current;
      const uitkomst = await volgTotEinde({
        levend: () => levendRef.current,
        wacht: (ms) => wachtMetWekker(ms, () => levendRef.current),
        // Bij een herkansing blijft de bubbel staan zoals hij is: het heraanhaken speelt de eventlog opnieuw af. Wat
        // er aan de hand is staat in de banner – die verdwijnt vanzelf zodra er weer iets binnenkomt (`onLeeft`).
        opVerbroken: () => setVerbindingWeg(true),
        naPoging: () => {
          afbrekenRef.current = null;
          zet({ type: "einde" });
          // De beurt is klaar (geslaagd of niet): het verbruik is hoe dan ook opgelopen.
          s().onBeurtKlaar?.();
        },
        poging: async (p) => {
          const beheerser = new AbortController();
          afbrekenRef.current = beheerser;
          zet({ type: "aangehaakt", runId });
          const stroom = frameplanner(() => s().schrijfStroom(antId, p.stand()));
          try {
            await volgRun(runId, {
              ...s().handlers(antId, p, stroom),
              onLeeft: () => {
                p.pas({ type: "leeft" });
                setVerbindingWeg(false);
                // Er ís weer contact met een lopende beurt; een "de agent is herstart"-melding klopt dan niet meer.
                setRunVerdwenen(false);
              },
              onDone: (u) => setBeurtEinde(aankondiging(u)),
            }, 0, beheerser.signal);
            stroom.nu();
          } catch (e) {
            // Een half frame met oudere tekst mag de foutmelding of het herstel niet overschrijven.
            stroom.annuleer();
            throw e;
          }
        },
      });
      if (uitkomst.soort === "losgekoppeld") {
        // Zelf losgekoppeld of het venster is weg: niets te herstellen, dus ook geen melding laten staan.
        setVerbindingWeg(false);
        return;
      }
      if (uitkomst.soort === "mislukt") {
        setVerbindingWeg(false);
        s().opMislukt(antId, uitkomst.stand, uitkomst.fout);
        setBeurtEinde(aankondiging("mislukt"));
        return;
      }
      // De stroom liep tot het einde: deze beurt is afgerond en het spoor mag weg.
      vergeetLopendeRun(gid);
      try {
        await s().opKlaar(antId, uitkomst.stand);
      } catch (e) {
        // De beurt zelf is rond; alleen de naverwerking faalde. Niet opnieuw aanhaken – dat speelt dezelfde afloop
        // nog eens af – maar zeggen wat er mis is.
        setVerbindingWeg(false);
        s().opNaverwerkingFout(e);
      }
    }

    return {
      /** Claim het venster voor een nieuwe beurt. `false` = er loopt al iets; niets doen. */
      claim(): boolean {
        if (!magStarten(faseRef.current)) return false;
        zet({ type: "claim" });
        // Meldingen over de vórige beurt horen niet bij deze.
        setRunVerdwenen(false);
        setVerbindingWeg(false);
        setBeurtEinde("");
        return true;
      },
      /** De beurt kwam niet tot een run (een fout vóór de run, het budget op). */
      vrij() { zet({ type: "einde" }); },
      /** Onthoud dát er een beurt liep: komt de agent tussentijds opnieuw op, dan is dit het enige spoor. */
      onthoud(gid: string, runId: string) { schrijfLopendeRuns(onthoudRun(leesLopendeRuns(), gid, runId)); },
      volg,
      /** Loopt er nog een beurt in dit gesprek? Haak er dan weer op aan, vanaf `seq 0`. Alleen bij een lópende run: een
       *  beurt die klaar is staat al in de geschiedenis, en die twee keer tonen is erger dan hem missen. */
      async hervat(gid: string, berichtRunIds: string[]) {
        if (!magStarten(faseRef.current)) return;
        const lopend = await haalActieveRun(gid);
        // Opnieuw toetsen ná de round-trip: typte de jurist ondertussen een vraag, dan draait die run al.
        if (!magStarten(faseRef.current)) return;
        // Niet kunnen vaststellen is geen "er liep niets": stil laten.
        if (lopend === "onbekend") return;
        if (lopend && lopend.status === "loopt") {
          const antId = schermRef.current.voorHervatten(lopend.run_id);
          await volg(lopend.run_id, gid, antId);
          return;
        }
        // Geen lopende run. Stond er wél een open? Dan is het register leeg – een herstart of deploy – tenzij de
        // beurt gewoon is afgerond en zijn bericht heeft achtergelaten.
        const stand = standVanVorigeRun(leesLopendeRuns()[gid], berichtRunIds);
        if (stand === "verdwenen") setRunVerdwenen(true);
        if (stand !== "geen") vergeetLopendeRun(gid);
      },
      /** Stop de lopende beurt. Een verzoek aan de agent, geen dichtvallende verbinding: de knop blijft in de
       *  stopt-stand tot de run echt afloopt. */
      async stop() {
        const runId = lopendeRunId(faseRef.current);
        if (!runId || stoptNu(faseRef.current)) return;
        zet({ type: "stopGevraagd" });
        try {
          await stopRun(runId);
        } catch {
          // Mislukt het stopverzoek, dan loopt de beurt gewoon door. Zet de knop terug.
          zet({ type: "stopMislukt" });
        }
      },
      /** Mag er nu een beurt beginnen (synchroon)? */
      magStarten: () => magStarten(faseRef.current),
      levend: () => levendRef.current,
      sluitRunVerdwenen: () => setRunVerdwenen(false),
    };
  });

  return {
    ...api,
    fase,
    bezig: isBezig(fase),
    runId: lopendeRunId(fase),
    stopt: stoptNu(fase),
    verbindingWeg,
    runVerdwenen,
    beurtEinde,
  };
}
