"use client";

import Link from "next/link";
import dynamic from "next/dynamic";
import { useCallback, useEffect, useState } from "react";
import { useSession } from "next-auth/react";

import { AppSidebar } from "@/components/werkplek/AppSidebar";
import { SkipLink, HOOFDINHOUD_ID } from "@/components/ui/SkipLink";
import { leesStand, moetStarten } from "@/lib/rondleiding";
import { maakDemoScene, type DemoScene } from "@/lib/rondleidingDemo";
import { MobieleTopbar } from "@/components/werkplek/MobieleTopbar";
import { WerkplekClient } from "@/components/werkplek/WerkplekClient";
import { getVerbruik } from "@/lib/api";
import { resetdatum, tokensKort } from "@/lib/tokenbudget";
import type { BeslissingType, GesprekSamenvatting, Verbruiksstand } from "@/lib/types";

// De rondleiding rendert alleen bij `demo` – eerste bezoek of een expliciete klik. Statisch
// geïmporteerd zat hij (met TourBubbel) toch in de bundel van iedereen die de werkplek opent,
// terwijl de terugkerende gebruiker hem nooit ziet. `moetStarten`/`leesStand` blijven wél eager:
// die bepalen hierboven of er überhaupt iets te laden valt.
const Rondleiding = dynamic(
  () => import("@/components/rondleiding/Rondleiding").then((m) => m.Rondleiding),
  { ssr: false },
);

/** De volledige werkplek-app: links de sidebar (logo → chatgeschiedenis → instellingen/gebruiker),
 *  rechts het chatvenster. `activeId` stuurt de highlight; `mountKey` bepaalt wanneer het chatvenster
 *  vers remount (nieuw/openen) – een gesprek dat tijdens een lopende beurt een id krijgt, remount NIET
 *  (anders breekt de SSE-stream). Op mobiel wordt de sidebar een off-canvas drawer. */
export function WorkbenchShell({
  beginGesprekId = null,
  beginArtefact,
}: {
  /** Gesprek dat bij binnenkomst open moet staan (deep-link vanuit het annotatie-overzicht). */
  beginGesprekId?: string | null;
  /** Annotatie die bij binnenkomst als artefact open moet staan. */
  beginArtefact?: string;
} = {}) {
  const [gesprekken, setGesprekken] = useState<GesprekSamenvatting[]>([]);
  const [activeId, setActiveId] = useState<string | null>(beginGesprekId);
  const [mountKey, setMountKey] = useState(0);
  const [drawerOpen, setDrawerOpen] = useState(false);
  // Verhoogd zodra de chat een gesprek aanmaakte: de sidebar bezit de lijst en haalt hem dan opnieuw.
  const [verversSignaal, setVerversSignaal] = useState(0);
  // Een mislukte hernoem- of verwijderactie mag de werkplek niet blokkeren, maar hoort ook niet stil
  // te blijven: zonder melding is "de nieuwe naam staat er niet" niet te onderscheiden van "de naam
  // is niet aangeslagen", en blijft een gesprek na een bevestigde verwijdering gewoon staan.
  const [fout, setFout] = useState<string | null>(null);
  // De rondleiding draait op een eigen mount van het chatvenster met een voorbeeldscène erin. Zo
  // hoeft het echte gesprek niets van de demo te weten: bij het afsluiten verdwijnt deze mount en
  // hydrateert de gewone werkplek zichzelf weer uit de api.
  const [demo, setDemo] = useState<DemoScene | null>(null);
  const [demoArtefact, setDemoArtefact] = useState(false);
  const [demoBeslissingen, setDemoBeslissingen] = useState(0);
  const [laatsteBeslissing, setLaatsteBeslissing] = useState<BeslissingType | null>(null);
  // Staat de werkplek op slot? De rondleiding bepaalt dat per stap: in een stap die om een handeling
  // vraagt moet de knop eronder juist bereikbaar blijven.
  const [achtergrondSlot, setAchtergrondSlot] = useState(false);
  const [demoOpenSignaal, setDemoOpenSignaal] = useState(0);
  const [demoSluitSignaal, setDemoSluitSignaal] = useState(0);
  const { data: session } = useSession();
  const isBeheerder = session?.user?.role === "beheerder";
  // De verbruiksstand: voedt de meterregel in de sidebar, de waarschuwingsstrook en de blokkade van
  // de invoerbalk. Eén bron voor die drie, zodat ze niet uit elkaar kunnen lopen.
  const [verbruik, setVerbruik] = useState<Verbruiksstand | null>(null);
  const [strookGesloten, setStrookGesloten] = useState(false);

  const laadVerbruik = useCallback(async () => {
    try {
      setVerbruik(await getVerbruik());
    } catch {
      /* Stil: de meter is een hulpmiddel, geen blokkade van het scherm. */
    }
  }, []);

  useEffect(() => {
    // Bij binnenkomst, en daarna elke minuut als vangnet. De echte verversing is event-gedreven
    // (na een beurt, hieronder) – dit interval vangt alleen het geval dat er elders is verbruikt.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    void laadVerbruik();
    const id = setInterval(() => void laadVerbruik(), 60_000);
    return () => clearInterval(id);
  }, [laadVerbruik]);

  function startRondleiding() {
    setDemoArtefact(false);
    setDemoBeslissingen(0);
    setLaatsteBeslissing(null);
    setDemoOpenSignaal(0);
    setDemo(maakDemoScene());
  }

  // Eerste bezoek aan de werkplek: de rondleiding biedt zichzelf aan. Bewust hier en niet in een
  // effect verderop – dit is het enige scherm waar hij iets kan aanwijzen.
  useEffect(() => {
    // Bewust in een effect en niet in een lazy initializer: `localStorage` bestaat niet tijdens de
    // server-render, dus zou de server "geen rondleiding" renderen en de client wél – een
    // hydratatieverschil. Eén keer bij binnenkomst is precies wat hier moet gebeuren.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    if (moetStarten(leesStand())) startRondleiding();
  }, []);

  function nieuwGesprek() {
    setActiveId(null);
    setMountKey((k) => k + 1);
    setDrawerOpen(false);
  }

  function openGesprek(id: string) {
    setActiveId(id);
    setMountKey((k) => k + 1);
    setDrawerOpen(false);
  }

  // Het chatvenster maakte zojuist (bij de eerste beurt) een gesprek aan → highlight bijwerken zónder
  // remount, en de lijst verversen zodat het bovenaan verschijnt.
  function gesprekAangemaakt(id: string) {
    setActiveId(id);
    setVerversSignaal((n) => n + 1);
  }

  const actieveTitel = gesprekken.find((g) => g.id === activeId)?.titel || "Nieuw gesprek";

  return (
    <div className="relative flex h-full flex-col">
      <SkipLink />
      {/* Waar zit ik? Deze strook hing eerder aan de globale sitekop, en die verborg zichzelf op de
          werkplek – dus juist waar je de hele dag werkt, zag je hem nooit. Nu staat hij bovenaan de
          schil. De klik opent de voorwaarden als dialog (intercepting route), zodat je je gesprek
          niet verlaat. */}
      <Link
        href="/disclaimer"
        className="focus-ring block shrink-0 bg-waarschuwing/10 py-1 text-center text-[0.7rem] text-ink transition-colors hover:bg-waarschuwing/20"
      >
        <span className="font-semibold">Testomgeving – proof of concept.</span>{" "}
        Analyses kunnen verloren gaan. <span className="underline">Lees de voorwaarden</span>
      </Link>

      {/* Tokenbudget: één strook die twee standen kent. Hij wordt uit de SERVERSTAND afgeleid en
          niet uit een eerder gezette vlag, zodat hij niet kan blijven hangen als hij niet meer
          geldt – de klacht die mensen over Claude's "Approaching usage limit" hebben. Om diezelfde
          reden noemt hij het percentage én de resetdatum, in plaats van alleen dat er "een" limiet
          nadert. Wegklikken geldt voor deze sessie; bij 100% kan het niet, want dan is het geen
          waarschuwing meer maar de reden dat de invoer dicht is. */}
      {verbruik?.actief && verbruik.geblokkeerd && (
        <div role="status" className="shrink-0 border-b border-fout/30 bg-fout/10 px-4 py-2 text-center text-[0.8125rem] text-fout">
          <span className="font-semibold">Je tokenbudget is op.</span>{" "}
          Je kunt geen nieuwe vragen stellen tot {resetdatum(verbruik.reset_op)}.{" "}
          <Link href="/instellingen/verbruik" className="focus-ring rounded font-medium underline underline-offset-2">
            Bekijk je verbruik
          </Link>
        </div>
      )}
      {verbruik?.actief && !verbruik.geblokkeerd && verbruik.waarschuwing && !strookGesloten && (
        <div role="status" className="shrink-0 border-b border-waarschuwing/30 bg-waarschuwing/10 px-4 py-2 text-center text-[0.8125rem] text-aandacht-geel-tekst">
          <span className="font-semibold">{verbruik.percentage}% van je tokenbudget gebruikt.</span>{" "}
          Nog {tokensKort(verbruik.resterend)} tokens tot {resetdatum(verbruik.reset_op)}.{" "}
          <button
            type="button"
            onClick={() => setStrookGesloten(true)}
            className="focus-ring rounded font-medium underline underline-offset-2"
          >
            Sluiten
          </button>
        </div>
      )}

      {fout && (
        <div role="status" className="shrink-0 border-b border-fout/30 bg-fout/10 px-4 py-2 text-center text-[0.8125rem] text-fout">
          {fout}{" "}
          <button
            type="button"
            onClick={() => setFout(null)}
            className="focus-ring rounded font-medium underline underline-offset-2"
          >
            Sluiten
          </button>
        </div>
      )}

      {/* Tijdens de rondleiding gaat de werkplek op slot: klikken vangt de dimlaag op, maar zonder
          `inert` tab je er alsnog naartoe en druk je Enter op "Nieuw gesprek". In de stap die om een
          handeling vraagt staat het slot uit — daar moet je de knop juist kunnen bereiken. */}
      <div className="flex min-h-0 flex-1" inert={achtergrondSlot}>
      <AppSidebar
        activeId={activeId}
        onNieuw={nieuwGesprek}
        onOpen={openGesprek}
        onVerwijderd={(id) => {
          if (id === activeId) nieuwGesprek();
        }}
        onFout={setFout}
        onLijst={setGesprekken}
        verversSignaal={verversSignaal}
        drawerOpen={drawerOpen}
        onDrawerSluit={() => setDrawerOpen(false)}
        onRondleiding={startRondleiding}
        demoGesprekken={demo?.gesprekken}
        verbruik={verbruik}
      />

      {/* Rechterkolom: mobiele topbar + chatvenster. `tabIndex={-1}` zodat de skip-link de focus
          hier echt neer kan zetten – zonder dat springt alleen de scrollpositie. */}
      <div id={HOOFDINHOUD_ID} tabIndex={-1} className="flex min-w-0 flex-1 flex-col">
        <MobieleTopbar
          titel={actieveTitel}
          onOpenSidebar={() => setDrawerOpen(true)}
          actie={
            <button
              type="button"
              onClick={nieuwGesprek}
              aria-label="Nieuw gesprek"
              className="focus-ring inline-flex items-center justify-center rounded-lg border border-line p-2 text-lint transition-colors hover:bg-surface"
            >
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" aria-hidden>
                <path d="M12 5v14M5 12h14" />
              </svg>
            </button>
          }
        />

        {demo ? (
          <WerkplekClient
            key="rondleiding"
            demo={demo}
            initialGesprekId={null}
            onGesprekAangemaakt={() => {}}
            onGewijzigd={() => {}}
            demoOpenSignaal={demoOpenSignaal}
            demoSluitSignaal={demoSluitSignaal}
            onDemoArtefact={setDemoArtefact}
            onDemoBeslissing={(type) => {
              setDemoBeslissingen((n) => n + 1);
              setLaatsteBeslissing(type);
            }}
          />
        ) : (
          <WerkplekClient
            key={mountKey}
            initialGesprekId={activeId}
            beginArtefact={beginArtefact}
            onGesprekAangemaakt={gesprekAangemaakt}
            onGewijzigd={() => setVerversSignaal((n) => n + 1)}
            onRondleiding={startRondleiding}
            verbruik={verbruik}
            // Na een beurt is de stand net veranderd; wachten op het minuut-interval zou de meter
            // achter laten lopen op precies het moment dat de gebruiker ernaar kijkt.
            onBeurtKlaar={() => void laadVerbruik()}
          />
        )}
      </div>
      </div>

      {demo && (
        <Rondleiding
          onAchtergrondSlot={setAchtergrondSlot}
          isBeheerder={isBeheerder}
          artefactOpen={demoArtefact}
          beslissingen={demoBeslissingen}
          laatsteBeslissing={laatsteBeslissing}
          onOpenArtefact={() => setDemoOpenSignaal((n) => n + 1)}
          onSluitArtefact={() => setDemoSluitSignaal((n) => n + 1)}
          onKlaar={() => setDemo(null)}
        />
      )}
    </div>
  );
}
